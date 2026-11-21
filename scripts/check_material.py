#!/usr/bin/env python
# -*- coding: utf-8 -*-
# <!--module
# id: checker
# title: 自检工具
# owns: 静态/运行时检查的实现 · 检查项的执行与报告产出
# not_owns: 能力的定义与边界 · 主项目链路 · 素材的形态契约 · 检查项与判据 · 机器可读格式 · 风格取舍
# rendering: 工具级：按调用方 --size 声明的 W×H 实测（画布尺寸/整数坐标/越界/重叠/字号/对比度/清单自洽）
# see: references/self_check_gates.md, references/output_format.md
# -->
"""素材自检闸门（自包含版）—— 静态契约 A1–A12 + 无头真渲染 B1–B7。

本文件 = **项目基础实现** + **技能专属扩展**（两段，互不干扰）：

  · 基础实现：A1–A12 / B1–B7。由 `scripts/sync_base.py` 从项目实现自动生成，
    **不要手改** —— 改请改项目里的 `check_material.py`（或 `webview_render.py` 里的
    find_edge / parse_size），然后重跑 `sync_base.py`。这样技能与项目实现不会漂移。
  · 技能专属扩展：产物格式约束（A13 清单块 / `--json` / `--emit-manifest`）。
    在文件末尾 `SKILL-ONLY EXTENSION BEGIN/END` 标记之间，**项目里没有这块**。
    `sync_base.py` 会按标记把它**原样保留**，所以刷新基础部分不会把它冲掉。

相对项目版的其它差别：把 `find_edge` / `parse_size` 内联进来，
去掉了对 `webview_render` 的导入 —— 于是本文件不依赖任何**项目内**文件，可独立运行。

退出码：0 = 全部通过；1 = 存在 FAIL
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import shutil
import pathlib

# 技能内的目录（自包含：不依赖项目路径）
HERE = os.path.dirname(os.path.abspath(__file__))   # .../scripts
SKILL_DIR = os.path.dirname(HERE)                   # 技能根目录

# Windows 控制台默认是 GBK：报告里的 ✗ / ★ 等符号一旦打印就会抛
# UnicodeEncodeError，让「有 FAIL」变成整份报告崩掉。这里统一把 stdout
# 改成 UTF-8 + errors=replace —— 不改检查逻辑，只修输出。
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

_EDGE = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

def find_edge(explicit=None):
    if explicit:
        if os.path.isfile(explicit):
            return explicit
        raise FileNotFoundError(f"--edge 路径不存在：{explicit}")
    for c in _EDGE:
        if os.path.isfile(c):
            return c
    raise FileNotFoundError("找不到 Edge / Chrome，请用 --edge 指定。")

def parse_size(html_text, override=""):
    """从 HTML 推断面板尺寸（W×H）。

    规则（按文档顺序取**第一个同时声明了 width 与 height 的样式块**）：
      · CSS 规则块 `{ ... }`（如 `html, body { width:320px; height:240px; }`）
      · 内联样式 `style="..."` / `style='...'`
    所以「契约里把 html,body（或 #stage）写成 W×H 并放在最前」就能被稳定识别。

    历史坑：旧实现用 `width\\s*:(\\d+)px[^;]*height\\s*:(\\d+)px` 单条正则，
    `[^;]*` 不能跨越分号 → `width:320px; height:240px`（最自然的写法）**匹配不到**，
    会静默回落到默认 320×240；320×170 的素材因此被按 320×240 渲染。
    现改为「按样式块成对提取」，两种写法都能识别。
    """
    if override:
        w, h = override.lower().split("x")
        return int(w), int(h)

    cands = []                                        # (出现位置, 样式体)
    for m in re.finditer(r"\{([^{}]*)\}", html_text):
        cands.append((m.start(), m.group(1)))
    for m in re.finditer(r"""style\s*=\s*(?:"([^"]*)"|'([^']*)')""", html_text):
        cands.append((m.start(), m.group(1) if m.group(1) is not None else m.group(2)))

    for _, body in sorted(cands, key=lambda t: t[0]):
        mw = re.search(r"width\s*:\s*(\d+)\s*px", body, re.I)
        mh = re.search(r"height\s*:\s*(\d+)\s*px", body, re.I)
        if mw and mh:
            return int(mw.group(1)), int(mh.group(1))
    return 320, 240


# ----------------------------------------------------------------- 解析

TAG_RE = re.compile(r'<([a-zA-Z][\w-]*)((?:[^<>"\']|"[^"]*"|\'[^\']*\')*?)/?>', re.S)
ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')
STYLE_BLOCK_RE = re.compile(r'<style[^>]*>(.*?)</style>', re.S | re.I)
RULE_RE = re.compile(r'([^{}]+)\{([^{}]*)\}')
PLACEHOLDER_RE = re.compile(r'\{\{\s*([^}]*?)\s*\}\}')

DEFAULT_SIZE = (320, 240)


def parse_css_map(css: str) -> dict:
    """选择器 → {属性: 值}（粗略但够用；跳过 @ 规则）。"""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    out: dict = {}
    for sel, body in RULE_RE.findall(css):
        sel = sel.strip()
        if not sel or sel.startswith('@'):
            continue
        decl = {}
        for part in body.split(';'):
            if ':' in part:
                k, v = part.split(':', 1)
                decl[k.strip().lower()] = v.strip()
        for one in sel.split(','):
            one = one.strip()
            if one and not one.startswith('@'):
                out.setdefault(one, {}).update(decl)
    return out


def iter_tags(html: str):
    """产出 (tag, attrs_dict)。attrs 里的 '_inline' 已解析为 {属性: 值}。"""
    for m in TAG_RE.finditer(html):
        tag = m.group(1).lower()
        if tag in ('br', 'hr', 'meta', 'link', 'img', 'input'):
            continue
        raw = m.group(2) or ''
        attrs = {k.lower(): v for k, v in ATTR_RE.findall(raw)}
        attrs['_tag'] = tag
        inline = {}
        for part in (attrs.get('style') or '').split(';'):
            if ':' in part:
                k, v = part.split(':', 1)
                inline[k.strip().lower()] = v.strip()
        attrs['_inline'] = inline
        yield tag, attrs


def eff_style(attrs: dict, css_map: dict) -> dict:
    """元素的「有效样式」：类 → id → 标签 → 内联（后者覆盖前者）。"""
    d = {}
    for c in (attrs.get('class') or '').split():
        d.update(css_map.get('.' + c, {}))
    if attrs.get('id'):
        d.update(css_map.get('#' + attrs['id'], {}))
    d.update(css_map.get(attrs.get('_tag', ''), {}))
    d.update(attrs.get('_inline', {}))
    return d


def px(v: str):
    """'18px' → 18；非像素值返回 None。"""
    if v is None:
        return None
    m = re.fullmatch(r'(-?\d+(?:\.\d+)?)px', str(v).strip())
    return float(m.group(1)) if m else None


# ---- A15 用：原生控件清单与「算不算被接管」的判据 ----
# 「受控」= 界面上每一个像素都由素材自己的 CSS 决定。浏览器给原生控件的默认外观
# （深色背景下刺眼的白底下拉、Windows 上灰扑扑的按钮、蓝色下划线链接）一律不算数。
NATIVE_CONTROL = {
    # 标签: 必须显式声明的属性组；每一组是「任选其一」的属性名元组
    'button':   [('appearance', '-webkit-appearance'), ('background',), ('border',), ('font-family',)],
    'input':    [('appearance', '-webkit-appearance'), ('background',), ('border',), ('font-family',)],
    'select':   [('appearance', '-webkit-appearance'), ('background',), ('border',), ('font-family',)],
    'textarea': [('appearance', '-webkit-appearance'), ('background',), ('border',), ('font-family',)],
    'progress': [('appearance', '-webkit-appearance'), ('background',), ('border',)],
    'meter':    [('appearance', '-webkit-appearance'), ('background',), ('border',)],
    # <option> 由系统画下拉列表，深色主题里会闪白块 —— 至少把底色和字色压住
    'option':   [('background',), ('color',)],
    'ul':       [('list-style', 'list-style-type'), ('margin',), ('padding',)],
    'ol':       [('list-style', 'list-style-type'), ('margin',), ('padding',)],
    'dl':       [('margin',), ('padding',)],
    'h1':       [('margin',), ('font-size',), ('font-weight',)],
    'h2':       [('margin',), ('font-size',), ('font-weight',)],
    'h3':       [('margin',), ('font-size',), ('font-weight',)],
    'h4':       [('margin',), ('font-size',), ('font-weight',)],
    'h5':       [('margin',), ('font-size',), ('font-weight',)],
    'h6':       [('margin',), ('font-size',), ('font-weight',)],
    'a':        [('color',), ('text-decoration',)],
    'table':    [('border-collapse', 'margin'), ('padding', 'border-spacing')],
    'fieldset': [('margin',), ('padding',), ('border',)],
    'pre':      [('margin',), ('padding',), ('font-family',)],
    'hr':       [('margin',), ('border',)],
}

# 这些标签是「骨架」，不算控件，不参与 A15
SKELETON_TAGS = {'html', 'head', 'body', 'style', 'script', 'meta', 'link', 'title',
                 'div', 'span', 'i', 'b', 'em', 'strong', 'small', 'br', 'img',
                 'canvas', 'svg', 'path', 'g', 'circle', 'rect', 'line', 'text'}


def used_native_tags(html: str):
    """素材里用到的原生控件标签（去重、按清单顺序）。"""
    seen = []
    for m in TAG_RE.finditer(html):
        tag = m.group(1).lower()
        if tag in NATIVE_CONTROL and tag not in seen:
            seen.append(tag)
    order = list(NATIVE_CONTROL)
    return sorted(seen, key=order.index)


def style_control_check(html: str, css_map: dict):
    """A15：原生控件必须由样式接管，返回 [(tag, 缺什么), …]。"""
    missing = []
    for tag in used_native_tags(html):
        # 标签规则 + 通配 `*` 规则叠加：两者都算「作者写的样式」
        props = dict(css_map.get('*', {}))
        props.update(css_map.get(tag, {}))
        lacks = []
        for group in NATIVE_CONTROL[tag]:
            if not any(g in props for g in group):
                lacks.append(group[0])
        if lacks:
            missing.append((tag, lacks))
    return missing


# ----------------------------------------------------------------- A 静态检查

def static_check(path: str, want=DEFAULT_SIZE):
    res = {'file': os.path.basename(path), 'fail': [], 'warn': [], 'info': []}
    html = open(path, encoding='utf-8').read()

    # A12 DOCTYPE
    if not html.lstrip().lower().startswith('<!doctype html>'):
        res['fail'].append('A12 缺少 <!DOCTYPE html>')

    style = '\n'.join(STYLE_BLOCK_RE.findall(html))
    css_map = parse_css_map(style)

    # A1 尺寸
    try:
        size = parse_size(html)
    except Exception as e:
        size = None
        res['fail'].append(f'A1 parse_size 抛错：{e}')
    if size is None:
        res['fail'].append('A1 未能从样式里推断出尺寸（需要第一个同时声明 width+height 的规则块）')
    elif tuple(size) != tuple(want):
        res['fail'].append(f'A1 推断尺寸 {size} ≠ 期望 {want}')
    else:
        res['info'].append(f'A1 尺寸 {size[0]}x{size[1]}')

    # A2 / A3 视口与居中
    html_body = css_map.get('html', {})
    html_body.update(css_map.get('body', {}))
    for prop, must in (('margin', '0'), ('padding', '0'), ('overflow', 'hidden')):
        val = html_body.get(prop, '')
        if must not in str(val):
            res['warn'].append(f'A2 html,body 的 {prop} 不是 "{must}"（当前 "{val}"）')
    if 'width' not in html_body or 'height' not in html_body:
        res['fail'].append('A2 html,body 未同时声明 width/height')
    for bad, why in (('place-items', '会居中'), ('margin:auto', '会居中')):
        if bad in style.replace(' ', ''):
            res['fail'].append(f'A3 样式里出现 {bad}（{why} → 画面会偏移）')
    for bad in ('100vw', '100vh'):
        if bad in style:
            res['fail'].append(f'A3 样式里出现 {bad}（无头视口下不可靠）')

    # 遍历元素
    slots, placeholder_names, from_refs, ids = set(), set(), set(), {}
    default_names = set(re.findall(r"__setSlot\(\s*'([\w-]+)'", html))
    tags = list(iter_tags(html))

    for tag, attrs in tags:
        if 'data-slot' in attrs:
            slots.add(attrs['data-slot'])
        if attrs.get('data-from'):
            from_refs.add(attrs['data-from'])
        if attrs.get('id'):
            ids[attrs['id']] = ids.get(attrs['id'], 0) + 1

        # A6 bar/seg 必备字段（data-box 只对连续宽度条强制；seg 由 CSS 定尺寸）
        kind = attrs.get('data-kind')
        if kind in ('bar', 'seg'):
            need = ('data-from', 'data-max', 'data-box') if kind == 'bar' else ('data-from', 'data-max')
            for need1 in need:
                if need1 not in attrs:
                    res['fail'].append(
                        f"A6 data-kind={kind} 的 [data-slot={attrs.get('data-slot')}] 缺 {need1}")
        # A7 data-box 格式与越界
        if attrs.get('data-box'):
            parts = [p.strip() for p in attrs['data-box'].split(',')]
            if len(parts) != 4 or not all(re.fullmatch(r'-?\d+', p) for p in parts):
                res['fail'].append(f"A7 data-box 不是 4 个整数：{attrs['data-box']}")
            else:
                x, y, w, h = (int(p) for p in parts)
                W, H = want
                if x < 0 or y < 0 or x + w > W or y + h > H:
                    res['fail'].append(
                        f"A7 data-box 越界 {attrs['data-box']}（画布 {W}x{H}）")

        st = eff_style(attrs, css_map)

        # A9 整数像素
        for prop in ('left', 'top', 'width', 'height'):
            if prop in st and 'px' in str(st[prop]):
                v = px(st[prop])
                if v is None:
                    res['warn'].append(f'A9 [{tag}] {prop}: {st[prop]} 不是纯 px')
                elif v != int(v):
                    res['fail'].append(f'A9 [{tag}] {prop}={st[prop]} 是半像素')

        # A10 position:absolute 必须能定位（left/top 或 right/bottom 有其一）
        if str(st.get('position', '')).strip() == 'absolute':
            miss = [p for p, alt in (('left', 'right'), ('top', 'bottom'))
                    if p not in st and alt not in st]
            if miss:
                label = attrs.get('id') or attrs.get('class') or tag
                res['fail'].append(
                    f'A10 [{label}] position:absolute 但缺 {" / ".join(miss)}（会堆到左上角）')

        # A11 越界（只在内联给了完整矩形时判断）
        inl = attrs.get('_inline', {})
        lx, ly = px(inl.get('left')), px(inl.get('top'))
        lw, lh = px(inl.get('width')), px(inl.get('height'))
        W, H = want
        if lx is not None and ly is not None:
            if not (0 <= lx <= W and 0 <= ly <= H):
                res['fail'].append(f'A11 [{tag}] left/top 越界：{lx},{ly}')
            if lw is not None and lx + lw > W:
                res['fail'].append(f'A11 [{tag}] 右边界越界：{lx}+{lw} > {W}')
            if lh is not None and ly + lh > H:
                res['fail'].append(f'A11 [{tag}] 下边界越界：{ly}+{lh} > {H}')

    # A4 占位符 ↔ data-slot
    for ph in PLACEHOLDER_RE.findall(html):
        placeholder_names.add(ph)
        if ph not in slots:
            res['fail'].append(f'A4 占位符 {{{{{ph}}}}} 没有同名 data-slot')
    res['info'].append(f'A4 占位符 {len(placeholder_names)} 个 / data-slot {len(slots)} 个')

    # A5 data-from / 默认值 是否可解析
    for ref in sorted(from_refs - slots - default_names):
        res['warn'].append(f'A5 data-from="{ref}" 既没有 data-slot 也没有默认值（可能永远不会被驱动）')
    for nm in sorted(default_names - slots):
        res['info'].append(f'A5 __setSlot 默认值 {nm} 没有对应的文本槽（只有条在跟随时属正常）')

    # A8 重复 id
    for k, v in ids.items():
        if v > 1:
            res['fail'].append(f'A8 id="{k}" 重复 {v} 次')

    # A15 原生控件必须受样式接管（不许吃浏览器默认外观）
    bad = style_control_check(html, css_map)
    if bad:
        for tag, lacks in bad:
            res['fail'].append(
                f'A15 <{tag}> 没有接管外观，缺 {"/".join(lacks)}'
                f'（原生控件会带出浏览器默认样式；能自绘就别用它）')
    else:
        native = used_native_tags(html)
        res['info'].append('A15 原生控件 %s' % ('、'.join('<' + t + '>' for t in native) if native else '0 个（全自绘）'))

    return res


# ----------------------------------------------------------------- B 运行期检查

SELFTEST_JS = r"""
<script>
(function () {
  var out = { ok: true, err: [], warn: [], slotCount: 0, leftover: 0, maxR: 0, maxB: 0 };
  function fail(m) { out.ok = false; out.err.push(String(m)); }
  try {
    /* --- 1) 入口函数 --- */
    if (typeof window.__setSlot !== 'function') fail('window.__setSlot 未定义');

    /* --- 2) 内容是否超出画布（用默认值量，避免极端值把条撑爆） --- */
    var els = document.querySelectorAll('#stage, #stage *');
    if (!els.length) els = document.querySelectorAll('body > *');
    var maxR = 0, maxB = 0;
    for (var q2 = 0; q2 < els.length; q2++) {
      var rect = els[q2].getBoundingClientRect();
      if (rect.width > 0 || rect.height > 0) {
        if (rect.right > maxR) maxR = rect.right;
        if (rect.bottom > maxB) maxB = rect.bottom;
      }
    }
    out.maxR = Math.round(maxR); out.maxB = Math.round(maxB);
    if (maxR > 320.5 || maxB > 240.5) {
      fail('内容超出画布 right=' + Math.round(maxR) + ' bottom=' + Math.round(maxB) + '（应 <= 320x240）');
    }

    /* --- 3) 是否还有未替换的占位符（注意：本脚本源码里不能出现字面量花括号对） --- */
    var src = document.documentElement.outerHTML;
    var OB = '{' + '{', CB = '}' + '}';
    var hits = src.match(new RegExp(OB + '[^}]*' + CB, 'g'));
    out.leftover = hits ? hits.length : 0;
    if (out.leftover) {
      var idx = src.indexOf(OB);
      out.ctx = src.substr(Math.max(0, idx - 70), 150);
      fail('仍有 ' + out.leftover + ' 处未替换的占位符：…' + out.ctx + '…');
    }

    /* --- 5) 元素重叠检测（文字压文字 / 文字压条 —— 对齐错位的主要判据） --- */
    var cand = [];
    var pool = document.querySelectorAll('#stage *');
    for (var z = 0; z < pool.length; z++) {
      var e2 = pool[z];
      if (e2.children.length) continue;                       /* 只看叶子 */
      var cls = e2.className || '';
      var hasText = e2.textContent.trim().length > 0;
      var isBar = /(^|\s)(bar|bar-track|barv|segbar|track|hazard|stripe|band)(\s|$)/.test(cls);
      if (!hasText && !isBar) continue;
      var r2 = e2.getBoundingClientRect();
      if (r2.width < 1 || r2.height < 1) continue;
      cand.push({ el: e2, r: r2, cls: cls, slot: e2.getAttribute('data-slot') || '', txt: e2.textContent.trim() });
    }
    var ov = [];
    for (var a2 = 0; a2 < cand.length; a2++) {
      for (var b2 = a2 + 1; b2 < cand.length; b2++) {
        var A = cand[a2], B = cand[b2];
        var candA = A.cls, candB = B.cls;
        /* 「条」压在自己的「轨道」上是设计意图，跳过 */
        var isT = function (c) { return /(^|\s)bar-track(\s|$)/.test(c); };
        var isB = function (c) { return /(^|\s)bar(\s|$)/.test(c); };
        if ((isB(candA) && isT(candB)) || (isT(candA) && isB(candB))) continue;
        var ix = Math.min(A.r.right, B.r.right) - Math.max(A.r.left, B.r.left);
        var iy = Math.min(A.r.bottom, B.r.bottom) - Math.max(A.r.top, B.r.top);
        /* 文字 × 文字：基线框只要挨上就算撞（10px 字上下叠 2px，墨迹已经糊在一起了）。
           其他组合（条 / 装饰）留 2px 容差，避免贴边误报。 */
        var tol = (A.txt && B.txt) ? 0 : 2;
        if (ix > 2 && iy > tol) {
          var n1 = A.slot || A.txt || candA, n2 = B.slot || B.txt || candB;
          ov.push('"' + n1 + '" × "' + n2 + '" ' + Math.round(ix) + '×' + Math.round(iy));
        }
      }
    }
    if (ov.length) {
      fail('元素重叠 ' + ov.length + ' 处（文字压文字/压条）：' + ov.slice(0, 6).join('；')
           + (ov.length > 6 ? ' …' : ''));
    }

    /* --- 6) 字号下限：<10px 在 320×240 + RGB565 上会糊；中文更苛刻，<11px 笔画就粘连
       （实测：设备截图上 10px「温度」两字会糊成一团，同行的「TEMP」还很清楚） --- */
    var small = [], cjk = [];
    var pool2 = document.querySelectorAll('#stage *');
    for (var s2 = 0; s2 < pool2.length; s2++) {
      var e3 = pool2[s2];
      if (e3.children.length || !e3.textContent.trim()) continue;
      var fs = parseFloat(window.getComputedStyle(e3).fontSize);
      var nm = e3.getAttribute('data-slot') || e3.textContent.trim().slice(0, 6);
      if (fs < 10) {
        small.push(nm + '=' + fs + 'px');
      } else if (fs < 11 && /[\u4e00-\u9fff]/.test(e3.textContent)) {
        cjk.push(nm + '=' + fs + 'px');
      }
    }
    if (small.length) {
      out.warn.push('字号 <10px 有 ' + small.length + ' 处（RGB565 小屏易糊）：' + small.slice(0, 6).join('、'));
    }
    if (cjk.length) {
      out.warn.push('中文 10px 档有 ' + cjk.length + ' 处（汉字笔画会粘连，英文/数字同字号反而清楚，建议 ≥11px）：'
                    + cjk.slice(0, 8).join('、') + (cjk.length > 8 ? ' …' : ''));
    }

    /* --- 7) 文字对比度：暗底深字 / 亮底浅字都会糊（可读性判据）
       做法：取文字元素中心点，用 elementsFromPoint 拿该点的绘制栈，
       从画布底色往上按 alpha 逐层合成出「真实底色」，再算 WCAG 对比度。
       注：#img 若用 linear-gradient，background-color 是透明的，
          会回落到 body 背景 —— 这两种颜色在这些素材里本来就一致。 --- */
    function _lin(v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }
    function _lum(c) { return 0.2126 * _lin(c[0]) + 0.7152 * _lin(c[1]) + 0.0722 * _lin(c[2]); }
    function _rgb(s) {
      var m = /rgba?\(([^)]+)\)/.exec(s || '');
      if (!m) return null;
      var p = m[1].split(',');
      var o = [parseFloat(p[0]), parseFloat(p[1]), parseFloat(p[2])];
      if (isNaN(o[0]) || isNaN(o[1]) || isNaN(o[2])) return null;
      o.push(p.length > 3 ? parseFloat(p[3]) : 1);
      return o;
    }
    function _over(bg, acc) {           /* bg 叠在 acc 之上 */
      var a = bg[3];
      return [bg[0] * a + acc[0] * (1 - a), bg[1] * a + acc[1] * (1 - a), bg[2] * a + acc[2] * (1 - a)];
    }
    var lowc = [], softc = [], cmin = 99, cn = 0;
    var pool3 = document.querySelectorAll('#stage *');
    for (var t2 = 0; t2 < pool3.length; t2++) {
      var e4 = pool3[t2];
      if (e4.children.length || !e4.textContent.trim()) continue;
      var cs = window.getComputedStyle(e4);
      if (cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.05) continue;
      var r4 = e4.getBoundingClientRect();
      if (r4.width < 1 || r4.height < 1) continue;
      var cx = Math.round(r4.left + r4.width / 2), cy = Math.round(r4.top + r4.height / 2);
      if (cx < 0 || cy < 0 || cx >= 320 || cy >= 240) continue;
      var fg = _rgb(cs.color);
      if (!fg) continue;
      var acc = [255, 255, 255];                       /* 浏览器画布默认白 */
      var hbg = _rgb(window.getComputedStyle(document.documentElement).backgroundColor);
      var bbg = _rgb(window.getComputedStyle(document.body).backgroundColor);
      if (hbg && hbg[3] > 0.001) acc = _over(hbg, acc);
      if (bbg && bbg[3] > 0.001) acc = _over(bbg, acc);
      var stk = document.elementsFromPoint(cx, cy);
      for (var i2 = stk.length - 1; i2 >= 0; i2--) {   /* 栈尾=最底层，逐层往上叠 */
        var bgc = _rgb(window.getComputedStyle(stk[i2]).backgroundColor);
        if (bgc && bgc[3] > 0.001) acc = _over(bgc, acc);
        if (stk[i2] === e4) break;                     /* 合成到文字自己这层为止 */
      }
      var L1 = _lum([fg[0], fg[1], fg[2]]), L2 = _lum(acc);
      var cr = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
      /* 前景自身的 alpha 也要算：半透明文字等效于被底色冲淡 */
      if (fg[3] < 0.999) {
        var mixed = _over([fg[0], fg[1], fg[2], fg[3]], acc);
        L1 = _lum(mixed);
        cr = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
      }
      cn++;
      if (cr < cmin) cmin = cr;
      var tag = (e4.getAttribute('data-slot') || e4.textContent.trim().slice(0, 6))
                + '=' + cr.toFixed(1) + ':1';
      if (cr < 4.5) lowc.push(tag);
      else if (cr < 6.0) softc.push(tag);
    }
    out.contrastN = cn;
    out.contrastMin = cn ? Math.round(cmin * 10) / 10 : 0;
    if (lowc.length) {
      fail('对比度低于 4.5:1 有 ' + lowc.length + ' 处（暗底深字/亮底浅字，屏上基本看不清）：'
           + lowc.slice(0, 6).join('、') + (lowc.length > 6 ? ' …' : ''));
    }
    if (softc.length) {
      out.warn.push('对比度偏低（6:1 以下）有 ' + softc.length + ' 处：'
                    + softc.slice(0, 16).join('、') + (softc.length > 16 ? ' …' : ''));
    }

    /* --- 4) 逐个槽注入（含边界与越界值）不应抛错 --- */
    var names = [], all = document.querySelectorAll('[data-slot]');
    for (var i = 0; i < all.length; i++) {
      var n = all[i].getAttribute('data-slot');
      if (names.indexOf(n) < 0) names.push(n);
    }
    out.slotCount = names.length;
    var vals = ['0', '50', '100', '999'];
    for (var k = 0; k < names.length; k++) {
      for (var j = 0; j < vals.length; j++) {
        try { window.__setSlot(names[k], vals[j]); }
        catch (e) { fail('__setSlot("' + names[k] + '","' + vals[j] + '") 抛错: ' + e); }
      }
    }
  } catch (e) {
    fail('自检脚本自身抛错: ' + e);
  }
  var d = document.createElement('div');
  d.id = '__selftest__';
  /* 标记串拆开写：避免脚本源码自身被当成结果匹配到 */
  d.textContent = '@@RES' + 'ULT@@' + JSON.stringify(out) + '@@EN' + 'D@@';
  document.body.appendChild(d);
})();
</script>
"""


def runtime_check(path: str, edge: str, timeout=60, want=(320, 240)):
    res = {'fail': [], 'warn': [], 'info': []}
    html = open(path, encoding='utf-8').read()
    tmpdir = tempfile.mkdtemp(prefix='chkm_')
    try:
        tmp_html = os.path.join(tmpdir, 'check.html')
        with open(tmp_html, 'w', encoding='utf-8') as fh:
            fh.write(html.replace('</body>', SELFTEST_JS + '</body>') if '</body>' in html
                     else html + SELFTEST_JS)
        prof = os.path.join(tmpdir, 'prof')
        cmd = [edge, '--headless=new', '--disable-gpu', '--no-first-run',
               '--no-default-browser-check', '--disable-extensions',
               '--user-data-dir=' + prof, '--virtual-time-budget=2000',
               '--dump-dom', pathlib.Path(tmp_html).as_uri()]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=timeout)
        except subprocess.TimeoutExpired:
            res['fail'].append(f'B0 无头渲染超时（{timeout}s）')
            return res
        dom = r.stdout or ''
        m = re.search(r'@@RESULT@@(.*?)@@END@@', dom, re.S)
        if not m:
            tail = (r.stderr or '')[-400:]
            res['fail'].append('B0 没拿到自检结果（页面可能在脚本执行前就崩了）'
                               + (f'  stderr: {tail}' if tail else ''))
            return res
        data = json.loads(m.group(1))
        res['info'].append(f"B2 逐个注入 {data.get('slotCount', 0)} 个槽（含 0/50/100/999）")
        res['info'].append(f"B4 内容包围盒 {data.get('maxR')}x{data.get('maxB')}（画布 {want[0]}x{want[1]}）")
        if data.get('contrastN'):
            res['info'].append(f"B7 文字对比度 {data['contrastN']} 处，最低 {data.get('contrastMin')}:1"
                               f"（<4.5 判失败；<6 提示——320×240 RGB565 上细笔画会发虚）")
        for e in data.get('err', []):
            res['fail'].append('B ' + e)
        for w in data.get('warn', []):
            res['warn'].append('B ' + w)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return res


# ----------------------------------------------------------------- 主流程

def run_one(path: str, edge, want, do_render):
    s = static_check(path, want)
    out = {'file': s['file'], 'fail': list(s['fail']), 'warn': list(s['warn']),
           'info': list(s['info'])}
    if do_render:
        try:
            r = runtime_check(path, edge, want=want)
            out['fail'] += r['fail']
            out['warn'] += r['warn']
            out['info'] += r['info']
        except Exception as e:
            out['fail'].append(f'B0 运行期检查异常：{e}')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='素材自检（下发前挑出素材自身的 bug，不碰设备）')
    ap.add_argument('files', nargs='*', help='要检查的 html（默认配合 --all）')
    ap.add_argument('--all', action='store_true', help='检查 materials/ 下全部 .html')
    ap.add_argument('--size', default='320x240', help='期望尺寸，默认 320x240')
    ap.add_argument('--no-render', action='store_true', help='只做静态检查（不启浏览器）')
    ap.add_argument('--edge', default=None, help='Edge/Chrome 路径')
    ap.add_argument('--quiet', action='store_true', help='只打印失败项')
    a = ap.parse_args(argv)

    want = tuple(int(x) for x in a.size.lower().split('x'))
    files = list(a.files)
    if a.all:
        files += sorted(glob.glob(os.path.join(
            SKILL_DIR, 'assets', 'verified_materials', '*.html')))
    if not files:
        ap.error('没有指定文件（用 --all 或直接给路径）')

    edge = None
    if not a.no_render:
        edge = find_edge(a.edge)
        if not edge:
            print('!! 没找到 Edge/Chrome，退化为只做静态检查')
            a.no_render = True

    npass = nfail = 0
    for p in files:
        if not os.path.isfile(p):
            print(f'!! 文件不存在：{p}')
            nfail += 1
            continue
        r = run_one(p, edge, want, not a.no_render)
        bad = len(r['fail'])
        mark = 'PASS' if bad == 0 else 'FAIL'
        if bad:
            nfail += 1
        else:
            npass += 1
        print(f'[{mark}] {r["file"]}' + (f'  —— {bad} 个问题' if bad else ''))
        for e in r['fail']:
            print('    ✗ ' + e)
        if not a.quiet:
            for w in r['warn']:
                print('    ! ' + w)
            for i in r['info']:
                print('    · ' + i)

    print(f'\n合计：{npass} 通过 / {nfail} 失败（共 {len(files)} 个文件）')
    return 1 if nfail else 0


# SKILL-ONLY EXTENSION BEGIN —— 产物格式约束（A13 清单块 / --json / --emit-manifest）
#
# 这一整块是**技能专属**的：项目里的 tools/css_panel_test/check_material.py **没有**它。
# 基础实现（A1–A12 / B1–B7）由 scripts/sync_base.py 从项目刷新，刷新时按下面的
# BEGIN / END 标记把本块**原样保留** —— 所以可以放心重跑 sync_base.py。
#
# 目的：让「技能产物」对下游机器程序是可抓取的（详见 references/output_format.md）
#   1) 定义素材内嵌「产物清单」块 <script type="application/json" id="material-manifest">
#      的 schema，以及派生（build_manifest）/ 渲染（manifest_block）/ 解析（parse_manifest）；
#   2) A13：清单块必须存在、合法，且与素材实际槽位自洽（漏槽 / 多槽 / 字段不符 → FAIL）；
#   3) 命令行加 --json（机器可读报告）与 --emit-manifest（派生清单块，供粘贴）。
#
# 实现方式：只**包装**基础函数（static_check / run_one / main），不修改基础实现本身。
# ============================================================================

import contextlib as _ctx
import io as _io

MANIFEST_SCHEMA = 'rgb565-panel-material/1'
MANIFEST_ID = 'material-manifest'

# ---- `data-unit` 单位族（A14 用）----
# 同一族内可换算（注入脚本按倍数换算）；跨族不换算、原样透传。规范单位见 MONITOR_METRICS.md。
UNIT_CAPACITY    = ('B', 'KB', 'MB', 'GB', 'TB')
UNIT_RATE        = ('B/s', 'KB/s', 'MB/s', 'GB/s', 'KBps', 'MBps')
UNIT_TEMPERATURE = ('℃', '℉')
UNIT_POWER       = ('W',)                                    # 电脑功耗 W 就够用，不做 kW
UNIT_DURATION    = ('秒', '分', '小时', '天', 's', 'min', 'h', 'd')
UNIT_PASSTHROUGH = ('%', 'RPM', 'V', 'A', 'MHz', 'GHz')      # 声明型：不换算
UNIT_CONVERTIBLE = UNIT_CAPACITY + UNIT_RATE + UNIT_TEMPERATURE + UNIT_POWER + UNIT_DURATION
UNITS_OK = set(UNIT_CONVERTIBLE) | set(UNIT_PASSTHROUGH)


def unit_options(slot):
    """这个槽位**能声明哪些单位**（None = 不在表里，不校验）。

    例：`net1_down` 是速率 → 只能 B/s·KB/s·MB/s·GB/s；`cpu_load` 是占用率 → 只能 %。
    """
    if re.fullmatch(r'(cpu_load|gpu\d+_load|gpu\d+_mem_pct|mem_pct|disk\d+_pct|disk_all_pct)', slot):
        return ('%',)
    if re.fullmatch(r'fan\d+', slot):
        return ('RPM',)
    if re.fullmatch(r'(cpu_temp|gpu\d+_temp|disk\d+_temp)', slot):
        return UNIT_TEMPERATURE
    if re.fullmatch(r'(cpu_power|gpu\d+_power)', slot):
        return UNIT_POWER
    if slot == 'sys_uptime':
        return UNIT_DURATION
    if re.fullmatch(r'net\d+_(down|up)', slot):
        return UNIT_RATE
    if re.fullmatch(r'(mem_(used|total)|disk\d+_(used|total)|disk_all_(used|total)'
                    r'|gpu\d+_mem_(used|total)|net\d+_total_(down|up))', slot):
        return UNIT_CAPACITY
    return None


MANIFEST_RE = re.compile(
    r'<script[^>]*\bid\s*=\s*["\']' + MANIFEST_ID + r'["\'][^>]*>(.*?)</script>',
    re.S | re.I)
MANIFEST_TAG_RE = re.compile(
    r'<script([^>]*\bid\s*=\s*["\']' + MANIFEST_ID + r'["\'][^>]*)>', re.S | re.I)
_URL_RE = re.compile(r'url\(\s*["\']?([^"\')]+)["\']?\s*\)', re.I)

# 清单里允许出现、且**必须与素材实际属性一致**的字段（清单键名 → 素材上的 data-* 名）
MANIFEST_MIRROR = {
    'kind': 'data-kind', 'from': 'data-from', 'max': 'data-max',
    'warn': 'data-warn', 'danger': 'data-danger', 'fmt': 'data-fmt',
}


def _num(v):
    """'75' → 75（能整就整）；解析不了就原样返回。"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return int(f) if f == int(f) else f


def bg_kind(html: str) -> str:
    """背景底图类型：css（纯样式）/ local（本地相对路径）/ url（在线地址）。"""
    urls = _URL_RE.findall(html)
    if not urls:
        return 'css'
    return 'url' if any(u.lower().startswith(('http://', 'https://')) for u in urls) else 'local'


def build_manifest(path: str, want=DEFAULT_SIZE) -> dict:
    """从素材**派生**出机器可读清单（不靠手写，保证与素材一致）。"""
    html = open(path, encoding='utf-8').read()
    try:
        size = parse_size(html)
    except Exception:
        size = None
    size = [int(size[0]), int(size[1])] if size else [int(want[0]), int(want[1])]

    meta, order = {}, []
    for _tag, attrs in iter_tags(html):
        name = attrs.get('data-slot')
        if not name:
            continue
        if name not in meta:
            meta[name] = {'name': name, 'kind': 'text'}
            order.append(name)
        slot = meta[name]
        if attrs.get('data-kind'):
            slot['kind'] = attrs['data-kind']
        for key, attr in MANIFEST_MIRROR.items():
            if key != 'kind' and attrs.get(attr) is not None:
                slot[key] = _num(attrs[attr])
        if attrs.get('data-group') == '1':
            slot['group'] = True
        if attrs.get('data-suffix'):
            slot['unit'] = attrs['data-suffix'].strip()

    return {
        'schema': MANIFEST_SCHEMA,
        'name': os.path.splitext(os.path.basename(path))[0],
        'size': size,
        'background': bg_kind(html),
        'slots': [meta[n] for n in order],
    }


def manifest_block(manifest: dict) -> str:
    """清单 → 可直接粘贴进素材的 <script> 块。"""
    body = json.dumps(manifest, ensure_ascii=False, indent=2)
    return '<script type="application/json" id="%s">\n%s\n</script>' % (MANIFEST_ID, body)


def parse_manifest(html: str):
    """取清单块 → (dict 或 None, 错误说明 或 None)。"""
    m = MANIFEST_RE.search(html)
    if not m:
        return None, '没找到 <script type="application/json" id="%s"> 清单块' % MANIFEST_ID
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        return None, '清单块不是合法 JSON：%s' % e
    if not isinstance(data, dict):
        return None, '清单块顶层必须是 JSON 对象'
    return data, None


def _a13_manifest(path, want, res, html):
    """A13：清单块存在、合法，且与素材实际槽位自洽。"""
    mani, err = parse_manifest(html)
    if err:
        res['fail'].append('A13 ' + err + '（下游机器靠它抓取槽位，不能省）')
        return
    tag = MANIFEST_TAG_RE.search(html)
    if tag and not re.search(r'type\s*=\s*["\']application/json["\']', tag.group(1), re.I):
        res['fail'].append(
            'A13 清单块的 type 必须是 application/json —— 否则浏览器会**执行**它并报语法错')
    if mani.get('schema') != MANIFEST_SCHEMA:
        res['fail'].append(f"A13 清单 schema={mani.get('schema')!r} ≠ {MANIFEST_SCHEMA!r}")

    derived = build_manifest(path, want)          # 与素材实际一致的那一份（单一真源）
    # size 与**样式声明的尺寸**比，不与 --size 比 —— 后者是 A1 的事，在这里比会变成循环论证
    if list(mani.get('size') or []) != list(derived['size']):
        res['fail'].append(
            f"A13 清单 size={mani.get('size')} 与样式声明的 {derived['size']} 不符")

    bg_now, bg_decl = bg_kind(html), mani.get('background')
    if bg_decl is not None and bg_decl != bg_now:
        res['fail'].append(f"A13 清单 background={bg_decl!r} 与素材实际不符（实际 {bg_now!r}）")
    listed = mani.get('slots')
    if not isinstance(listed, list):
        res['fail'].append('A13 清单 slots 必须是数组')
        return
    want_slots = {s['name']: s for s in derived['slots']}
    named = {}
    for s in listed:
        if not isinstance(s, dict) or not s.get('name'):
            res['fail'].append(f'A13 清单里有条目缺 name：{s!r}')
            continue
        named[s['name']] = s
    for miss in sorted(set(want_slots) - set(named)):
        res['fail'].append(f'A13 清单漏了槽 "{miss}"（素材里有 data-slot）')
    for extra in sorted(set(named) - set(want_slots)):
        res['fail'].append(f'A13 清单多了槽 "{extra}"（素材里没有这个 data-slot）')
    for name in sorted(set(want_slots) & set(named)):
        d, m = want_slots[name], named[name]
        for key in MANIFEST_MIRROR:
            actual = d.get(key, 'text' if key == 'kind' else None)
            if key in m and m[key] != actual:
                res['fail'].append(
                    f'A13 槽 "{name}" 的 {key}={m[key]!r} 与素材实际 {actual!r} 不符')
        if 'unit' in m and m['unit'] != d.get('unit'):
            res['fail'].append(
                f'A13 槽 "{name}" 的 unit={m["unit"]!r} 与素材实际 {d.get("unit")!r} 不符')
    res['info'].append(
        f'A13 清单 schema={MANIFEST_SCHEMA} / background={bg_now} / 槽 {len(named)} 个')


# ---- 运行期自检的**尺寸参数化**（基础实现把画布写死成 320×240） ----
#
# 为什么必须补：技能宣称支持 320×240 / 320×170，但基础实现里的 SELFTEST_JS 把
# 画布边界、对比度取样范围都写死成 320×240 —— 换成别的尺寸就会**按错的画布判定**。
# 这里按 want 把 JS 模板重写一遍，保证「不同场景下都按真实画布判定」。

_BASE_SELFTEST_JS = SELFTEST_JS
_SIZED_JS = {}


def _sized_selftest(w, h):
    key = (int(w), int(h))
    if key not in _SIZED_JS:
        js = _BASE_SELFTEST_JS
        js = js.replace('maxR > 320.5 || maxB > 240.5',
                        'maxR > %g || maxB > %g' % (key[0] + 0.5, key[1] + 0.5))
        js = js.replace('应 <= 320x240', '应 <= %dx%d' % key)
        js = js.replace('cx >= 320 || cy >= 240', 'cx >= %d || cy >= %d' % key)
        js = js.replace('在 320×240 + RGB565', '在 %d×%d + RGB565' % key)
        _SIZED_JS[key] = js
    return _SIZED_JS[key]


_base_runtime_check = runtime_check


def _unescape(s):
    """`--dump-dom` 会把结果里的 < > & 转义；还原成可读文本（只影响报告文字）。"""
    return (s.replace('&lt;', '<').replace('&gt;', '>')
             .replace('&quot;', '"').replace('&#39;', "'").replace('&amp;', '&'))


def runtime_check(path, edge, timeout=60, want=DEFAULT_SIZE):
    w, h = int(want[0]), int(want[1])
    globals()['SELFTEST_JS'] = _sized_selftest(w, h)   # 基础实现按全局名取模板
    r = _base_runtime_check(path, edge, timeout=timeout, want=want)
    for k in ('fail', 'warn', 'info'):
        r[k] = [_unescape(s) for s in r[k]]
        if (w, h) != (320, 240):                       # 文案里的示例尺寸也换成真实画布
            r[k] = [s.replace('320×240', '%d×%d' % (w, h)) for s in r[k]]
    return r


# ---- 包装基础实现（只在运行期接管，不改基础文件本身） ----

_base_static_check = static_check


# ---- 交付形态：--mode local|online（A16–A19 只在线形态查）----
#
# 基础 main 不认 --mode，所以**先把它摘掉**再交给基础实现（否则参数解析会报错）。
# local（缺省）= 本地素材，数据由上位机注入；online = 托管出去的页面，页面自己取数。
_MODE = 'local'
_MODES = ('local', 'online')

_SECRET_RES = (
    (re.compile(r'\bsk-[A-Za-z0-9_\-]{8,}'), 'sk- 开头的密钥'),
    (re.compile(r'\bBearer\s+[A-Za-z0-9._\-]{12,}'), 'Bearer token'),
    (re.compile(r'''\bapi[_-]?key\s*[:=]\s*["'][^"']{8,}'''), 'api_key 明文'),
)
_EXT_REF_RE = re.compile(r'''(?:src|href)\s*=\s*["']([^"']+)["']''', re.I)
_DRIVE_RE = re.compile(r'(?<![\w])[A-Za-z]:[\\/]')
_SCHEME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9+.-]*:')


def _take_mode(argv):
    """摘掉 `--mode X` / `--mode=X`，返回剩余参数（顺带设置全局 _MODE）。"""
    global _MODE
    out, i = [], 0
    while i < len(argv):
        x = argv[i]
        if x == '--mode' or x.startswith('--mode='):
            if x == '--mode':
                if i + 1 >= len(argv):
                    raise ValueError('--mode 后面要跟 local 或 online')
                m = argv[i + 1]
                i += 2
            else:
                m = x.split('=', 1)[1]
                i += 1
            m = m.strip().lower()
            if m not in _MODES:
                raise ValueError('--mode 只支持 %s，收到 %r' % (' / '.join(_MODES), m))
            _MODE = m
            continue
        out.append(x)
        i += 1
    return out


def _a16_online(html, res):
    """A16–A19：在线形态（页面自己取数、可托管、失败可见、不越权）。"""
    # A16 自己取数
    has_fetch = re.search(r'\bfetch\s*\(', html) is not None
    has_port = ('__api' in html) or (re.search(r'\b8766\b', html) is not None)
    has_catch = re.search(r'\.catch\s*\(|\bcatch\s*\(', html) is not None
    if not has_fetch:
        res['fail'].append('A16 在线素材必须自己取数：没找到 fetch()'
                           '（app 不会给在线页面注入取数脚本）')
    elif not has_port:
        res['fail'].append('A16 没读 ?__api 也没写 8766：端口一变就取不到'
                           '（8766 被占时上位机会换端口）')
    else:
        res['info'].append('A16 页面自己取数：fetch() + 端口来源 ok')

    # A17 可托管
    refs = _EXT_REF_RE.findall(html) + _URL_RE.findall(html)
    bad = []
    # 只认**引用位置**的 file://（`src="file:///…"`、`url("file://…")`）；
    # 注释里提一句 `file://` 不算 —— 素材里常见「本地模式是 file://」这种说明。
    if re.search(r'''["'\'(]file://''', html, re.I):
        bad.append('出现 file:// 资源引用（托管后取不到本机文件）')
    if _DRIVE_RE.search(html):
        bad.append('出现盘符绝对路径（本机能开、托管后 404）')
    up = [r for r in refs if r.strip().startswith('../') or '/../' in r]
    if up:
        bad.append('资源用了 .. 越出站点根：%s' % '、'.join(up[:3]))
    for r in refs:
        r = r.strip()
        if not r or r.startswith('#') or r.startswith('data:') or r.startswith('//'):
            continue
        if _SCHEME_RE.match(r) and not re.match(r'https?://', r, re.I):
            bad.append('资源用了非 http(s) 协议：%s' % r)
    if bad:
        res['fail'].extend('A17 ' + b for b in bad)
    else:
        res['info'].append('A17 可托管：资源均为相对路径 / https / data:')

    # A18 失败可见（CSP 与兜底）
    m = re.search(r'<meta[^>]+http-equiv\s*=\s*["\']Content-Security-Policy["\'][^>]*>',
                  html, re.I)
    if m:
        tag = m.group(0)
        if 'connect-src' not in tag:
            res['warn'].append('A18 设了 CSP 但没有 connect-src，fetch 会被拦（画面永远不动）')
        elif not re.search(r'connect-src[^;]*(\*|127\.0\.0\.1|localhost|http:)', tag):
            res['warn'].append('A18 CSP 的 connect-src 没放行本机接口'
                               '（建议加 http://127.0.0.1:8766）')
    if not has_catch:
        res['warn'].append('A18 没有 catch 兜底：取不到数据时可能白屏 / 停止轮询')
    elif ('—' not in html) and ('离线' not in html):
        res['warn'].append('A18 有兜底但没看到「—」/「离线」：'
                           '失败时无法区分"没数据"和"页面坏了"')

    # A19 不越权
    for pat, what in _SECRET_RES:
        if pat.search(html):
            res['fail'].append('A19 页面里疑似有%s（在线页面是公开代码）' % what)
    for api in ('/app/show', '/app/quit'):
        if api in html:
            res['fail'].append('A19 页面调了控制接口 %s'
                               '（在线页面调用一律 403，不该依赖它）' % api)
    third = re.findall(r'<script[^>]+src\s*=\s*["\']https?://[^"\']+', html, re.I)
    if third:
        res['warn'].append('A19 引用了 %d 个外部脚本：在线页面等于公开代码，确认来源可信'
                           % len(third))


def static_check(path, want=DEFAULT_SIZE):
    res = _base_static_check(path, want)
    html = open(path, encoding='utf-8').read()
    try:
        _a13_manifest(path, want, res, html)
    except Exception as e:
        res['fail'].append(f'A13 清单检查异常：{e}')
    try:
        _a14_unit(html, res)
    except Exception as e:
        res['fail'].append(f'A14 单位声明检查异常：{e}')
    if _MODE == 'online':
        try:
            _a16_online(html, res)
        except Exception as e:
            res['fail'].append(f'A16–A19 在线形态检查异常：{e}')
    return res


def _a14_unit(html, res):
    """A14：`data-unit` 声明合法、与 `data-suffix` 显示一致、槽位对得上，且**同槽只有一种单位**。"""
    bad, n, per_slot = [], 0, {}
    for m in re.finditer(r'<[a-zA-Z][^>]*\bdata-unit\s*=\s*["\']([^"\']*)["\'][^>]*>', html):
        tag, unit = m.group(0), m.group(1).strip()
        n += 1
        if unit not in UNITS_OK:
            bad.append(f'data-unit={unit!r} 不是允许的单位（可换算：{" ".join(UNIT_CONVERTIBLE)}）')
            continue
        ms = re.search(r'data-suffix\s*=\s*["\']([^"\']*)["\']', tag)
        if ms and ms.group(1).strip() != unit:
            bad.append(f'data-unit={unit!r} 与 data-suffix={ms.group(1)!r} 不一致')
            continue
        # 槽位 ↔ 单位对不对得上（例：cpu_load 只能 %，给它声明 GB 会被拦下）
        sm = re.search(r'data-slot\s*=\s*["\']([^"\']*)["\']', tag)
        if sm:
            slot = sm.group(1).strip()
            opts = unit_options(slot)
            if opts and unit not in opts:
                bad.append(f'槽 {slot} 不能用 {unit!r}（可用：{" / ".join(opts)}）')
            elif opts:
                per_slot.setdefault(slot, unit)
                if per_slot[slot] != unit:
                    bad.append(f'槽 {slot} 声明了两种单位（{per_slot[slot]!r} 与 {unit!r}）'
                               f'—— 一个槽只能一种，注入按槽广播值')
    if bad:
        res['fail'].extend('A14 ' + b for b in bad)
    elif n:
        res['info'].append(f'A14 单位声明 {n} 处（合法、与后缀一致、槽位对得上、单槽单单位）')


_COLLECTED = []

_base_run_one = run_one


def _downgrade_online_b(res):
    """在线形态：页面自己取数，不实现 `__setSlot` 是合法的 → B 层这两类失败降级为 WARN。

    其余 B 层判据（残留占位符 / 包围盒 / 重叠 / 字号 / 对比度）照旧是 FAIL。
    """
    keep = []
    for f in res['fail']:
        if f.startswith('B') and ('__setSlot 未定义' in f or '__setSlot(' in f):
            res['warn'].append(f + '（在线形态允许页面不自实现 __setSlot）')
        else:
            keep.append(f)
    res['fail'] = keep


def run_one(path, edge, want, do_render):
    r = _base_run_one(path, edge, want, do_render)
    r['path'] = os.path.abspath(path)
    if _MODE == 'online':
        _downgrade_online_b(r)
    r['status'] = 'FAIL' if r['fail'] else 'PASS'
    _COLLECTED.append(r)
    return r


_base_main = main

_OPTS_WITH_VALUE = ('--size', '--edge')


def _wanted_files(argv):
    """按与基础实现相同的规则算出「这次要检查哪些文件」+ 期望尺寸。"""
    files, do_all, size = [], False, '320x240'
    i = 0
    while i < len(argv):
        x = argv[i]
        if x == '--all':
            do_all = True
        elif x.startswith('--size='):
            size = x.split('=', 1)[1]
        elif x in _OPTS_WITH_VALUE:
            if i + 1 < len(argv):
                if x == '--size':
                    size = argv[i + 1]
                i += 1
        elif not x.startswith('-'):
            files.append(x)
        i += 1
    if do_all:
        files += sorted(glob.glob(os.path.join(
            SKILL_DIR, 'assets', 'verified_materials', '*.html')))
    return files, tuple(int(v) for v in size.lower().split('x'))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    # --mode：先摘掉（基础 main 的 argparse 不认识它）
    try:
        argv = _take_mode(argv)
    except ValueError as e:
        print(f'!! {e}', file=sys.stderr)
        return 2

    # --emit-manifest：只派生并打印清单块（生成方粘贴用），不做检查
    if '--emit-manifest' in argv:
        files, want = _wanted_files([x for x in argv if x != '--emit-manifest'])
        if not files:
            print('!! --emit-manifest 需要给一个 html 文件（或用 --all）', file=sys.stderr)
            return 2
        rc = 0
        for p in files:
            if not os.path.isfile(p):
                print(f'!! 文件不存在：{p}', file=sys.stderr)
                rc = 1
                continue
            print(manifest_block(build_manifest(p, want)))
        return rc

    # --json：报告以机器可读 JSON 输出（人读输出被吞掉，只留 JSON）
    if '--json' in argv:
        argv = [x for x in argv if x != '--json']
        files, want = _wanted_files(argv)
        del _COLLECTED[:]
        with _ctx.redirect_stdout(_io.StringIO()):
            rc = _base_main(argv)
        got = {r['path']: r for r in _COLLECTED}
        results = []
        for p in files:
            r = got.get(os.path.abspath(p))
            if r is None:
                r = {'file': os.path.basename(p), 'path': os.path.abspath(p),
                     'status': 'FAIL', 'fail': [f'文件不存在：{p}'], 'warn': [], 'info': []}
            results.append(r)
        npass = sum(1 for r in results if r['status'] == 'PASS')
        print(json.dumps({
            'schema': 'rgb565-material-check/1',
            'size': f'{want[0]}x{want[1]}',
            'mode': _MODE,
            'total': len(results), 'pass': npass, 'fail': len(results) - npass,
            'files_with_warn': sum(1 for r in results if r['warn'] and r['status'] == 'PASS'),
            'results': results,
        }, ensure_ascii=False, indent=2))
        return rc

    return _base_main(argv)


# SKILL-ONLY EXTENSION END


if __name__ == '__main__':
    sys.exit(main())
