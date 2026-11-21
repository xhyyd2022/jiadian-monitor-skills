<!--module
id: maintenance
title: 技能维护
owns: 技能自身的制作约定 · 维护流程（两段式结构/同步/打包校验/安全审计）
not_owns: 能力的定义与边界 · 主项目链路 · 素材的形态契约 · 检查项与判据 · 机器可读格式 · 风格取舍
rendering: 维护级：保证约束渲染条件在刷新后不被破坏（刷新只动基础段、技能段按标记保留、判据仍按 W×H 参数化）
see: references/self_check_gates.md
-->

# 技能维护约定

> 本文只讲**这个技能自己怎么维护**：结构怎么分、怎么和项目同步、做过哪些验收、审计结论。
> 能力的定义 → `references/capability.md`；主项目 → `references/project.md`。**本文不重复它们的内容。**

## 1. 两段式结构（改的时候别改错地方）

自检脚本是**两段**拼起来的：

| 段 | 内容 | 谁维护 |
|---|---|---|
| **基础段** | A1–A12 / B1–B7（静态契约 + 无头真渲染） | **由 `scripts/sync_base.py` 从项目刷新**，别手改 |
| **技能专属段** | 产物格式约束：A13 清单块 / `--json` / `--emit-manifest` | 手写在文件末尾 `SKILL-ONLY EXTENSION BEGIN/END` 之间 |

> **2026-11 增量**：`sync_base.py` 在生成基础段时会额外注入一段 **stdout UTF-8 护栏**
> （`sys.stdout.reconfigure(encoding='utf-8', errors='replace')`）。原因：Windows 控制台默认 GBK，
> 报告里的 `✗` / `★` 等符号会让「有 FAIL」的检查直接抛 `UnicodeEncodeError`、整份报告崩掉。
> 护栏由同步脚本注入，不是手改基础段；跑 `sync_base.py --check` 应显示「已是最新」。

**为什么这么分**：基础逻辑来自项目实现，手抄必然漂移（本项目已吃过两次文档漂移的亏）；
而「产物格式约束」是**技能独有**的能力，项目里没有，也不打算回流。两段用标记隔开 →
`sync_base.py` 刷新基础段时会**按标记把技能段原样保留**；**标记找不到就停下报错**，绝不静默冲掉。

**推论**：技能相关的改动**只放技能文件夹内**，不改项目里的 `tools/css_panel_test/check_material.py`。

## 2. 与项目实现同步

```bash
cd <skill>
python scripts/sync_base.py --check                # 只比对，不写盘（有差异退出码 1）
python scripts/sync_base.py                        # 刷新基础段（参考素材按 p\d+_[a-z_]+\.html 复制，见下）
python scripts/sync_base.py --project <项目目录>    # 项目不在默认位置时显式指定
```

改了项目里的 `check_material.py`（或 `webview_render.py` 的 `find_edge` / `parse_size`）后**必须重跑同步**，
否则两边漂移。同步脚本做这些事：

1. 从 `webview_render.py` 切片出 `_EDGE` / `find_edge` / `parse_size` 三段，内联进来；
2. 把 `check_material.py` 对 `webview_render` 的导入换成内联片段，`wr.xxx(` 改成直接调用；
3. 把 `--all` 的扫描目录指到技能自带的 `assets/verified_materials/`；
4. 把末尾 `SKILL-ONLY EXTENSION` 块**原样搬过去**（标记缺失即报错退出）；
5. 复制 `materials/p*.html` 过来，并**重新派生**产物清单块。
   ⚠️ 项目 `materials/` 里的文件名与技能库**不一致**（项目 `p1_taskmgr.html` ↔ 技能 `p1_dash.html`），
   `sync_materials()` 会按项目名直接落地，**手工新增的 `p14–p16`（外设电量）在项目里没有对应源文件**，
   所以正常流程只跑 `--check`，不要盲目跑会写盘的 `sync_base.py`。

⚠️ **`SKILL.md`、`references/`、`assets/material_prompt.md`、`assets/verified_materials/README.md`
不归同步脚本管**，需手工维护。`material_prompt.md` 的基础部分从项目 `PIPELINE_SPEC.md` §3 抽，
但技能**另追加了产物清单块要求**（`1.1` + 闸门 `2.10`）—— 改提示词时两处都要顾到。

> **与主项目提示词副本的关系**（2026-11-07）：`assets/material_prompt.md` 是技能分发版，
> 比项目里 `app/src/components/material_prompt.md` 多了模块描述块 + ```text 包装，**正文应当一致**；
> 改事实性内容（槽位 / 状态 / 节奏）时两边都要改，别只改一边。
> 2026-11-07 已同步两侧正文（app 侧只改文档，未重新编译；下次构建生效）。

## 3. 描述块与边界（本技能的自描述机制）

每个模块在自己的文档/脚本**开头**写一个 `<!--module ... -->` 描述块，声明
`id` / `title` / `owns` / `not_owns` / `rendering` / `see`（多值用 `·` 分隔，兼容 ASCII `,`；
**全角 `，` 不算分隔符**）。`scripts/describe.py` 负责**聚合**并**校验边界**：

```bash
python scripts/describe.py --check   # D1–D4，有冲突退出码 1
python scripts/describe.py --md      # 人读职责索引表
python scripts/describe.py --json    # 机器可读描述
```

- **D1** 每个模块都有描述块、`id` 唯一、文件存在；
- **D2** `owns` / `not_owns` / `rendering` 三项都必须写；
- **D3** 同一条 `owns` **不许出现在两个模块里**（职责不重叠）；
- **D4** 每个 `see` 指向的文件都存在。

**词表纪律（写描述块时遵守）**：

- 六大「定义类」词表固定为：**能力的定义与边界 · 主项目链路 · 素材的形态契约 ·
  检查项与判据 · 机器可读格式 · 风格取舍**（按此顺序）。
- 每个模块的 `not_owns` = 六大类中**不属于自己**的项（自己 owns 的那类不写进去），
  必要时在最前面追加**模块特有的甩锅项**（如 sync-base 的「技能专属扩展的内容」）。
- 不在词表里的词（如「工具用法」）**不要**写进 not_owns —— 它不是任何模块 owns 的定义类。
- 多值字段只用 `·`；短语内部要停顿用全角 `，`（全角不算分隔符，ASCII `,` 算）。

**脚本里的描述块必须写在文件最前面**（在模块 docstring 之前）——
否则 docstring 里的示例块会被当成该模块自己的描述。

## 4. 制作技能时踩到的坑

| 坑 | 现象 | 根因 / 修法 |
|---|---|---|
| **`description` 里不能有尖括号** | 官方校验器报 `Description cannot contain angle brackets` | YAML **折叠块** `description: >` 的 `>` **本身就被判成尖括号**。改成**单行** description 即通过 |
| **折叠块又长又脆** | 打开文件时头部一大片，像没排版 | `description: >` + 多行缩进续行：缩进被任何环节吃掉就坏；**单行最稳** |
| **技能必须自包含** | 拷走就报 `ModuleNotFoundError` | 基础逻辑依赖同项目模块 → 同步脚本从源实现**切片内联** |
| **`--all` 默认目录指向原项目** | 技能拷走后 `--all` 扫不到东西 | 同步时把扫描目录改到技能自带的 `assets/`；**改名/改路径后必须实跑一次** |
| **刷新基础会把技能段冲掉** ⭐ | 同步脚本整份重写 → A13 / `--json` 悄悄没了 | 扩展放 `BEGIN/END` 标记之间；同步脚本按标记**原样搬过去**，标记找不到**停下报错** |
| **技能改动别写进项目** ⭐ | 在项目 `tools/` 里加技能专属功能 → 项目被污染、下次同步被冲掉 | 技能改动**只放技能文件夹内**；同步是**单向**的（项目 → 技能基础段） |
| **描述块里写了 ASCII `,` 被当成多值分隔** | `owns` 里一个带逗号的短语被拆成两条，误报 D3 重叠 | 多值字段**只用 `·`**；短语内部若要停顿用**全角 `，`**（全角不算分隔符） |

## 5. 定稿前的验收动作（都跑过）

```bash
# 1) 官方校验器（检查 frontmatter / 命名 / 目录结构 / 描述质量）
python <skill-creator>/scripts/quick_validate.py  jiadian-monitor-skills      # → Skill is valid!
# 2) 完整打包校验（更严，顺带产出可分发的 zip）
python <skill-creator>/scripts/package_skill.py   jiadian-monitor-skills <输出目录>
# 3) 独立性：从别的盘符用绝对路径跑
cd C:/ && python <abs>/jiadian-monitor-skills/scripts/check_material.py --all  # → 16/16 PASS
# 4) 同步幂等：连跑两次 --check，第二次应"已是最新"
python scripts/sync_base.py --check
# 5) 边界校验
python scripts/describe.py --check                                           # → 边界清晰
# 6) 在线形态自检：A16–A19 与 B 层降级都要生效
python scripts/check_material.py <在线素材>.html --mode online --no-render   # → 看 A16/A17/A19
# 7) 自截图（有视觉能力时判闸门 4 用）
python scripts/screenshot.py <素材>.html --scale 2                           # → out/<素材>.png
# 8) 输出护栏：故意给一个缺清单块的素材，在 GBK 控制台应打印 FAIL 而不是崩掉
python scripts/check_material.py <坏素材>.html --no-render                    # → exit 1，有 ✗ A13
```

## 6. 安全审计（2026-10-12，2026-11-07 复核）

> 本机未安装 `skills-security-check`，按同等标准手工审计。
> 2026-10-12 增量：新增产物格式约束（A13 / `--json` / `--emit-manifest`）与
> `add_manifest.py` / `sync_base.py` / `describe.py` 后**重审**，结论不变（仍是 P2）。
> **2026-11-07 增量**：新增 `references/api_map.md`（纯文档，只登记本地 HTTP 端点与调用关系，不含可执行代码）
> 与 `sync_base.py` 的 stdout 护栏（不新增外部动作 / 网络 / 子进程），结论不变（P2）。

**范围**：技能目录下全部文件（1 个 SKILL.md、4 个 Python 脚本、7 篇 reference、1 个提示词、
1 个素材库 README、16 个 HTML 素材）。

| 模式 | 命中 | 结论 |
|---|---|---|
| 网络访问 / 外部资源引用 | **0 处** | 全目录无 http(s) 请求、无 `fetch`/`XHR`/`WebSocket`；素材不引任何外部 `src`/`href`/`@import`（`bg_kind()` 里的 `http://` 只是**字符串前缀判断**，不发请求） |
| 子进程调用 | 3 处 | 全在 `check_material.py`：`subprocess.run(cmd, capture_output=True)` 启动**无头 Edge**；命令是**固定列表**、**无 `shell=True`**，无命令注入 |
| 删除 / 破坏操作 | 1 处 | `shutil.rmtree(tmpdir)` 在 `finally` 里，`tmpdir` 由同函数 `tempfile.mkdtemp()` 创建 —— **配对且只删自己的临时目录** |
| 凭据 / 环境变量读取 | 0 处 | 两处 "token" 命中是文档里"token 数"这个词，非凭据 |
| 动态执行 / 混淆 | 0 处 | `compile(` 全是 `re.compile()`；`exec(` 是注入脚本里 JS `RegExp.exec()`。**无 `eval` / `__import__` / base64 解码 / 十六进制转义** |
| 注册表 / 系统改动 / 权限 | 0 处 | 无 |

**文件写入面**：

- `check_material.py`：只往自己创建的临时目录写一个 `check.html`；
- `add_manifest.py`：只写用户**显式指定**（或 `--all` 覆盖的参考素材）的 `.html`，且**幂等**；
- `sync_base.py`：只写技能目录内的 `scripts/check_material.py` 与 `assets/verified_materials/`；
- `describe.py`：**只读**，不写任何文件。

**结论：P2（安全）—— 无 P0 / P1 风险。** 唯一外部可执行动作是启动本机浏览器做无头渲染，
这是自检功能本身必需的，参数完全固定（`--headless=new --disable-gpu ... --dump-dom <file-url>`）；
脚本对素材只做**读取 + 正则解析**，不执行素材里的 JS（素材 JS 只在无头沙箱里跑，用于回读自检结果）。

## 7. 运行环境的已知边界

| 现象 | 原因 | 处理 |
|---|---|---|
| `B0 运行期检查异常：[Errno 13] / [WinError 5]`（临时目录写不了） | 受限令牌 / 沙箱把 `%TEMP%` 或子进程管道拦了 | 在普通桌面会话跑；临时目录可写后再试。只做静态层时加 `--no-render` |
| `FATAL: platform_channel.cc ... 拒绝访问` / 无头浏览器起不来 | 受限进程无法创建命名管道（Chromium 多进程必需） | 同上：换普通会话。这不是素材问题，静态层 `A1–A15` 不受影响 |
| 报告里的 `✗` 触发 `UnicodeEncodeError` | Windows 控制台默认 GBK | 已由 `sync_base.py` 注入 stdout 护栏；仍有问题可设 `PYTHONIOENCODING=utf-8` |
| `--all` 找不到素材 | 技能被拷贝到别的目录后扫描路径仍指旧项目 | 本版已把 `--all` 指到技能内 `assets/verified_materials/`；见 §1 |
| 临时目录明明可写，仍报 `Errno 13: ...\chkm_xxx\check.html` | `tempfile.mkdtemp` 建的是 **0700** 目录，若运行进程与被沙箱进程**不是同一个用户**（某些 agent 沙箱），子进程写不进去 | 与素材无关。换普通桌面会话；或在包装脚本里把 `tempfile.mkdtemp` 换成 `os.makedirs(..., 0o777)` 的实现 |
| 截图/渲染报 `Network: 拒绝访问 (0x5)`、`--dump-dom` 拿不到结果 | 浏览器自身沙箱（多进程）在受限令牌下起不来 | 同上：换普通会话。静态层 `--no-render` 不受影响 |

## 8. 2026-11-07 与 v0.9.1 对齐的改动（本次升级记录）

| 改动 | 文件 | 依据 |
|---|---|---|
| 新增「真实调用关系」参考：8766 直读 13 个端点实况、注入脚本节奏/失败语义、8765 移交、外部 API 现状 | `references/api_map.md`（新） | 本机运行实例实测 + `app/src-tauri/src/{api,pipeline,handoff,units,assets,peripherals}` |
| 指标字典纠偏：删掉不存在的 `cpu_fan`；补条件槽 `cpu_load_p/e`；补 `/metrics` 的 `kind` 字段、数组随实例展开、失败/清空语义 | `references/metrics.md` | `metrics.rs::basic`、`select_cpu_source`、`pipeline.rs::pull_js` |
| 链路纠偏：抓帧不是 CDP screencast，而是 `Page.captureScreenshot` 轮询（33/100ms，静止 3 帧→300ms）；差分 mode 0/1/2，LZ4 未启用 | `references/project.md`、`SKILL.md` | `pipeline.rs`、`live_frame.rs`、`diff.rs` |
| 注入细节纠偏：并发拉 `/metrics`+`/units`+`/peripherals`、文本槽 vs 数值槽、单位换算与 `data-suffix` 改写、`?__api` 只是地址标注 | `references/contract.md`、`assets/material_prompt.md` | `pipeline.rs::pull_js`、`units.rs` |
| 删掉已不存在的「预览界面一键复制占位符」，改为 CLI `--dump-metrics` / `--peripherals-dump` | `SKILL.md`、`references/metrics.md`、`assets/material_prompt.md` | `main.rs` CLI 列表 |
| 数量/对照关系：技能样例 16 套、主产品内置 18 套主题（2 套未收进库：本地图片底图 / 紫绿初号机监控台） | `style_catalog.md`、`verified_materials/README.md`、`SKILL.md` | `GET /themes` 实测 + `bin/assets/` |
| `describe.py` 的 SCAN 补上 `references/metrics.md` 与 `references/api_map.md`（原先 metrics 有描述块却没被扫到）→ 16 个模块 | `scripts/describe.py`、`skills/README.md` | `describe.py --check` |
| 修 Windows GBK 控制台「有 FAIL 就 UnicodeEncodeError 崩掉」：`sync_base.py` 生成基础段时注入 stdout 护栏 | `scripts/sync_base.py`（生成 `scripts/check_material.py`） | 本机复现 + 修复后负例测试 |
| 环境边界与排查写进文档：沙箱/受限令牌下 B 层起不了无头浏览器时怎么办 | `references/self_check_gates.md`、`references/maintenance.md` §7 | 本次在受限会话中实测 B0 权限错误 |
| 同步项目侧文档（只改文档，未重新编译）：删 `cpu_fan`、补 `cpu_load_p/e` 条件槽 / `kind` / 注入细节 / 外设 `_name` 来源 | `app/MONITOR_METRICS.md`、`app/src/components/material_prompt.md` | 用户 2026-11-07 确认修复；`git -C app diff` 仅文档改动 |

**本次验证**：`describe.py --check`（16 模块 / 边界清晰）、`check_material.py --all`（**16/16 PASS，
含 B1–B7 运行时层**；本会话切到完全权限后可跑无头浏览器，已补跑全量）、
`add_manifest.py --all --check`（16 套均有清单）、`sync_base.py --check`（已是最新）、GBK 负例不崩溃。
**素材库本轮未增删**：尝试回填内置的「本地图片底图」可通过闸门但违反本库「单文件 + 纯 CSS 底图」约定；
「紫绿初号机监控台」B 层不达标（条/轨道重叠 + 1 处对比度 5.1:1），故保持 16 套。
