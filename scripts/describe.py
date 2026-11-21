#!/usr/bin/env python
# -*- coding: utf-8 -*-
# <!--module
# id: describe
# title: 描述聚合与边界校验
# owns: 描述块的聚合与机器可读输出 · 职责边界校验（D1–D4）
# not_owns: 各模块职责的内容（各模块自己写） · 能力的定义与边界 · 主项目链路 · 素材的形态契约 · 检查项与判据 · 机器可读格式 · 风格取舍
# rendering: 元工具，不渲染；只校验每个模块都声明了自己的 rendering 判据
# see: references/capability.md
# -->
"""描述功能的**实现**：聚合各模块自带的描述块，并校验职责边界。

设计（对应「每个模块各自配备一份描述文档，由该文档负责说明并实现描述功能」）
--------------------------------------------------------------------------
描述**不集中写在一个地方**，而是**写在每个模块自己的文档里**：文档开头一个
机器可读的描述块，声明这个模块 `owns`（负责什么）/ `not_owns`（不负责什么，
并指向该由谁负责）/ `rendering`（满足约束渲染条件的判据）。

本脚本负责把散落的描述块**聚合成一份机器可读描述**，并**校验边界**：

    python scripts/describe.py --json     # 机器可读（下游程序抓这个）
    python scripts/describe.py --md       # 人读索引表
    python scripts/describe.py --check    # 校验边界（D1–D4），有冲突退出码 1

描述块的写法（HTML 注释，渲染 markdown 时不可见；脚本里写在**文件最前面**）：

    <!--module
    id: demo
    title: 示例模块
    owns: 示例职责甲 · 示例职责乙
    not_owns: 检查项与判据 · 机器可读格式
    rendering: 示例判据（按调用方声明的 W×H 判定）
    see: references/output_format.md
    -->

多值字段用 `·` 分隔（也兼容 ASCII `,`；**全角 `，` 不算分隔符**，它只是中文句读）。
**边界靠 D3 强制**：同一条 `owns` 不许出现在两个模块里。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)

SCHEMA = 'rgb565-panel-describe/1'
BLOCK_RE = re.compile(r'<!--\s*module\b(.*?)-->', re.S | re.I)
FIELDS = ('id', 'title', 'owns', 'not_owns', 'rendering', 'see')
MULTI = ('owns', 'not_owns', 'rendering', 'see')
# 多值分隔符：`·` 为主，兼容 **ASCII** `,`（see 里常写逗号）。
# 注意：**全角 `，` 不作分隔符** —— 它只是中文句读，不然一句带逗号的话会被误拆成多条。
SEP_RE = re.compile(r'[·,]')
# 脚本里描述块写在注释中（`# <!--module ... -->`）；剥掉行首注释标记再解析
LEAD_RE = re.compile(r'^\s*(?:#+|\*+|//+)?\s*')

# 扫描哪些文件找描述块（技能根目录相对路径）
#   · 文档：`<!--module ... -->` HTML 注释
#   · 脚本：同样内容写在 Python 注释里（`# <!--module ... -->`）—— 格式统一，一套解析
SCAN = [
    'SKILL.md',
    'references/capability.md',
    'references/project.md',
    'references/api_map.md',
    'references/metrics.md',
    'references/contract.md',
    'references/online_hosting.md',
    'references/output_format.md',
    'references/self_check_gates.md',
    'references/style_catalog.md',
    'references/maintenance.md',
    'assets/material_prompt.md',
    'assets/verified_materials/README.md',
    'scripts/check_material.py',
    'scripts/add_manifest.py',
    'scripts/sync_base.py',
    'scripts/describe.py',
    'scripts/screenshot.py',
]


def parse_block(text, where):
    """取出**第一个**描述块 → dict；没有块返回 None。

    脚本文件里描述块必须写在**文件最前面**（在模块 docstring 之前），
    否则 docstring 里若出现示例块会被当成该模块自己的描述。
    """
    m = BLOCK_RE.search(text)
    if not m:
        return None
    out = {'doc': where}
    for line in m.group(1).splitlines():
        line = LEAD_RE.sub('', line).strip()
        if not line or ':' not in line:
            continue
        key, val = line.split(':', 1)
        key, val = key.strip().lower(), val.strip()
        if key in MULTI:
            out[key] = [x.strip() for x in SEP_RE.split(val) if x.strip()]
        else:
            out[key] = val
    return out


def collect():
    mods = []
    for rel in SCAN:
        p = os.path.join(SKILL_DIR, rel)
        if not os.path.isfile(p):
            mods.append({'_missing': rel})
            continue
        with open(p, encoding='utf-8') as fh:
            b = parse_block(fh.read(), rel)
        mods.append(b if b else {'_noblock': rel})
    return mods


def check(mods):
    """D1–D4 边界校验，返回 [(级别, 说明)]。"""
    out = []
    seen_ids, owner_of = {}, {}

    for m in mods:
        if '_missing' in m:
            out.append(('FAIL', f"D1 描述块所在文件不存在：{m['_missing']}"))
            continue
        if '_noblock' in m:
            out.append(('FAIL', f"D1 {m['_noblock']} 里没有 <!--module ...--> 描述块"))
            continue
        mid = m.get('id')
        if not mid:
            out.append(('FAIL', f"D1 {m['doc']} 的描述块缺 id"))
        elif mid in seen_ids:
            out.append(('FAIL', f"D1 模块 id 重复：{mid}（{seen_ids[mid]} 与 {m['doc']}）"))
        else:
            seen_ids[mid] = m['doc']
        for f in ('owns', 'not_owns', 'rendering'):
            if not m.get(f):
                out.append(('FAIL', f"D2 {m['doc']}（{mid}）的描述块缺 {f}（三项都必须写）"))
        for item in m.get('owns', []):
            if item in owner_of and owner_of[item] != mid:
                out.append(('FAIL', f"D3 职责重叠：{item!r} 同时写在 {owner_of[item]} 与 {mid}"))
            else:
                owner_of[item] = mid
        for rel in m.get('see', []):
            if not os.path.exists(os.path.join(SKILL_DIR, rel)):
                out.append(('FAIL', f"D4 {mid} 的 see 指向不存在的文件：{rel}"))

    ids = [m.get('id') for m in mods if 'id' in m]
    if len(ids) != len(set(ids)):
        pass                                    # 上面已逐条报过
    if not out:
        out.append(('OK', f"D1–D4 全过：{len(ids)} 个模块，职责互不重叠，see 全部可达"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='聚合模块描述 + 校验职责边界')
    ap.add_argument('--json', action='store_true', help='机器可读描述')
    ap.add_argument('--md', action='store_true', help='人读索引表')
    ap.add_argument('--check', action='store_true', help='校验边界（D1–D4）')
    a = ap.parse_args(argv)
    if not (a.json or a.md or a.check):
        a.check = True

    mods = collect()
    good = [m for m in mods if 'id' in m]

    if a.json:
        print(json.dumps({
            'schema': SCHEMA,
            'modules': [{k: m.get(k) for k in ('id', 'title', 'doc') + FIELDS if k in m}
                        for m in good],
        }, ensure_ascii=False, indent=2))
        return 0

    if a.md:
        print('| 模块 | 职责（owns） | 不负责（not_owns） | 描述文档 |')
        print('|---|---|---|---|')
        for m in good:
            print('| %s | %s | %s | `%s` |' % (
                m.get('title') or m['id'],
                ' · '.join(m.get('owns', [])),
                ' · '.join(m.get('not_owns', [])),
                m['doc']))
        return 0

    rc = 0
    for level, msg in check(mods):
        print(('✗ ' if level == 'FAIL' else '· ') + msg)
        if level == 'FAIL':
            rc = 1
    print(f"\n合计：{len(good)} 个模块 / {'边界清晰' if rc == 0 else '存在边界冲突'}")
    return rc


if __name__ == '__main__':
    sys.exit(main())
