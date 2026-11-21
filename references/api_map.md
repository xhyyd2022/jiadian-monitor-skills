<!--module
id: api-map
title: 本地 API 与调用关系
owns: 本地 API 端点实况与调用关系 · 注入脚本行为 · 上位机移交（handoff）契约
not_owns: 能力的定义与边界 · 主项目链路 · 素材的形态契约 · 检查项与判据 · 机器可读格式 · 风格取舍
rendering: 素材级：说明页面运行时真正被谁、以什么频率、喂了哪些值（README 与素材作者只需要知道边界）
see: references/project.md, references/metrics.md, references/contract.md
-->

# 本地 API 与真实调用关系

> 本文回答一个问题：**素材在真机上运行时，到底有哪些东西在调 API、调了什么、什么时候调。**
> 数据槽字典 → `references/metrics.md`；契约 → `references/contract.md`；项目链路 → `references/project.md`。
>
> **核对时间：2026-11-07**，对照 `app/`（jiadian-monitor **v0.9.1**）源码 + 本机运行实例实测
> （`GET http://127.0.0.1:8766/*`、`POST http://127.0.0.1:8765/usb/status`、CDP `9333/json/list`）。
> 源码行号会漂，引用只保证「曾经在这些位置」；以行为描述为准。

## 1. 总览：谁在调谁

```
LHS 共享内存（LibreHardwareService）──┐
Win32：GetIfTable2 / 逻辑盘 / 开机时长 ─┤→ Rust 采集（metrics / source_lhws）→ GET /metrics ┐
HID 外设轮询（3s 一轮）──────────────┘                                                │
                                                                                    ▼
                                                    本机 HTTP API 127.0.0.1:8766（JSON，只读）
                                                     GET /units   ← 单位设置（前端改、注入脚本拉）
                                                     GET /settings /devices /link /themes
                                                     GET /peripherals
                                                            ▲
                                                            │ 每秒 3 个并发 fetch（注入脚本）
                                                            │
               Tauri 隐藏 WebView2 ── 加载 file:///…/assets/<主题>/<v1p|v2>/index.html?__api=8766
                     ▲  加脚本：CDP Page.addScriptToEvaluateOnNewDocument + Runtime.evaluate
                     │  抓帧：CDP Page.captureScreenshot 轮询（33ms / 100ms / 静止 300ms）
                     └────────────── RGB565 → 脏矩形 → USB LIVE（A5 5A 0B）→ 佳点 V1P / V2 小屏
                                                     ↕ USB 使用权移交（POST http://127.0.0.1:8765/usb/handoff/*）
                                              官方上位机「佳点V1PRO控制工具」8765
```

关键点：

- **素材本身不调 API**。所有取数由上位机在面板页面里注入的一段脚本完成（`pipeline.rs::pull_js`），
  素材只需要 `window.__setSlot` + `data-slot`。
- 面板页面与本地 API 之间是**跨源请求**（页面 `file://`，origin 为 `null`），
  靠 8766 统一回 `Access-Control-Allow-Origin: *` 才能 fetch。
- 面板加载**仍然是 `file://`**；`?__api=8766` 只是上位机加在地址上的端口标注，
  **页面不需要解析它**，自取脚本由 CDP 注入，不依赖 URL 参数。（所以真机上的 8766 换成 `[::1]` 也不影响素材。）
- 8766 **没有静态文件能力**：`/assets/...` 路由不存在（截至 2026-11-07），面板不能改走
  `http://127.0.0.1:8766/assets/...`。

## 2. 8766 端点实况（本机 v0.9.1 实测）

所有响应带 `Access-Control-Allow-Origin: *`；服务只监听回环（`127.0.0.1` / `[::1]`，`localhost` 亦可），
不做鉴权；每次都 `Connection: close`。`OPTIONS` → `204`；未知路径 → `404 text/plain "not found"`。

| 方法 | 路径 | 返回 | 形状 / 要点 |
|---|---|---|---|
| GET | `/` | JSON | 自描述索引：`{name, version, note, base, endpoints[]}` |
| GET | `/version` | JSON | `{"version":"0.9.1"}`（等于程序版本） |
| GET | `/health` | text | `ok`（2 字节） |
| GET | `/metrics` | JSON 数组 | 每项 `{key, group, label, value, unit, text, source, kind}`；`kind` = `number` / `text`；读不到 `value=null`。索引里写「23 项基础指标」，**数组长度随本机实例数展开**（本机实测 42 条：3 块盘、2 块网卡、4 路风扇…） |
| GET | `/units` | JSON | `{"mode":"auto"| "manual", "units":{族:单位}}`；族固定四类：`capacity` / `rate` / `temperature` / `duration`，空串 = 跟随素材 |
| GET | `/settings` | JSON | 全部设置（camelCase）：`silentStart/highFps/hybridCompat/logging/logLevel/theme/closeToTray/devtools/unitMode/unitCapacity/unitRate/unitTemp/unitDuration/peripheralNames`。**没有 `[proxy]`**（见 §6） |
| GET | `/devices` | JSON 数组 | 每项 `{connected, width, height, serial, variant, path}`；本地 WinUSB 枚举 + 8765 富化，未连接设备给空字段 |
| GET | `/link` | JSON | `{"open":true,"ready":true,"serial":"…"}`（USB 是否已接管） |
| GET | `/themes` | JSON 数组 | `[{name, page, variants:[{tag, page, width, height}]}]`；`page` 相对 `assets/`（如 `圆环仪表盘/v2/index.html`）。**存在只有 `v2` 变体的主题**（如「紫绿初号机监控台」） |
| GET | `/peripherals` | JSON | 后台轮询的**快照**：`{ok, exeName, dir, dirLabel, pollMs, updatedMs, devices[], errors[]}`。`devices[i]` 字段见 §3.3 |
| POST | `/peripherals/refresh` | text | `refreshing`——立即重读协议 JSON 并轮询一轮，不等 3s |
| POST（GET 也兼容） | `/app/show` | text | `ok`——唤起主窗口 |
| POST（GET 也兼容） | `/app/quit` | text | `quitting`——归还设备后退出 |

补充（容易误判）：

- 8766 可能落在 Windows 保留端口段。bind 失败报 `os error 10013` 时程序**每 5 秒重试**，
  面板会「有画面但数字不动」。素材里把 8766 当固定端口没问题，因为它就是固定设计（不可换）。
- 基址不一定写死 `127.0.0.1`：注入脚本用「实际绑上的回环地址」拼 URL（IPv4 或 `[::1]`）。
- `/metrics`、`/units`、`/peripherals` 是素材唯一会感知到的三个端点；其余是给界面 / 调试 / 第三方工具用的。

## 3. 注入脚本：素材实际拿到数据的唯一途径

上位机在渲染会话里注入 `pull_js()`（`pipeline.rs:388-572`）：

1. **注入时机**：新页面在 `Page.addScriptToEvaluateOnNewDocument`（导航前，`pipeline.rs:626`）；
   复用已加载页面时补一次 `Runtime.evaluate`（就绪后，`pipeline.rs:844`）。
2. **启动条件**：每 100ms 检查 `typeof window.__setSlot === 'function'`，就绪后立刻跑第一轮。
3. **节奏**：上一轮**结束后**再等 1s（`setTimeout(p,1000)`，不是 `setInterval`），
   所以稳定期约 1Hz；单请求有 **4s AbortController 超时**，`cache:'no-store'`，
   网络/接口故障不会堆积旧响应。
4. **拉什么**：每轮 `Promise.all` 并发拉 `/metrics`、`/units`、`/peripherals`。
5. **怎么喂**：
   - `kind === 'text'` → `__setSlot(key, String(text))`（如 `cpu_name` / `gpu1_name`）；
   - 其他（数值）→ 先按单位换算，再 `__setSlot(key, String(数值))`（**素材的 `data-fmt` 再决定小数位**）；
   - 单位：扫 `[data-unit]` 得到「素材要的单位」；`/units` 为 `manual` 时按族覆盖素材声明；
     换算结果按目标单位取合适位数（`DEC` 表）。手动模式还会把新单位写回元素的 `data-suffix`，
     切回 `auto` 时还原素材原始后缀。
   - CPU 特殊槽：`cpu_load` / `cpu_load_p` / `cpu_load_e` 缺失或非有限值时统一喂 `—`（不喂 0）。
   - `/metrics` 请求失败：CPU 三槽清成 `—`，**其余槽保持上一轮值**（不整屏闪空）。
6. **外设通道**（`applyPeri`，`pipeline.rs:508-543`）：
   - 类别前缀：`Mouse→mouse`、`Keyboard→kbd`、`Headset|Earbuds→headset`、`Gamepad→gamepad`、
     `Dongle→dongle`、其他→`peri`；**同类别内从 1 编号**（按快照顺序）。
   - `_pct` = `battery`（仅当 `supported && battery != null`），否则字符串 `—`；
   - `_name` = `model || brand || '—'`（**注意：v0.9.1 支持编辑显示名，但注入槽用的仍是 `model`/`brand`，
     改过的名字不会进素材**）；
   - `_status` 映射（严格按 `pipeline.rs::pstatus`）：
     `!supported → 未支持`；`error && !online → 未连接`；`charging === true → 充电中`；
     `charging === false → 放电中`；`!online → 离线`；否则 `—`。
   - `peri_count` = 本轮 `devices.length`（认到几台，不是「几台有电」）。
   - **请求失败（null）时整轮跳过**，保留上一轮外设槽；只有设备从快照消失才把对应槽喂回 `—`。
   - 外设数据本身是后台 **3 秒一轮**（`/peripherals` 的 `pollMs`），注入脚本每秒拉的是同一份快照。

## 4. 面板加载与「检查闸门」的差别

| 场景 | 页面 | 注入脚本 | 数据 |
|---|---|---|---|
| 真机渲染 | `file:///…/assets/<主题>/<v1p|v2>/index.html?__api=8766` | ✅ CDP 注入 | 每秒从 8766 拉真值 |
| 在线渲染 | `https://…/panel.html?__api=8766`（或局域网私有地址 http） | ❌ **不注入** | 页面**自己**每秒从 8766 拉 |
| 自检闸门（在线） | 素材文件直接 `file://` 打开 + `--mode online` | ❌ 不注入 | 只查代码里「有没有取数」，不真连 |
| 自检闸门 | 素材文件直接 `file://` 打开 | ❌ 不注入 | 只有默认值 / `?槽名=值` URL 参数 |

所以闸门结果确定、可复现；素材**不要**依赖 `?__api` 或自己 fetch —— 真机上注入脚本是唯一数据源。

### 4.1 在线形态的取数差异

| 项 | 本地素材（`file://`） | 在线素材（`http(s)://`） |
|---|---|---|
| 注入脚本 | ✅ 上位机注入 | ❌ 不注入 |
| 谁取数 | 注入脚本 | **页面自己** `fetch` |
| `?__api` | 只是标注，**不用解析** | **必须解析**（端口会变） |
| 页面地址 | `file:///…/index.html?__api=8766` | `https://…` 或 `http://192.168.x.x:8080/…` |
| 失败表现 | 注入脚本清 CPU 三槽为 `—` | 页面自己的 `catch` 决定，**必须也写 `—`** |
| 常见拦截 | 无 | CSP `connect-src`、LNA（公网→私网） |

三个补充事实：

- **`?__api` 会被上位机重写**：加载在线页面时先摘掉 URL 里已有的 `__api=`，再追加当前实际端口 ——
  所以页面里写死的旧端口不会生效，只能读参数。
- **端口不是恒定 8766**：8766 被占用时上位机会重试到 10013 等端口，页面必须读参数。
- **在线页面不能调控制接口**：`/app/show`、`/app/quit` 只放行无 Origin / `Origin: null`，在线页面调用一律 403。
  数据接口（`/metrics` `/units` `/peripherals`）是 `Access-Control-Allow-Origin: *`，可跨源取。

> 托管步骤、CSP 写法、LNA 症状 → `references/online_hosting.md`

## 5. 与官方上位机 8765 的调用关系（USB 移交）

素材不直接接触这一层，但它是「为什么程序能在官方 GUI 开着时推屏」的答案：

- 基址 `http://127.0.0.1:8765`；请求统一 **POST**（`/usb/status` 也是 POST，不是 GET）；单次超时 4s。
- 顺序：`POST /usb/status`（看 `guiRunning`）→ `POST /usb/handoff/start`
  `{serial, clientId:"jiadian-monitor-<pid>", ttlSeconds:120}` → 拿 `leaseId`
  → 每 20s `POST /usb/handoff/keepalive {leaseId, serial}` → 退出时
  `POST /usb/handoff/finish {leaseId, serial}`。
- **红线**：必须先关 USB 句柄再 `finish`，否则 GUI 会认为设备仍被占用；任何正常退出路径都要归还。
- TTL 120s（管线）；命令行 `--render` 路径用 90s（`lib.rs::cmd_render`）。CLI 不续期也要能跑完。
- 8765 本身只有「状态 / 移交 / 文字 `/live`」，**没有素材下发 HTTP 接口**；写素材要走 USBDL 协议或官方
  `usb_send_gif.exe`。素材作者不需要碰这些。

## 6. 外网 / 实验性调用（**都不在素材链上**）

- 主程序运行时**没有任何出站 HTTP 请求**；面板也不允许自己 fetch（见 §3、§4）。
- 素材里写 `url("https://…")` 这类**静态资源**是允许的，但渲染发生在**上位机所在的电脑**（WebView2），
  不是设备 —— 所以需要的是「电脑能上网」，不是「设备能上网」。
- 实验：`tools/weather-panel/` 的天气面板直连 `https://uapis.cn/api/v1/misc/weather`
  （`Authorization: Bearer <key>`，密钥当前硬编码在源码里，**仅测试**）。
  该接口 CORS 行为：对**真实 Origin 回显** `Access-Control-Allow-Origin`，对 `Origin: null`（`file://`）
  **不回** → 从 `file://` 面板直接 fetch 会被浏览器拦；换个 http origin（如本机静态服务器）才通。
  （2026-11-06 无头 Edge 实测；本次核对时本机外网不可达，未复测。）
- 实验：`tools/proxy_demo.py`（8770）验证 `/proxy/<host>/<path>` 白名单代理，**没有并入主程序**。
  `bin/settings.ini` 里的 `[proxy] hosts=…` 目前只有这个原型会读；主程序的 `Settings` 结构
  **没有 `proxy_hosts`** —— 用户改任何设置时 `to_ini()` 会重写整份 `settings.ini` 把该段抹掉。
  将来若要正式实现，必须按设置项「五处同步」（结构 / `from_map` / `to_ini` / `to_json` / `apply_patch`）。
- 实验：把面板改为 `http://127.0.0.1:8766/assets/...` 加载（同源化）**尚未实现**；
  8766 目前是手写的串行 JSON 服务器，没有静态文件路由 / MIME / 并发能力。

## 7. 怎么核对（只读，不碰设备）

```bash
# 8766 概览与指标
curl -s http://127.0.0.1:8766/
curl -s http://127.0.0.1:8766/version
curl -s http://127.0.0.1:8766/metrics
curl -s http://127.0.0.1:8766/peripherals
# 本机 CLI（等价数据，不用开界面）
jiadian-monitor.exe --dump-metrics
jiadian-monitor.exe --peripherals-dump
# 官方上位机状态（只读）
curl -s -X POST http://127.0.0.1:8765/usb/status -H 'Content-Type: application/json' -d '{}'
# 当前渲染页面（CDP）——能看到真实的 file:// + ?__api= 地址
curl -s http://127.0.0.1:9333/json/list
```

## 8. 对素材作者的约束（从上面结论直接推导）

1. **本地素材**不写 `fetch` / XHR / WebSocket；真机数据只经 `__setSlot` 进来。
   （**在线素材相反**：必须自己 `fetch`，见 §4.1 与 `references/online_hosting.md`）
2. **本地素材**不解析 `location.search` 里的 `__api`，也不假设回环一定是 `127.0.0.1`。
   （**在线素材必须**解析 `__api` —— 端口会变，且上位机会重写这个参数）
3. 数据节奏是「指标 ~1s、外设 ~3s」；不要做需要每帧新数据的高频动效。
4. 读不到时按 `—` 设计（`cpu_load` 及 P/E 核、外设 `_pct`），**绝不把未知当 0**。
5. 文本槽（`cpu_name` / `gpu1_name` / `<类别><n>_name` / `_status`）不要配数值属性。
6. 不新增数据通道、不引用未在 `references/metrics.md` 出现的槽名。

## 9. 源码索引（行为出处）

| 行为 | 源码 |
|---|---|
| 注入脚本 / 外设映射 / 单位换算 | `app/src-tauri/src/pipeline.rs`（`pull_js`、`applyPeri`、`panel_url`、`file_url`） |
| 抓帧节奏 / 静止退避 / 差分 | `app/src-tauri/src/pipeline.rs`（`INTERVAL_HIGH/NORMAL/IDLE`、`IDLE_AFTER=3`、`Page.captureScreenshot`） |
| LIVE 帧格式（mode 0/1/2，LZ4 预留未启用） | `app/src-tauri/src/live_frame.rs`、`diff.rs` |
| 8766 路由 / 响应头 / 基址 | `app/src-tauri/src/api.rs` |
| 8765 移交 | `app/src-tauri/src/handoff.rs`、`pipeline.rs`（keepalive） |
| 指标组装 / 文本槽 / P/E 核 | `app/src-tauri/src/metrics.rs`、`source_lhws.rs` |
| 单位设置 | `app/src-tauri/src/units.rs` |
| 主题扫描 / 尺寸推断 / 清单兜底 | `app/src-tauri/src/assets.rs`（`declared_size` 先 CSS、再 manifest `size`） |
| 外设快照 / 轮询 / 状态机 | `app/src-tauri/src/peripherals/`（`mod.rs::json`、`poll_ms`） |
