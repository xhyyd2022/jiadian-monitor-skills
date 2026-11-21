#!/usr/bin/env python
# -*- coding: utf-8 -*-
# <!--module
# id: add-manifest
# title: 清单块回填
# owns: 产物清单块的派生与幂等写入
# not_owns: 能力的定义与边界 · 主项目链路 · 素材的形态契约 · 检查项与判据 · 机器可读格式 · 风格取舍
# rendering: 不渲染；只保证清单块落在 #stage 之外、不参与画面
# see: references/output_format.md
# -->
"""给素材回填 / 刷新「产物清单」块（<script type="application/json" id="material-manifest">）。

清单是从素材**派生**的（不手写，所以不会与素材漂移），本脚本只是把
`check_material.py --emit-manifest` 的结果**自动插到 `</body>` 之前**：

    python scripts/add_manifest.py my.html        # 就地回填 / 刷新（幂等）
    python scripts/add_manifest.py --all          # 技能自带的 16 套参考素材
    python scripts/add_manifest.py --all --check  # 只报哪些缺清单，不改文件

清单块的格式约束见 references/output_format.md。
**注意**：新素材应当在生成时就带上清单块；本脚本是给「已有素材」补票用的。
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from check_material import (  # noqa: E402
    DEFAULT_SIZE, MANIFEST_RE, build_manifest, manifest_block)

BODY_END_RE = re.compile(r'(\s*</body>)', re.I)


def apply_one(path: str, want=DEFAULT_SIZE) -> str:
    """回填 / 刷新一份素材，返回 'added' | 'refreshed'。"""
    html = open(path, encoding='utf-8').read()
    block = manifest_block(build_manifest(path, want))

    if MANIFEST_RE.search(html):
        new = MANIFEST_RE.sub(lambda _m: block, html, count=1)
        state = 'refreshed'
    elif BODY_END_RE.search(html):
        new = BODY_END_RE.sub(lambda m: '\n' + block + m.group(1), html, count=1)
        state = 'added'
    else:                                   # 没有 </body>：退化为追加到末尾
        new = html.rstrip() + '\n' + block + '\n'
        state = 'added'

    if new != html:
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            fh.write(new)
    return state


def main(argv=None):
    ap = argparse.ArgumentParser(description='回填 / 刷新素材的产物清单块')
    ap.add_argument('files', nargs='*', help='要处理的 html')
    ap.add_argument('--all', action='store_true', help='处理技能自带的参考素材')
    ap.add_argument('--size', default='320x240', help='期望尺寸，默认 320x240')
    ap.add_argument('--check', action='store_true', help='只报缺清单的文件，不写盘')
    a = ap.parse_args(argv)

    want = tuple(int(x) for x in a.size.lower().split('x'))
    files = list(a.files)
    if a.all:
        files += sorted(glob.glob(os.path.join(
            SKILL_DIR, 'assets', 'verified_materials', '*.html')))
    if not files:
        ap.error('没有指定文件（用 --all 或直接给路径）')

    rc = 0
    for p in files:
        if not os.path.isfile(p):
            print(f'!! 文件不存在：{p}')
            rc = 1
            continue
        if a.check:
            missing = not MANIFEST_RE.search(open(p, encoding='utf-8').read())
            print(f'[{"缺清单" if missing else "有清单"}] {os.path.basename(p)}')
            if missing:
                rc = 1
            continue
        print(f'[{apply_one(p, want)}] {os.path.basename(p)}')
    return rc


if __name__ == '__main__':
    sys.exit(main())
