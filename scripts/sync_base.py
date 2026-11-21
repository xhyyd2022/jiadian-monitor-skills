#!/usr/bin/env python
# -*- coding: utf-8 -*-
# <!--module
# id: sync-base
# title: 基线同步
# owns: 从项目刷新检查器基础部分 · 按标记保留技能专属扩展
# not_owns: 技能专属扩展的内容 · 能力的定义与边界 · 主项目链路 · 素材的形态契约 · 检查项与判据 · 机器可读格式 · 风格取舍
# rendering: 不渲染；只维护工具，刷新后判据仍按 W×H 参数化
# see: references/self_check_gates.md
# -->
"""从项目实现刷新技能的**基础部分**（技能专属扩展原样保留）。

为什么需要它
------------
技能必须能**独立拿走**：丢到任何目录、任何机器上都能跑。但自检脚本的基础逻辑
（A1–A12 / B1–B7）来自项目里的 `tools/css_panel_test/check_material.py`，手抄必然漂移
（本项目已经吃过两次文档漂移的亏）。所以：**以项目实现为源**，跑一次本脚本刷新。

它只动**基础部分**，两处技能专属内容会被保留：

1. `scripts/check_material.py` 末尾 `SKILL-ONLY EXTENSION BEGIN/END` 之间的整块
   （产物格式约束：A13 / `--json` / `--emit-manifest`）—— 原样搬过去；
2. `assets/verified_materials/*.html` 里的「产物清单」块 —— 复制完素材后**重新派生**一遍，
   所以清单永远与素材内容一致。

用法
----
    python scripts/sync_base.py                       # 自动推断项目目录
    python scripts/sync_base.py --project <项目目录>   # 显式指定
    python scripts/sync_base.py --check               # 只比对，不写盘
"""

from __future__ import annotations

import argparse
import importlib
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))       # .../scripts
SKILL_DIR = os.path.dirname(HERE)                       # 技能根目录

BEGIN = '# SKILL-ONLY EXTENSION BEGIN'
END = '# SKILL-ONLY EXTENSION END'
MAIN_GUARD = "if __name__ == '__main__':"

# 技能里需要的、从项目实现中「切片」出来的片段（按定义顺序）
SLICE_FUNCS = [
    ("webview_render.py", r"(^_EDGE = \[.*?\n\]\n)"),          # 候选浏览器路径表
    ("webview_render.py", r"(^def find_edge\(.*?)(?=^def )"),  # 找 Edge / Chrome
    ("webview_render.py", r"(^def parse_size\(.*?)(?=^def )"),  # 从样式里推断 W×H
]

HEADER = '''#!/usr/bin/env python
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
'''


def find_project(explicit=None):
    """定位项目里的 tools/css_panel_test（含 check_material.py + webview_render.py）。"""
    cands = []
    if explicit:
        cands.append(os.path.abspath(explicit))
    cands.append(os.path.abspath(os.path.join(SKILL_DIR, '..', '..', 'tools', 'css_panel_test')))
    for c in cands:
        if (os.path.isfile(os.path.join(c, 'check_material.py'))
                and os.path.isfile(os.path.join(c, 'webview_render.py'))):
            return c
    raise SystemExit(
        '找不到项目目录（需要含 check_material.py + webview_render.py）。\n'
        '用 --project <项目目录> 指定，例如：\n'
        '    python scripts/sync_base.py --project D:/your/project/tools/css_panel_test')


def read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def build_base(project):
    """生成自包含的基础部分（不含技能专属扩展）。"""
    src = read(os.path.join(project, 'check_material.py'))

    chunks = []
    for fname, pat in SLICE_FUNCS:
        m = re.search(pat, read(os.path.join(project, fname)), re.S | re.M)
        if not m:
            raise SystemExit('切不出来：%s → %s（项目源可能改过了）' % (fname, pat))
        chunks.append(m.group(1).rstrip() + '\n')
    inlined = '\n'.join(chunks)

    body = src[src.index('from __future__ import annotations'):]

    old_imp = (
        "HERE = os.path.dirname(os.path.abspath(__file__))\n"
        "sys.path.insert(0, HERE)\n"
        "import webview_render as wr  # noqa: E402  （复用 find_edge / parse_size）\n"
    )
    if old_imp not in body:
        raise SystemExit('没找到 import webview_render 那三行，项目源可能改过了')
    here_defs = (
        "# 技能内的目录（自包含：不依赖项目路径）\n"
        "HERE = os.path.dirname(os.path.abspath(__file__))   # .../scripts\n"
        "SKILL_DIR = os.path.dirname(HERE)                   # 技能根目录\n\n"
        "# Windows 控制台默认是 GBK：报告里的 ✗ / ★ 等符号一旦打印就会抛\n"
        "# UnicodeEncodeError，让「有 FAIL」变成整份报告崩掉。这里统一把 stdout\n"
        "# 改成 UTF-8 + errors=replace —— 不改检查逻辑，只修输出。\n"
        "try:\n"
        "    sys.stdout.reconfigure(encoding='utf-8', errors='replace')\n"
        "except Exception:\n"
        "    pass\n\n"
    )
    body = body.replace(old_imp, here_defs + inlined + '\n')
    body = body.replace('wr.parse_size(', 'parse_size(').replace('wr.find_edge(', 'find_edge(')
    if 'wr.' in body:
        raise SystemExit('还有没替换掉的 wr. 调用，请检查项目源')

    old_all = "files += sorted(glob.glob(os.path.join(HERE, 'materials', '*.html')))"
    new_all = ("files += sorted(glob.glob(os.path.join(\n"
               "            SKILL_DIR, 'assets', 'verified_materials', '*.html')))")
    if old_all not in body:
        raise SystemExit("没找到 --all 的扫描目录那行，项目源可能改过了")
    body = body.replace(old_all, new_all)

    return HEADER + '\n' + body


def extract_extension(text, where):
    """取出 SKILL-ONLY 块（含两行标记）。取不到就报错 —— 宁可停下也不冲掉它。"""
    i = text.find(BEGIN)
    j = text.find(END)
    if i < 0 or j < 0:
        raise SystemExit(
            f'在 {where} 里找不到 {BEGIN} / {END} 标记。\n'
            '技能专属扩展靠这对标记保命，标记丢了就不能安全刷新基础部分 —— 请先补回标记。')
    return text[i:text.index('\n', j) + 1]


def compose(base, extension):
    """基础 + 技能专属扩展 + __main__ 收尾。"""
    head, tail = base.rsplit(MAIN_GUARD, 1)
    return head.rstrip('\n') + '\n\n\n' + extension + '\n\n' + MAIN_GUARD + tail


def sync_materials(project, dry=False):
    """复制项目素材 → 技能，然后**重新派生**清单块（保证与素材一致）。"""
    src_dir = os.path.join(project, 'materials')
    dst_dir = os.path.join(SKILL_DIR, 'assets', 'verified_materials')
    os.makedirs(dst_dir, exist_ok=True)
    copied = []
    for name in sorted(os.listdir(src_dir)):
        if not re.fullmatch(r'p\d+_[a-z_]+\.html', name):
            continue
        if not dry:
            shutil.copy2(os.path.join(src_dir, name), os.path.join(dst_dir, name))
        copied.append(os.path.join(dst_dir, name))
    return copied


def main(argv=None):
    ap = argparse.ArgumentParser(description='从项目刷新技能的基础部分（保留技能专属扩展）')
    ap.add_argument('--project', default=None, help='项目目录（含 check_material.py）')
    ap.add_argument('--check', action='store_true', help='只比对，不写盘')
    a = ap.parse_args(argv)

    project = find_project(a.project)
    target = os.path.join(HERE, 'check_material.py')

    base = build_base(project)
    ext = extract_extension(read(target), target)
    new = compose(base, ext)

    changed = new != read(target)
    print('项目目录 : %s' % project)
    print('自检脚本 : %s（%d 字符，%s）'
          % (target, len(new), '需更新' if changed else '已是最新'))
    if a.check:
        return 1 if changed else 0

    if changed:
        with open(target, 'w', encoding='utf-8', newline='') as fh:
            fh.write(new)

    # 素材：复制后再刷新清单块
    copied = sync_materials(project, dry=a.check)
    sys.path.insert(0, HERE)
    importlib.invalidate_caches()
    sys.modules.pop('check_material', None)
    sys.modules.pop('add_manifest', None)
    add_manifest = importlib.import_module('add_manifest')
    states = {}
    for p in copied:
        s = add_manifest.apply_one(p)
        states[s] = states.get(s, 0) + 1
    print('参考素材 : %d 套 → %s（清单 %s）'
          % (len(copied), os.path.join(SKILL_DIR, 'assets', 'verified_materials'),
             ' / '.join('%s %d' % (k, v) for k, v in sorted(states.items()))))
    print('提醒     : SKILL.md / references / assets/material_prompt.md 需手工维护（本脚本不动）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
