<!--module
id: materials
title: 已验证素材库
owns: 16 套参考素材清单与各自风格/槽位标注
not_owns: 能力的定义与边界 · 主项目链路 · 素材的形态契约 · 检查项与判据 · 机器可读格式 · 风格取舍
rendering: 素材级：16 套都已过闸门；下表标注各自在约束渲染下的落点（明暗/动效面积/自定义 kind）
see: references/style_catalog.md, references/self_check_gates.md
-->

# 已验证素材库（16 套）

> 本目录只讲**这 16 套素材自己**：它们分别是什么风格、有几个槽、用了哪些自定义 kind。
> **怎么选风格** → `references/style_catalog.md`；**怎么判它们合格** → `references/self_check_gates.md`。
> 契约、判据、机器可读格式**不在本文重复**，各自去看对应文档。

**定位**：这 16 套是**能直接跑、且全部通过闸门**的单文件素材，用作：
① 写新素材时照抄的骨架；② 回归测试的固定样本（`check_material.py --all` 应 16/16 PASS）。

> **与内置主题的关系**：主产品 v0.9.1 内置 18 套主题，其中 16 套与本库同源（本库的 p1–p16
> 对应内置的硬件面板 / 键鼠电量三套）；未收进本库的两套是「本地图片底图」（演示本地底图，
> 需要 `bg.png` 同层，参考 `bin/assets/本地图片底图/v2/index.html`）与
> 「紫绿初号机监控台」（仅 v2 变体）。本库仍以 16 套可独立跑、纯 CSS 底图的单文件为回归集。

**只保留基础指标**：每套的 `data-slot` 一律取自标准占位符字典
（`cpu_load` / `gpu1_load` / `mem_pct` / `disk1_pct` / `net1_up` / `net1_down` /
`cpu_temp` / `fan1`），**不含**每核 / 进程 / 节点等进阶项。

**共同点**（都是素材自身的属性，不是契约要求）：

- 视口 `320×240`、贴左上、单文件、`background` 全为 `css`（纯 CSS 渐变，不引任何文件）。
- 每套都带产物清单块（`<script type="application/json" id="material-manifest">`），**派生不手写**。
- 每套都实现了 `window.__setSlot`，逐槽注入 `0/50/100/999` 不抛错、无残留占位符。

---

## 清单

| # | 文件 | 风格 | 明暗 | data-slot | 自定义 kind | 动效落点（重绘面积） |
|---|---|---|---|---|---|---|
| 1 | `p1_dash.html` | 深蓝紫仪表盘 | 深 | 7 | — | 大数字 / 细条 |
| 2 | `p2_seg_hud.html` | 深青军规分段条 | 深 | 8 | `seg` | 逐格点亮的段 |
| 3 | `p3_mac_cards.html` | 浅灰白 macOS 风 | 浅 | 9 | — | 卡内数值 / 底条 |
| 4 | `p4_light_grid.html` | 清爽浅灰四宫格 | 浅 | 10 | — | 四格数值 / 条 |
| 5 | `p5_paper_columns.html` | 暖灰报刊 | 浅 | 8 | — | 制表行数值 |
| 6 | `p6_alert_industrial.html` | 黑底荧光黄工业警示 | 自由 | 7 | — | 超大主数值 |
| 7 | `p7_blueprint.html` | 深蓝工程蓝图细线 | 自由 | 10 | — | 刻度 / 数据盒数值 |
| 8 | `p8_glass_cards.html` | 玻璃拟态 | 深 | 9 | — | 玻璃卡内数值 / 条 |
| 9 | `p9_neumorph.html` | 新拟物 | 浅 | 7 | — | 凸凹面板内数值 / 条 |
| 10 | `p10_terminal.html` | 绿色磷光终端 | 深 | 10 | — | 段式条 + 闪烁光标（面积极小） |
| 11 | `p11_swiss.html` | 瑞士国际主义 | 浅 | 10 | — | 网格内数值 |
| 12 | `p12_cyber_neon.html` | 赛博霓虹 | 深 | 9 | — | 霓虹数字 / 斜切块 |
| 13 | `p13_ring_gauges.html` | 圆环仪表盘 | 浅 | 9 | `ring` | `conic-gradient` 圆环（1~3k px） |
| 14 | `p14_peri_dark.html` | 键鼠电量深色 | 深 | 9 | — | 大百分比 / 细条 |
| 15 | `p15_peri_light.html` | 键鼠电量浅色 | 浅 | 9 | — | 右对齐大数字 / 细条 |
| 16 | `p16_peri_terminal.html` | 键鼠电量终端 | 深 | 9 | — | 大百分比 / 纯色块条 |

> 14–16 是**外设电量专项**（`mouse1_pct` / `mouse1_name` / `mouse1_status` / `kbd1_pct` /
> `kbd1_name` / `kbd1_status` / `peri_count` + 两条 bar），数据走第二条通道 `GET /peripherals`。
> 它们同时也是内置主题 `键鼠电量深色` / `键鼠电量浅色` / `键鼠电量终端` 的 `v2` 版本来源。

> 「自定义 kind」= 该套额外演示了 `data-kind` 的哪种扩展形态（`seg` / `ring`）。
> 其余套只用基础的 `text` + `bar`。
>
> 曾有的「任务管理器（进程列表）」「八核热力矩阵（每核）」「服务器机架图（节点）」三套
> **已删除** —— 它们依赖本机取不到的进阶传感器（进程 / 每核 / 多节点），不在基础范围。

---

## 怎么用这套素材

```bash
# 全部跑一遍（应 16/16 PASS；需要本机 Edge/Chrome）
python scripts/check_material.py --all

# 只跑静态契约层（不需要浏览器）
python scripts/check_material.py --all --no-render

# 机器可读报告
python scripts/check_material.py --all --json
```

照抄时**只抄骨架与排版**，数据槽位按自己的需求改（从标准占位符字典里挑）；改完**务必重跑闸门**，
并**重新派生清单块**（`python scripts/add_manifest.py 你的.html`）——
清单块与素材不一致会被 **A13** 判 FAIL。
