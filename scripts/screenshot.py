#!/usr/bin/env python
# -*- coding: utf-8 -*-
# <!--module
# id: screenshot
# title: 自截图（给有视觉能力的模型自检用）
# owns: 把素材 / 在线页面渲染成 PNG 供模型自己看 · 截图参数（尺寸、缩放、等待、URL 参数）
# not_owns: 检查项与判据 · 素材的形态契约 · 机器可读格式 · 主项目链路 · 托管方式
# rendering: 截图按调用方声明的 W×H 出图（--size 传什么就是什么画布），不代替 A/B 层判据
# see: references/self_check_gates.md
# -->
"""把素材渲染成 PNG —— 给**有视觉能力的模型**自己看一眼用。

为什么单独一个脚本：机器判据只覆盖「坐标级」问题（越界 / 重叠 / 字号 / 对比度 / 清单自洽），
**"坐标都对但看着别扭"只能看**。有视觉的模型（能读图）应该自己截图、自己看、自己改，
而不是把闸门 4 甩给人。

用法：

    python scripts/screenshot.py a.html                      # 单张 → out/a.png
    python scripts/screenshot.py --all                       # 全部参考素材
    python scripts/screenshot.py a.html --size 320x170       # V1P 尺寸
    python scripts/screenshot.py --url https://x/p.html      # 在线页面（托管后的地址）
    python scripts/screenshot.py a.html --scale 2            # 2 倍图（小字更清楚）
    python scripts/screenshot.py a.html --param cpu_load=57  # 传 URL 参数模拟数据
    python scripts/screenshot.py a.html --print-cmd          # 只打印命令，不跑浏览器

约定：

- 出图目录默认 `out/`（相对当前目录），可用 `--out` 改。
- 截图**不注入数据**（与闸门一致）→ 看到的是默认值；想验某个数值就用 `--param`。
- 本脚本**只出图、不判分**；判分仍是 `check_material.py`。
"""

from __future__ import annotations

import argparse
import glob
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
DEFAULT_SIZE = (320, 240)
MATERIALS = os.path.join(SKILL_DIR, 'assets', 'verified_materials')

EDGE_CANDIDATES = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]


def find_edge(explicit=None):
    """找 Edge / Chrome；找不到返回 None（调用方给出可执行的提示）。"""
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    for p in EDGE_CANDIDATES:
        if os.path.isfile(p):
            return p
    for name in ('msedge', 'chrome'):
        p = shutil.which(name)
        if p:
            return p
    return None


def parse_size(text):
    try:
        w, h = text.lower().split('x')
        return int(w), int(h)
    except Exception:
        raise SystemExit(f'!! --size 要写成 宽x高（例 320x240），收到 {text!r}')


def build_cmd(edge, target_uri, out_png, size, scale, wait_ms, prof):
    w, h = size
    return [
        edge,
        '--headless=new',
        '--disable-gpu',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-extensions',
        '--hide-scrollbars',
        '--mute-audio',
        f'--force-device-scale-factor={scale}',
        f'--window-size={w},{h}',
        f'--user-data-dir={prof}',
        f'--virtual-time-budget={wait_ms}',
        f'--screenshot={out_png}',
        target_uri,
    ]


def shoot(edge, target, out_png, size, scale, wait_ms, params, print_cmd=False):
    """截一张图，返回 (ok, 说明)。target 是本地文件路径或 http(s) URL。"""
    if os.path.isfile(target):
        uri = pathlib.Path(os.path.abspath(target)).as_uri()
    elif target.lower().startswith(('http://', 'https://', 'file://')):
        uri = target
    else:
        return False, f'既不是文件也不是 URL：{target}'

    if params:
        sep = '&' if ('?' in uri) else '?'
        uri = uri + sep + '&'.join(params)

    tmpdir = tempfile.mkdtemp(prefix='shot_')
    prof = os.path.join(tmpdir, 'prof')
    os.makedirs(out_png and os.path.dirname(os.path.abspath(out_png)) or '.', exist_ok=True)
    cmd = build_cmd(edge, uri, os.path.abspath(out_png), size, scale, wait_ms, prof)
    try:
        if print_cmd:
            print(' '.join(cmd))
            return True, '（--print-cmd，未执行）'
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=90)
        if not os.path.isfile(out_png):
            tail = ((r.stderr or '') + (r.stdout or ''))[-300:]
            return False, f'没生成 PNG（浏览器可能没跑起来）{("  " + tail.strip()) if tail else ""}'
        return True, out_png
    except subprocess.TimeoutExpired:
        return False, '截图超时（90s）'
    except OSError as e:
        return False, f'启动浏览器失败：{e}'
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='screenshot.py',
        description='把素材 / 在线页面渲染成 PNG（给有视觉能力的模型自己看）')
    ap.add_argument('files', nargs='*', help='html 文件（可多个）')
    ap.add_argument('--all', action='store_true', help='assets/verified_materials/*.html 全截')
    ap.add_argument('--url', action='append', default=[], help='在线页面地址（可多次给）')
    ap.add_argument('--size', default='320x240', help='画布尺寸，默认 320x240（V1P 用 320x170）')
    ap.add_argument('--scale', type=int, default=1, help='设备像素比，默认 1；看小字用 2')
    ap.add_argument('--wait', type=int, default=1500, help='虚拟时间预算 ms，默认 1500')
    ap.add_argument('--param', action='append', default=[], help='追加 URL 参数，如 cpu_load=57')
    ap.add_argument('--out', default='out', help='出图目录，默认 out/')
    ap.add_argument('--edge', default=None, help='浏览器可执行文件路径（默认自动找 Edge/Chrome）')
    ap.add_argument('--print-cmd', action='store_true', help='只打印命令，不执行')
    a = ap.parse_args(argv)

    size = parse_size(a.size)
    targets = list(a.files) + list(a.url)
    if a.all:
        targets += sorted(glob.glob(os.path.join(MATERIALS, '*.html')))
    if not targets:
        ap.print_help()
        return 2

    edge = find_edge(a.edge)
    if not edge:
        print('!! 找不到 Edge / Chrome：装一个，或用 --edge 指路径', file=sys.stderr)
        return 2

    os.makedirs(a.out, exist_ok=True)
    ok_n = 0
    for t in targets:
        stem = os.path.splitext(os.path.basename(t.rstrip('/\\')))[0] or 'page'
        suffix = f'_{size[0]}x{size[1]}' if size != DEFAULT_SIZE else ''
        out_png = os.path.join(a.out, f'{stem}{suffix}.png')
        ok, msg = shoot(edge, t, out_png, size, a.scale, a.wait, a.param, a.print_cmd)
        if ok:
            ok_n += 1
            print(f'[OK] {os.path.basename(t)} → {msg}')
        else:
            print(f'[!!] {os.path.basename(t)}：{msg}')
    print(f'\n合计：{ok_n} / {len(targets)} 张')
    if ok_n and not a.print_cmd:
        print('接下来：用看图能力逐条过闸门 4（主题 / 数据来源 / 中英混用 / 多样性 / 层级），'
              '别只看坐标对不对。')
    return 0 if ok_n == len(targets) else 1


if __name__ == '__main__':
    sys.exit(main())
