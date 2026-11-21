<!--module
id: metrics
title: 监控指标与占位符
owns: 统一占位符命名 · 多实例编号规则 · 各占位符的含义与单位
not_owns: 素材的形态契约 · 检查项与判据 · 机器可读格式 · 风格取舍 · 能力边界
rendering: 生成前：给面板作者一份「可用的数据槽字典」——只能从这些占位符里选，不要自造名字
see: references/contract.md
-->

# 监控指标与占位符

> 面板作者写素材时，`data-slot` / `{{占位符}}` **只能从下表选**，不要自造名字。
> **本表就是「该用哪些传感器」的权威清单** —— 面板要显示什么，就从这里挑对应的占位符。
> 数据由上位机从**本机硬件传感器**（LibreHardwareService）读，算好后经**本地指标 API** 喂给页面（见下）。
> 素材的**形态契约** → `references/contract.md`。

## 数据怎么来（关键：面板不用自己取数）

```
本机硬件传感器 ──► 上位机换算（编号/单位/合计）──► 本地 API /metrics ─┐
                                                      /units    ────┤ 同一段注入脚本
                 外设 HID 电量（鼠标/键盘/耳机）──►    /peripherals ──┤ 并发拉取
                                                                     ▼
                                                   window.__setSlot(key, value)
```

- 上位机在渲染面板时，**通过 CDP 自动往页面注入一段"自取脚本"**（不是素材里的代码）：
  等 `window.__setSlot` 就绪后，每轮**并发**拉
  `GET /metrics`、`GET /units`、`GET /peripherals`，再分别喂进 `__setSlot`。
  稳定期约 **1 秒一轮**（上一轮结束后再等 1s），单请求 4s 超时。
- 所以面板**只要**：① 定义 `__setSlot`（见契约 §4）；② `data-slot` / `{{占位符}}` 用**本表的真名**
  （`cpu_load` / `gpu1_temp`…）。**不要**自己写 `fetch`，也**不要**用 `v1` / `s1` 这类自造名。
- `/metrics` 返回数组，每项：`{ key, group, label, value, unit, text, source, kind }`。
  - `kind` = `number`（默认）或 `text`（型号这类固定文本，注入 `text` 而不是 `value`）；
  - `value` 是数字（读不到为 `null`）；`text` 是格式化好的串（如 `"66.4%"`）；
  - 注入数值槽用 `value`（让 `data-fmt` / `data-suffix` 生效），文本槽才用 `text`。
- 索引里写「23 项基础指标」，但**数组长度按本机实例数展开**：多实例（GPU / 磁盘 / 网卡 / 风扇）
  各占若干条。本机实测（9700X + 5070Ti）为 **42 条**。不要假设固定条数。
- 上位机没开 / 指标读不到时：数值槽给 `—` 或保持默认值，**页面必须有默认值**（不能白屏）。
  `/metrics` 整轮失败时，CPU 三槽（`cpu_load` / `cpu_load_p` / `cpu_load_e`）会被清成 `—`，
  其余槽保持上一轮值（不整屏闪空）。
- **第二条通道**：同一段注入脚本还会拉 `GET /peripherals`（外设电量快照），映射成
  `mouse1_pct` / `kbd1_pct` 这类槽喂进**同一个** `__setSlot`。面板侧无感，仍然不用写 fetch。
- **真实端点/失败行为/谁在调谁** → `references/api_map.md`。

## 外设电量（鼠标 / 键盘 / 耳机）

| 占位符 | 含义 | 单位 |
| --- | --- | --- |
| `<类别><编号>_pct` | 电量百分比（整数 0–100）；**读不到是字符串 `—`，不是 0** | % |
| `<类别><编号>_name` | 型号名（文本槽，如 `VGN S99` / `Rapoo Gaming Device`） | — |
| `<类别><编号>_status` | `充电中` / `放电中` / `离线` / `未支持` / `未连接` / `—`（文本槽） | — |
| `peri_count` | 当前认到几台外设 | — |

类别前缀：`Mouse→mouse`、`Keyboard→kbd`、`Headset|Earbuds→headset`、`Gamepad→gamepad`、
`Dongle→dongle`、其他 `peri`。编号**在同一类别内**从 1 起，按快照顺序（品牌 + 型号排序）。

- **`_pct` 可能是 `—`**：`__setSlot` 必须像处理 `cpu_load` 的「—」一样透传非数字，
  **绝不 `parseFloat` 当 0**（0% = 没电，`—` = 不知道，电池语义下不能混）。
- **`_status` 是文本槽**：不配 `data-fmt`/`data-warn`/`data-danger`/`data-suffix`；
  充电图标按 `v === '充电中'` 判等，**不要**从 `_pct` 反推。
  `_status` 由上位机按固定顺序判定：`!supported → 未支持`；`error && !online → 未连接`；
  `charging === true → 充电中`；`charging === false → 放电中`；`!online → 离线`；否则 `—`。
- **`_name` 的真实来源是 `model || brand`**：外设页里改过的「显示名」（v0.9.1）不会进素材槽；
  名字长度从 `VGN S99` 到 `Rapoo Gaming Device` 不等，别假设长度。
- **编号会随插拔变化**：只画一只鼠标就用 `mouse1_*`，不要为「稳定 ID」设计。
- `supported=false`（认得品牌但没协议）的设备照样出槽：`_pct`=`—`、`_status`=`未支持`、`_name` 有值。
- **设备消失才清空**：设备从快照消失 → 对应槽被喂回 `—`；而单次 `/peripherals` 请求失败时
  整轮跳过、保留上一轮读数（不闪 `—`）。
- **快照约 3 秒一轮**（`/peripherals` 里 `pollMs` 实测 3000），注入脚本每秒拉的是同一份快照 ——
  所以别给电量做逐帧动效。快照里还有 `state`（`live`/`retrying`/`sleeping`/…）等诊断字段，
  但**没有**映射成素材槽；素材只能看到 `_pct` / `_name` / `_status` / `peri_count`。

## 编号规则（多实例）

| 类型 | 是否编号 | 例子 |
| --- | --- | --- |
| **单实例**（一台机器只有一个） | **不编号** | `cpu_load`、`mem_pct`、`sys_uptime` |
| **多实例**（可能有多个） | **从 1 开始编号**，编号紧贴类别名 | `gpu1_temp`、`disk2_pct`、`net1_down`、`fan1` |

- 编号**从 1 起、连续**；顺序**稳定可复现**（磁盘按盘符、网卡按「在用 → 流量 → 连接名」、
  风扇按通道号），不随数据到达顺序漂移。
- 只监控第一个时用 `…1`（如 `gpu1_temp`、`disk1_pct`）。
- 单位**不进名字**（用 `data-suffix` 显示）。
- **哪些是多实例**：GPU（`gpu1_*`/`gpu2_*`…）、磁盘（`disk1_*`/`disk2_*`…）、
  网卡（`net1_*`/`net2_*`…）、风扇（`fan1`/`fan2`…）。台机器上有几个就有几组，
  面板**只引用你确实要显示的那几个编号**即可。
- **网卡**：本机**所有物理网卡**都会出（断开的也在，速率为 0）；虚拟网卡
  （Hyper-V / WSL / Wi-Fi Direct / 蓝牙）与 NDIS 过滤驱动不计入。
- **风扇**：数据源报出的风扇通道，编号**稳定**（同一路风扇的编号不会来回跳）。
- 磁盘另有**合计**：`disk_all_*`（所有固定盘的汇总），不受编号规则约束。

## 指标表

### CPU（单实例）

| 占位符 | 含义 | 单位 | 建议 `data-suffix` |
| --- | --- | --- | --- |
| `cpu_name` | **CPU 型号（文本槽）** | — | 无 |
| `cpu_load` | CPU 总占用率 | % | `%` |
| `cpu_temp` | CPU 温度 | ℃ | `℃` |
| `cpu_power` | CPU 功耗 | W | `W` |
| `cpu_load_p` | **P 核占用率（可选槽）** | % | `%` |
| `cpu_load_e` | **E 核占用率（可选槽）** | % | `%` |

> **`cpu_load_p` / `cpu_load_e` 是条件槽**：只有打开「大小核兼容模式」（`hybrid_compat=1`，
> 自算 CPU 占用率）且数据源/CPU 能给出 P/E 分组时才会出现；AMD 等无 P/E 分组的机器上**没有这两个槽**。
> 素材需要显示它们时，要接受「槽可能一直不出现」——默认值 / 占位文案要能看。
>
> **CPU 风扇没有独立槽**：`cpu_fan` 在 v0.9.x 代码里不存在，主板风扇统一走 `fanN`（见「风扇 / 系统」）。
> 旧文档（含项目侧 `MONITOR_METRICS.md`）里的 `cpu_fan` 是历史残留，**不要引用**。

### GPU（多实例：`gpu1_*` / `gpu2_*` …）

| 占位符 | 含义 | 单位 | 建议 `data-suffix` |
| --- | --- | --- | --- |
| `gpu1_name` | **GPU 型号（文本槽）** | — | 无 |
| `gpu1_load` | GPU 占用率 | % | `%` |
| `gpu1_mem_pct` | 显存占用率 | % | `%` |
| `gpu1_mem_used` | 显存已用 | MB | `MB` |
| `gpu1_mem_total` | 显存总量 | MB | `MB` |
| `gpu1_temp` | GPU 温度 | ℃ | `℃` |
| `gpu1_fan` | GPU 风扇转速 | RPM | `RPM` |

> **文本槽**：`cpu_name` / `gpu1_name` 注入的是**名字本身**（精简型号，如 `9700X`、`5070Ti`），
> 不是数字。所以它们**不要**配 `data-fmt` / `data-warn` / `data-danger` / `data-suffix`，
> 直接 `<span data-slot="cpu_name">{{cpu_name}}</span>` 即可。
>
> **名称从哪来**（CPU / GPU 型号、网卡连接名、风扇通道名都由上位机从数据源读，**不写死**）：
> CPU / GPU 取传感器里的硬件名再精简成型号；网卡取 Windows 的**连接名**（如 `以太网` / `WLAN`）；
> 风扇取数据源给的**风扇通道名**（如 `CPU Fan` / `System Fan #4`）。名称放在 `label`
> （`网卡1 (以太网) 下行`）与 `source`（悬停可见）里 —— 素材能当**文本槽**用的目前只有
> `cpu_name` / `gpu1_name`，`fanN` / `netN` 只给数值。

### 内存（单实例）

| 占位符 | 含义 | 单位 | 建议 `data-suffix` |
| --- | --- | --- | --- |
| `mem_pct` | 内存占用率 | % | `%` |
| `mem_used` | 已用内存 | GB | `GB` |
| `mem_total` | 内存总容量 | GB | `GB` |

### 磁盘（多实例：`disk1_*` / `disk2_*` …，另加**合计**）

| 占位符 | 含义 | 单位 | 建议 `data-suffix` |
| --- | --- | --- | --- |
| `disk1_pct` | 容量占用率（1 号盘） | % | `%` |
| `disk1_used` | 容量已用 | GB | `GB` |
| `disk1_total` | 容量总量 | GB | `GB` |
| `disk1_temp` | 磁盘温度 | ℃ | `℃` |
| `disk_all_pct` | **所有固定盘合计** 占用率 | % | `%` |
| `disk_all_used` | 所有固定盘合计 已用 | GB | `GB` |
| `disk_all_total` | 所有固定盘合计 总量 | GB | `GB` |

> `disk1` / `disk2` … 按**盘符顺序**（C: / D: / E: / F: …）。合计 `disk_all_*` 没有温度。

### 网络（多实例：`net1_*` / `net2_*` …）

| 占位符 | 含义 | 单位 | 建议 `data-suffix` |
| --- | --- | --- | --- |
| `net1_down` | 下行速度 | KB/s | `KB/s` |
| `net1_up` | 上行速度 | KB/s | `KB/s` |
| `net1_total_down` | 累计下行流量 | GB | `GB` |
| `net1_total_up` | 累计上行流量 | GB | `GB` |

### 风扇 / 系统

| 占位符 | 含义 | 单位 | 建议 `data-suffix` |
| --- | --- | --- | --- |
| `fan1` | 风扇 1 转速（多实例：`fan2`…，最多 6 路） | RPM | `RPM` |
| `sys_uptime` | 开机时长 | s | `s` |

> 风扇取自主板 SuperIO 的 Fan 通道，**按通道号稳定排序**，转速为 0 的通道不出现
> （没接风扇 / 停转不会占编号）；面板按「实际有几路」引用即可。
> GPU 风扇是单独的 `gpuN_fan`（0 RPM 也会显示，空闲零转是正常值）。

## 阈值建议（`data-warn` / `data-danger`）

| 占位符 | warn | danger |
| --- | --- | --- |
| `cpu_load` / `cpu_load_p` / `cpu_load_e` / `gpu1_load` | 75 | 90 |
| `cpu_temp` / `gpu1_temp` / `disk1_temp` | 75 | 90 |
| `gpu1_mem_pct` / `mem_pct` / `disk1_pct` | 80 | 92 |

> 其余不强制阈值；**`data-danger ≥ data-warn`**（契约要求）。

## 推荐使用（按面板主题）

| 面板主题 | 推荐占位符 |
| --- | --- |
| CPU | `cpu_name` `cpu_load` `cpu_temp` `cpu_power`（需要时再加条件槽 `cpu_load_p` / `cpu_load_e`） |
| GPU | `gpu1_name` `gpu1_load` `gpu1_mem_pct` `gpu1_mem_used` `gpu1_mem_total` `gpu1_temp` `gpu1_fan` |
| 内存 / 磁盘 | `mem_pct` `mem_used` `mem_total` `disk1_pct` `disk1_used` `disk1_total` |
| 网络 | `net1_down` `net1_up` `net1_total_down` `net1_total_up` |
| 外设电量 | `mouse1_pct` `mouse1_name` `mouse1_status` `kbd1_pct` `kbd1_name` `kbd1_status` `peri_count` |
| 综合 | `cpu_name` `cpu_load` `gpu1_name` `gpu1_load` `gpu1_temp` `mem_pct` `net1_down` |

## 怎么查本机真实槽位（**别手打**）

上位机 exe 自带 CLI，不用开界面、不碰设备：

```bash
jiadian-monitor.exe --dump-metrics        # 打印 /metrics 的同一份 JSON（含本机实际编号与 source）
jiadian-monitor.exe --dump-units          # 单位设置
jiadian-monitor.exe --peripherals-dump    # 打印 /peripherals 的同一份 JSON（外设实际槽名/状态）
```

直接把 `key` 复制进素材的 `data-slot` / `{{...}}`，**不要手敲**（拼错会静默失效，见坑表 A 组）。
原先「预览界面一键复制占位符」的 UI 目前已不在界面里 —— 以 CLI 输出 + 本表为准。

## 使用边界

- 上表是**全部可用数据槽**，写面板时**只从这里选**，不要自造 `v1` / `s1` 之类。
- 每个面板不必用全，按主题挑（如"GPU 面板"取 `gpu1_*` + `cpu_load` + `mem_pct`）。
- 多实例按需取编号（`disk1_pct`、`disk2_pct`…），编号从 1 起、连续。
- **没有的指标**（每核占用、电压、SMART、FPS 等）本版**不提供**，不要引用。
  P/E 核是**分组**占用率（`cpu_load_p` / `cpu_load_e`），条件出现，不是逐核数据。
- 本表与 v0.9.1 实测对齐（2026-11-07 核对）；项目侧 `MONITOR_METRICS.md` 已于同日同步
  （`cpu_fan` 已删、补 P/E 条件槽与 `kind` 字段），但仍以本表 + `--dump-metrics` 实际输出为准。
