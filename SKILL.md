---
name: jiadian-monitor-skills
description: Generate and validate single-file HTML materials for small embedded RGB565 panels (320x240 / 320x170) driven by an offscreen-browser + frame-diff streaming pipeline. Covers the material contract (fixed viewport, data-slot placeholders, __setSlot injection entry, background conventions), an embedded machine-readable manifest plus a JSON check report so downstream programs can scrape results, a self-contained checker (static A1-A19 + headless runtime B1-B7), the real local-API call map (8766 injection / 8765 USB handoff), the two delivery modes (local file with app-injected data, or an online page hosted on https/LAN that fetches the local API itself), and the full pitfall list. Use when asked to 生成/设计/排版 一块监控面板或仪表盘素材 for an embedded screen, 校验/自检 素材是否合规, review a panel HTML for contract, alignment or readability problems, 做一个托管到云端或局域网的在线面板, or build a library of panel styles. Do NOT use for previewing/rendering screenshots, for the streaming or delivery pipeline, or for general web pages.
agent_created: true
---

<!--module
id: skill
title: 技能入口
owns: 技能的加载入口与导航 · 端到端工作流编排
not_owns: 能力的定义与边界 · 主项目链路 · 素材的形态契约 · 检查项与判据 · 机器可读格式 · 风格取舍
rendering: 入口级：把「约束渲染条件」拆到各环节（生成前约束 / 静态闸门 / 运行时闸门），并指明每环节由谁判
see: references/capability.md
-->

# 佳点监控面板素材（本地 / 在线）：生成与验证

给**小尺寸嵌入式 RGB565 屏**（320×240 / 320×170 点阵屏）生成单文件 HTML 素材，并验证它是否合规。

素材 = 一块跑在上位机**隐藏 WebView2** 里的 HTML 面板。上位机定期抓帧 → 差分 → 只把**变化区域**推给屏。

**数据从哪来**：上位机从**本机硬件传感器**（LibreHardwareService）读数据、换算成指标，开一个**本地 API**
（`http://127.0.0.1:8766`）；渲染面板时**自动往页面注入**一段脚本，启动后每秒并发拉
`/metrics`、`/units`、`/peripherals`，对每条 `{key, value}` 调 `window.__setSlot(key, …)`。
**面板不用自己取数**，只要实现 `__setSlot` + 用**真名** `data-slot`（`cpu_load` / `gpu1_temp`…，
见 `references/metrics.md`）。其中 `cpu_name` / `gpu1_name` 是**文本槽**（精简型号 `9700X` / `5070Ti`），
直接当文字用；数值槽拿到的是**数字字符串**，由素材的 `data-fmt` / `data-suffix` 负责显示。
刷新节奏：**指标数据 ~1Hz、外设电量 ~3s 一轮**；抓屏/下发按页面变化触发，
两档目标帧率（高刷 33ms≈30fps / 普通 100ms≈10fps），连续 3 帧没变化再降到 ~3fps。
**真实调用关系（谁在调谁、每次拉什么、失败怎么办）** → `references/api_map.md`。

**两种交付形态 —— 开工前必须先问是哪一种**（`references/online_hosting.md`）：

| | **本地素材**（local，默认） | **在线素材**（online） |
|---|---|---|
| 形态 | 一个 `.html` 文件，放进 app 的 `assets/<主题>/v1p|v2/` | 一个能独立打开的页面，**托管在云端或局域网**（https / 私有地址 http） |
| 取数 | 上位机**注入**脚本，每秒调 `__setSlot` | 页面**自己** `fetch('http://127.0.0.1:8766/metrics')`（app 不注入） |
| `__setSlot` | **必须实现**（C4） | **不要求**（实现了就能同时当本地素材用） |
| 底图/资源 | 单文件；ⓑ 只能同目录文件名 | 可多文件、可相对路径引用；**不能** `file://` 或盘符绝对路径 |
| 交付到哪 | 拷进 `assets/` | 填 URL 进 app 的「在线」页（`online/<slug>.toml`） |
| 自检 | `check_material.py x.html` | 同上，加 `--mode online`（多查 A16–A19） |

> 其余约束（视口锁死、`{{}}`↔`data-slot`、视觉下限、变化面积）**两种形态完全一样** ——
> 因为下游是同一条抓帧 → 差分 → USB 链路。**云端只托管静态页面，数据始终留在本机。**

**第二条通道：外设电量**。同一段注入脚本还会拉 `http://127.0.0.1:8766/peripherals`，
把鼠标 / 键盘 / 耳机 / 手柄的电量映射成 `mouse1_pct` / `kbd1_pct` / `headset1_pct`…
（外加 `_name` 型号、`_status` 文本状态、`peri_count` 台数），喂进**同一个** `__setSlot`。
面板侧仍然**不用写 fetch**。五条必须知道的边界：

- **读不到就是 `—`，不是 0**：`_pct` 可能是字符串 `—`（品牌没收录 / 协议档位不匹配 / 设备离线），
  `parseFloat` 后当 0 会把「不知道」画成「没电了」。这和 `cpu_load` 的 `—` 是同一条约定。
- **`_status` 是文本槽**（`充电中` / `放电中` / `离线` / `未支持` / `未连接` / `—`）：
  不配 `data-fmt` / `data-warn` / `data-danger` / `data-suffix`；充电状态**按文本判等**，别从 `_pct` 反推。
- **3 秒一轮、编号会变**：别做高频动效（没有新数据可跟）；插拔会让同类编号前移，只画第一个就用 `mouse1_*`。
- **`_name` 用的是型号/品牌，不是界面里改过的显示名**：v0.9.1 支持在外设页给设备改名，
  但注入槽仍是 `model || brand`，改名不会进素材；要显示自定义名就得等协议扩展。
- **取不到 ≠ 清空**：单次请求失败会保留上一轮读数（不闪 `—`），只有设备真的从快照消失才把对应槽清成 `—`。

外设电量的数据来源是**配置 + 设备协议**（`index.toml` 做 PID→品牌索引，`brands/<品牌>.toml` 存协议帧），
不是系统电量 API —— 所以"有些设备就是读不到"是常态，画面上要能容下 `未支持` / `离线` 这两个状态。
参考骨架见 `assets/verified_materials/p14_peri_dark.html`（深色）/ `p15_peri_light.html`（浅色）/
`p16_peri_terminal.html`（终端风）。

所以素材的目标不是"网页好看"，而是**在这条链路约束下好看且稳定**：视口锁死、数据可注入、
每帧变化面积小、文字在低分辨率下真能看清。

## 边界：这个技能做什么 / 不做什么

| | |
|---|---|
| ✅ **做** | **生成**素材（写 HTML）· **验证**素材（静态契约 + 运行时行为） |
| ✅ **做** | **定义产物格式** —— 素材内嵌机器可读清单 + 自检 JSON 报告（下游程序直接抓） |
| ❌ **不做** | **预览 / 截图 / 渲染出图** —— 交给别的环节 |
| ❌ **不做** | 抓帧、差分、协议、USB 下发、设备交互 —— 那是上位机的事 |
| ❌ **不做** | 普通网页 / 桌面端界面 |

**零外部依赖**：整个技能目录可以拷到任何地方用。验证脚本只用 Python 标准库；
只有"运行时验证"那一层需要本机有个 Edge / Chrome（理由见第三节）。

**完全不碰设备**：全程只读你的 HTML 文件 + 可选地开一个无头浏览器读 DOM。

---

## 一、开工前必问（**多问，别猜**）

宁可多问一轮，也不要猜着做。开工前用**一组选择题**一次问清（别一句句挤牙膏）：

0. **先问交付形态：本地素材，还是在线素材？**（对照表见开头）
   - **本地素材**（默认）：交付一个 `.html`，拷进 app 的 `assets/<主题>/v1p|v2/`；数据由上位机注入。
   - **在线素材**：交付一个**能托管出去**的页面（云端 https / 局域网私有地址），页面自己 `fetch` 本机 API；
     交付物是 **URL**，填进 app 的「在线」页。
   - 判据：对方说「托管 / 云端 / 网址 / 远程更新 / 不想每次拷文件」→ 在线；只说「做个面板」→ 本地。
     拿不准就**默认本地**并说明「要托管的话页面写法要加取数代码（C9–C12）」。
   - 两种形态的**画面约束完全相同**，只有取数与资源引用不同（见 2.6 与 `references/online_hosting.md`）。
1. **要监控哪些传感器？分辨率是多少？** —— 没给就必须问。
   **数据槽只能从 `references/metrics.md` 里挑**（那本字典就是「该用哪些传感器」的权威清单），
   或直接从上位机 exe 的 `--dump-metrics` 输出里挑（**别手打**，拼错会静默失效；
   原先「预览界面一键复制占位符」的 UI 目前已不在界面里，以 CLI / `references/metrics.md` 为准）。
2. **风格偏好？**（深色 / 浅色 / 某种具体风格）—— 没给就问，或给 2–3 个候选让对方挑。
3. **背景底图走哪种？**（**三选一，必须问**，见下）
4. **动效偏好？**（完全静态 / 轻微呼吸感 / 扫描线之类）
5. **有没有品牌色、或必须避开的颜色？**
6. **要不要画外设电量（鼠标 / 键盘 / 耳机）？** —— 要画就点名要哪几类（`mouse*` / `kbd*` / `headset*`），
   并提醒对方「读不到时显示 `—` / `未支持`」这个状态在画面里必须留位置
   （本机到底认到哪些设备：`jiadian-monitor.exe --peripherals-dump`）。

### 背景底图：只有三种，必须让用户选

不要自己默认某一种。给出三个选项，让对方选：

| 选项 | 写法 | 说明 |
|---|---|---|
| **ⓐ 纯 CSS**（推荐默认） | `linear-gradient` / `radial-gradient` / `repeating-linear-gradient` | **不引任何文件**，最省事、最可控、最不容易出错 |
| **ⓑ 本地文件** | `url("bg.png")` | 图片与 HTML **放在同一目录**，只写文件名相对引用 |
| **ⓒ 在线 URL** | `url("https://example.com/bg.png")` | 直接写完整 URL（渲染在上位机所在电脑，**电脑要能上网**，不是设备联网） |

**ⓑ 的硬规则**：只写「文件名」，图片与 HTML 同目录（放进 app 的 `assets/` 时也是同一层）。
❌ 不许写盘符（`C:\...`）、❌ 不许写绝对路径、❌ 不许 `..` 往上层跑、❌ 不许 `file:///`、❌ 不许另建子目录。
**选了 ⓑ 但没有对应的图片文件 → 先问用户，不要自己编一个路径。**

选定后**在交付说明里写明用了哪一种**，并如实写进产物清单的 `background` 字段
（`css` / `local` / `url`）—— 自检 **A13** 会拿它和素材实际用法交叉校验。

---

## 二、生成：怎么写一块素材

### 2.1 八条硬性契约（违反即返工）

| # | 约束 | 说明 |
|---|---|---|
| C1 | **单文件** | 一个 `.html`，CSS/JS 都在里面；可引外部 CDN / 字体；不得残留本机路径 |
| C2 | **视口锁死 `W×H` 贴左上** | 样式表**最前面**写一条**同时声明宽高**的规则块（工具据此推断视口）；禁止居中 |
| C3 | **动态文字用 `{{名字}}` + 同名 `data-slot`** | 静态文字直接写死、**不加** `data-slot` |
| C4 | **实现 `window.__setSlot(name, value)`** | 上位机**自动注入的自取脚本**调它喂真值；`data-slot` 用真名（`cpu_load`…），别自造 |
| C5 | **不注入也有完整画面** | 页面自带默认值，不能白屏 |
| C6 | **每帧变化面积 ≤ 画布 10%** | 唯一性能杠杆；禁止整屏持续动画 |
| C7 | **内嵌产物清单块** | `</body>` 前放 `<script type="application/json" id="material-manifest">`，让下游程序直接抓槽位 |
| C8 | **样式全自控（A15）** | 屏上每个像素都得由素材自己的 CSS 决定。原生控件（`button` `input` `select` `textarea` `progress` `option` `ul` `ol` `dl` `h1`–`h6` `a` `table` `fieldset` `pre` `hr`）**要么不用**（`div`/`span` 自绘），**要么在样式里显式接管**（`appearance:none` + `background` + `border` + `font-family`…）；出现却未接管 = A15 FAIL |

> **C8 的来源**：深色面板里放一个没接管的 `<select>`，展开瞬间是纯白底（RGB565 上像闪光灯）；
> `<a>` 不接管就是 UA 蓝链 + 下划线，在霓虹 / 磷光主题里彻底出戏。现有 18 套内置主题
> （其中 16 套已收进 `assets/verified_materials/` 作为回归样例）全部用 `div`/`span` 自绘，原生控件数为 0 —— **这是默认做法，不是特例**。


最小骨架：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  html, body { margin:0; padding:0; width:320px; height:240px;
               overflow:hidden; display:block; background:#101a2a; }
  #stage, #img, #render, #text { position:absolute; left:0; top:0; width:320px; height:240px; }
  #img { z-index:1; } #render { z-index:2; } #text { z-index:3; }
  .txt { position:absolute; line-height:1; white-space:nowrap; font-variant-numeric:tabular-nums; }
</style>
</head>
<body>
<div id="stage">
  <div id="img"></div>
  <div id="render"></div>
  <div id="text">
    <span class="txt" data-slot="v1" style="left:20px;top:20px;"
          data-fmt="0" data-suffix="%" data-warn="75" data-danger="90">{{v1}}</span>
  </div>
</div>
<script>/* 见 assets/material_prompt.md 附录的 __setSlot 参考实现 */</script>

<!-- C7：产物清单块。放在 #stage 之外，别手写 —— 用 --emit-manifest / add_manifest.py 派生 -->
<script type="application/json" id="material-manifest">
{ "schema": "rgb565-panel-material/1", "name": "my_panel", "size": [320, 240],
  "background": "css",
  "slots": [ { "name": "v1", "kind": "text", "warn": 75, "danger": 90, "fmt": 0, "unit": "%" } ] }
</script>
</body>
</html>
```

> 完整契约、`data-*` 字段表、可直接照抄的 `__setSlot` 脚本 → `references/contract.md`
> 产物清单与自检报告的字段表 → `references/output_format.md`

### 2.2 `data-*` 字段速查

| 属性 | 用在哪 | 含义 |
|---|---|---|
| `data-slot="v1"` | 任何会变的东西 | 注入用的名字，与 `{{v1}}` 同名 |
| `data-fmt="0"` | 文本槽 | 保留小数位 |
| `data-group="1"` | 文本槽 | 千分位分隔 |
| `data-suffix="%"` | 文本槽 | 单位后缀。**用了它就别再放静态单位元素** |
| `data-warn` / `data-danger` | 文本槽 / 条 | 阈值，切 `.warn` / `.danger` 类；**`danger ≥ warn`** |
| `data-kind="bar"` | 条 | 连续宽度条（可扩展 `ring` / `heat` / `led` 等） |
| `data-from="v1"` | 条 | 跟随哪个文本槽 |
| `data-max="100"` | 条 | 满值 |
| `data-box="x,y,w,h"` | 条 | 条的可用区域，**必须与元素实际 `left/top/width` 对得上** |

### 2.3 视觉下限（写的时候就该做对）

- **数值右对齐**：成列数值用 `right:` 锚定右边缘。**边界**：页脚"标签后紧跟一个孤立读数"左锚定可以。
- **单位紧跟数值**：间距固定；能合成一个串就用 `data-suffix`。
- **同行基线对齐**：标签 / 数值 / 单位的 `top` 落在同一条线上。
- **不重叠**：文字×文字、文字×装饰条都不许压；**10px 字两行 `top` 至少差 11px**。
- **字号下限**：正文 ≥11px、次要 ≥10px、**中文一律 ≥11px**。
- **对比度 ≥6:1**（硬线 4.5:1）：判据是文字色 vs **它底下真实的底色**。
- **文字不压装饰图案**；从图案上挪开时**记得同步改颜色**。
- **浅色底别太白**：平均亮度 ≳80% 会拖垮供电/链路 → 用中灰 / 暖灰 / 冷灰底（实测 67~76% 安全）。

### 2.4 性能

唯一杠杆 = **每帧变化的像素面积**，目标 ≤ 画布 10%。
动效只做"小范围 + 低频"（数字 / 细条 / 光点 / 状态灯 / 单格变色）；
禁止整屏持续动画。**页面自身不带动画、只在数据变化时重绘是完全正确的** ——
不要为了"凑帧率"强加持续动画。

### 2.5 产物清单（机器可读，**别手写**）

交付的素材要能被下游程序**直接抓取**，所以 `</body>` 前必须有一块惰性 JSON：

```html
<script type="application/json" id="material-manifest">{ "schema": … }</script>
```

- 位置：**`#stage` 之外**、`</body>` 之前（它是**数据不是画面**，别混进画面树）；
  `type="application/json"` 保证浏览器**不执行**它，纯数据。
- 内容：`schema` / `name` / `size` / `background`（`css`|`local`|`url`）/ `slots[]`；
  每个 `data-slot` 一条，字段与素材上的 `data-*` **必须一致**。
- **派生，不手抄**（手抄必漂移）：

```bash
python scripts/check_material.py my.html --emit-manifest   # 打印清单块，粘进 </body> 前
python scripts/add_manifest.py my.html                     # 或者直接就地回填/刷新（幂等）
```

> 完整字段表、`--json` 报告 schema、退出码 → `references/output_format.md`
> 清单块缺 / 漏槽 / 字段不符 → 自检 **A13 FAIL**。

### 2.6 在线素材：C9–C12（托管出去的那一种）

C1–C8 在两种形态下**全部照旧**（单文件、视口、占位符、清单块、视觉下限都是同一条链路的要求）。
在线形态额外多四条 —— 因为**没有注入脚本替页面取数**：

| # | 约束 | 说明 |
|---|---|---|
| C9 | **页面自己取数** | app 不注入。页面读 `?__api` 拿端口（缺省 8766），并发拉 `/metrics` `/units` `/peripherals`，约 1s 一轮、单请求 4s 超时（`AbortController`）。数值槽传数字字符串、文本槽传字符串 |
| C10 | **可托管** | 资源引用只能是**相对路径**或 `https://`；❌ `file://`、❌ 盘符/本机绝对路径、❌ `..` 跑出站点根。托管地址必须 https 或局域网私有地址 http（公网 http 被拒） |
| C11 | **失败可见 + 不越权** | 取不到就显示 `—` / `离线`，**不要空白、不要假数据**，恢复后自动继续；不调控制接口 `/app/show` `/app/quit`（403）；页面里不放密钥、不引不可信第三方脚本；设了 CSP 必须放行 `connect-src 'self' http://127.0.0.1:8766` |
| C12 | **一份代码两种模式（推荐）** | 仍实现 `window.__setSlot` + `data-slot`，并把取到的数据喂给同一个渲染函数 → 同一份页面在本地模式也能直接跑。不实现也合法（自检只降级为 WARN） |

最小取数骨架（放进页面自己的 `<script>`，替代本地模式的注入脚本）：

```html
<script>
(function () {
  var port = new URLSearchParams(location.search).get('__api') || '8766';
  var base = 'http://127.0.0.1:' + port;
  var SLOTS = { cpu_load: 'pct', cpu_temp: 'temp', mem_pct: 'pct' };  // 只列真用到的
  function put(k, v) { if (window.__setSlot) window.__setSlot(k, v); else draw(k, v); }
  function tick() {
    var ac = new AbortController(), t = setTimeout(function () { ac.abort(); }, 4000);
    fetch(base + '/metrics', { signal: ac.signal })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        (d.metrics || []).forEach(function (m) {
          if (SLOTS[m.key]) put(m.key, String(m.value));   // 数值槽一律字符串
        });
      })
      .catch(function () { ['cpu_load', 'cpu_temp', 'mem_pct'].forEach(function (k) { put(k, '—'); }); })
      .then(function () { clearTimeout(t); });
  }
  tick(); setInterval(tick, 1000);
})();
</script>
```

> 完整托管流程（云端 / 局域网 / CSP / 缓存 / LNA 风险）→ `references/online_hosting.md`
> 取数字段与 `_pct` / `_status` 语义 → `references/metrics.md`、`references/api_map.md`
> 自检：`python scripts/check_material.py 页面.html --mode online`（A16–A19）

---

## 三、验证：怎么跑闸门

```bash
# 全部自带参考素材（16 套，应该 16/16 PASS）
python scripts/check_material.py --all

# 单个文件
python scripts/check_material.py path/to/your.html

# 只做静态契约检查（更快；完全不需要浏览器）
python scripts/check_material.py path/to/your.html --no-render

# 报告输出为机器可读 JSON（下游程序抓这个，而不是解析人读文本）
python scripts/check_material.py --all --json

# 派生产物清单块（粘进素材的 </body> 前）；或直接就地回填
python scripts/check_material.py your.html --emit-manifest
python scripts/add_manifest.py your.html

# 在线素材（托管出去的那种）：在 A1–A15 之外再查 A16–A19
python scripts/check_material.py path/to/online.html --mode online

# 有视觉能力就自己截图看一眼（闸门 4 只能看，不能算）
python scripts/screenshot.py your.html            # → out/your.png
python scripts/screenshot.py your.html --scale 2   # 小字更清楚
python scripts/screenshot.py --all --size 320x170   # V1P 全量

# 指定浏览器（默认自动找 Edge / Chrome）
python scripts/check_material.py your.html --edge "C:\Program Files\...\msedge.exe"
```

### 两层验证，各查什么

| 层 | 需要什么 | 查什么 |
|---|---|---|
| **静态契约 A1–A15**（在线形态另加 **A16–A19**） | 只要 Python | 尺寸能否推断、禁居中、`{{}}`↔`data-slot` 闭环、`data-from` 引用有效、条必备字段、`data-box` 格式与越界、id 重复、半像素、`absolute` 缺 `left/top`、元素越界、DOCTYPE、**产物清单块是否齐全自洽**、**原生控件是否被样式接管（A15）** |
| **运行时行为 B1–B7** | Python + 本机浏览器 | `__setSlot` 存在、逐槽注入 `0/50/100/999` 不抛错、无残留占位符、内容包围盒、元素重叠、字号、**文字对比度** |

> **运行时那层为什么要浏览器**：`B2`（注入不抛错）、`B5`（重叠）、`B6`（字号）、`B7`（对比度）
> 都必须在**真实布局**下量 —— 尤其是 `B7`，它要取文字中心点、用 `elementsFromPoint`
> 把逐层底色按 alpha 合成出真实底色，再算 WCAG 比值。纯静态文本分析做不到。
>
> ⚠️ **这不是预览**：它把 DOM `--dump-dom` 回读出来做断言，**不产出任何图片、不做视觉呈现**。
> 预览/截图是另一个环节的事。若连浏览器也不想开，加 `--no-render` 只跑静态层。

### 有视觉能力，就自己截图看（**该做，不是可选**）

机器判据只覆盖**坐标级**问题（越界 / 重叠 / 字号 / 对比度 / 清单自洽）；
**"坐标都对但看着别扭"只能看**。所以：

- **如果你的模型能读图**（支持视觉输入）：交付前**必须**自己截图、自己看图、自己改，
  把闸门 4 的五条（主题 / 数据来源 / 中英混用 / 多样性 / 层级）逐条过一遍。
  ```bash
  python scripts/screenshot.py your.html --scale 2   # 出图 → 再用看图能力读 out/your.png
  ```
  截图**不注入数据**（与闸门一致），看到的是默认值；想验某个数值就 `--param cpu_load=57`。
- **如果不能读图**：**明说"闸门 4 我没法自判"**，把 `references/self_check_gates.md` 的 4.1–4.5
  清单连同截图路径一起交给人 —— **不要**假装看过画面。
- 截图是**自检手段，不是交付物**；本技能仍然不产出预览图、不做视觉呈现给别人看。

### 四道闸门（与机器编号的对应）

| 闸门 | 查什么 | 机器 |
|---|---|---|
| **1 · 完整性** | 单文件、尺寸声明、`{{}}`↔`data-slot` 闭环、`__setSlot` 存在 | A1 A2 A4 B1 |
| **2 · 格式与规格** | 命名唯一、引用有效、条必备字段、`data-box` 自洽、阈值语义、单位不重复、定位与整数坐标、不越界、**产物清单块齐全自洽**、**原生控件样式自控** | A5–A11 **A13 A15** |
| **3 · 运行时行为** | 注入不抛错、无残留占位符、不重叠、字号、对比度、动态面积 | B2–B7 |
| **2·b 在线形态** | 页面自己取数、资源可托管、失败可见、不越权 | **A16–A19**（`--mode online`） |
| **4 · 内容与主题一致性** | 主题对得上、每个槽有真实数据来源、中英混用统一、明暗分布与多样性、信息层级 | **看**（机器查不了）：模型有视觉就自己截图判，没有就交给人 |

> 闸门 4 需要**看着画面**做：模型能读图就 `scripts/screenshot.py` 自己截、自己判；
> 不能读图就明说没判，把清单和截图路径交给人。逐条明细 → `references/self_check_gates.md`

### 三态判定

- **PASS** → 允许交付。
- **WARN** → 只命中建议项（如 10px 中文、对比度 4.5~6:1）→ **可交付但必须记录在案**，
  下一轮统一处理；**不允许当成 PASS 吞掉**。
- **FAIL** → 就地修复 → **重跑整份清单**（不是只重跑失败那一项）；
  连续 2 次仍失败就**停下来问人**，不要靠放宽阈值让它变绿。

---

## 四、完整坑表（现象 → 原因 → 修法）

全是真实踩过的。按"能不能跑"→"能不能看"→"风格落地"→"调试验收"四组排。

### A. 能不能跑（契约类，机器能抓）

| 坑 | 原因 | 修法 |
|---|---|---|
| **占位符与 `data-slot` 拼错** | `{{v1}}` 与 `data-slot="v2"` 对不上；注入时 `querySelector` 找不到元素，**静默失败** | 逐个比对名字 —— 它**不报任何错**，只会"数字永远不变"，最容易被误判成链路问题 |
| **尺寸只声明一半** | 工具按"第一个**同时**含 width+height 的样式块"推断视口，缺一个就推断失败、回落到默认尺寸 | 补全并放到样式表最前面 |
| **`position:absolute` 漏 `left/top`** | 绝对定位元素没有偏移量，全部落在静态位置 `(0,0)` | 每个绝对定位元素都写 `left`/`top`（或用 `right`/`bottom`） |
| **元素有 `left/top` 但容器没尺寸** | 父容器没有 `width/height` → 子元素撑不开，整块塌成 0×0 | 给容器显式尺寸。这类只有截图或包围盒检查才发现 |
| **`bottom:0` 相对错了祖先** | `bottom`/`right` 相对**最近的非 static 祖先**算；放进整块画布高的容器，它就会横跨全屏 | 让该元素自己的容器有正确高度，别挂在整块画布上 |
| **`data-box` 与实际坐标不一致** | `data-box` 是条的**可用宽度**，与元素 `width` 不一致 → 条撑出框或永远填不满 | 让 `data-box` 与元素实际的 `left/top/width` 对齐 |
| **`danger < warn`** | 判据是 `v >= warn` 且 `v < danger` 才切 warn，`v >= danger` 切 danger；写反了 danger 分支永远进不去 | 保证 `data-danger ≥ data-warn` |
| **`data-suffix` + 静态单位并存** | `suffix` 是运行期拼上去的，静态单位不会自动让位 → `63%%` | 二者只留一个 |
| **URL 参数不生效** | 脚本里必须**先给默认值、再用 URL 覆盖**；顺序反了默认值会把参数盖掉 | 调整脚本顺序 |
| **999 把条撑出框** | 条宽没做 `clamp(0,1)`，极端值溢出 | 条宽 = `clamp(值/上限, 0, 1) × data-box 宽度` |
| **轨道类名不叫 `.bar-track`** | 部分检查器按**类名**放行"条压在自己轨道上"；换个名字就被判成重叠 | 轨道统一用 `.bar-track` —— **类名是契约的一部分** |
| **装饰元素越界** | 越界检查量的是 `getBoundingClientRect`，**哪怕视觉上被裁掉也算失败** | 装饰光斑/斜纹也要完整落在画布内 |
| **页面崩溃 → 拿不到验证结果** | 首屏 JS 抛异常或语法错误，注入脚本跑不起来 | 看浏览器控制台；先保证首屏不报错 |
| **清单块漏槽 / 字段与素材不符** ⭐ | 手抄清单，改了素材没改清单 → 下游按清单推数据，**推到一个不存在的槽上，静默失效** | **别手写**：`--emit-manifest` 或 `add_manifest.py` 派生。A13 会交叉校验 |
| **清单块 `type` 写错（如 `text/javascript`）** | 浏览器会**执行**它 → 报语法错，或把 JSON 当 JS 跑 | 必须 `type="application/json"` —— **A13 会判** |
| **清单块放进了 `#stage`** | 它是**数据不是画面**；`#stage *` 这类选择器会把它一并选中，语义也不对 | 放在 `#stage` **之外**、`</body>` 之前（A13 查不了，靠自查） |

### B. 能不能看（视觉 / 可读性类）

| 坑 | 原因 | 修法 |
|---|---|---|
| **数值左对齐** | 成列数值用固定 `left` 就是左对齐，位数一变（`8%`↔`100%`）整列参差 | 成列数值改成 `right:` 锚定右边缘。**边界**：页脚"标签后紧跟孤立读数"左锚定可以（右边没有可比对象） |
| **单位与数值脱节** | 单位用固定 `left` 放太远，看着像"没对齐" | 单位紧跟数值右边缘，或直接 `data-suffix` 合成一串 |
| **同行元素不齐** | 同行的标签/数值/单位 `top` 没对齐 | 按视觉中心（`top + 行高/2`）对齐 |
| **文字压在装饰图案上** | 条纹带/网格上的字对比度被图案吃掉 | 把文字移出图案区，或给文字加**实底** |
| **挪开文字却忘改颜色** ⭐ | 从浅色带挪到深底时漏改 `color`，仍是给浅底准备的深色 | **挪位置和改配色必须一起做**。实测：深褐 `#1a1a10` 压在 `#0a0a08` 上只有 **1.1:1**，等于没有 |
| **中灰底上次级文字不够深** ⭐ | 对比度要吃**真实底色**：同一个 `#3a4a5a` 在白底绰绰有余，在中灰底只剩 4.5:1 | **中灰底最坑**，次级文字必须压更深。别用"深底/浅底"二分来估 |
| **亮饱和色直接当文字色** ⭐ | 招牌红 / 霓虹色本身亮度不够，在灰底上普遍只有 3.6~5.8:1 | 要么按底色**提亮/压深**，要么让亮色**只做规则线 / 色块**这类非文字元素 |
| **10px 中文粘连** ⭐ | 汉字笔画密度远高于拉丁字母，10px 时笔画糊在一起（同行的英文还很清楚） | **中文一律 ≥11px**，10px 只留给英文/数字 |
| **两行文字纵向叠上** ⭐ | 10px 字两行 `top` 只差 8px → 纵向叠 2px；而"包围盒相交 > 2px"这种宽松判据**刚好放过** | 文字×文字要判严：**基线框一挨上就报**；两行至少差 11px |
| **浅色底太白** | 平均亮度 ≳80% 拖垮供电/链路 | 用中灰 / 暖灰 / 冷灰底（实测 67~76% 安全） |
| **装饰性元素没有信息含义** | 放了个"看着莫名其妙"的角标/光点 | **没有明确信息含义的装饰就不要放** |

⭐ = 影响最大、最容易复发的几条。

### C. 风格落地类

| 风格 | 坑 / 取舍 |
|---|---|
| **玻璃拟态** | ❌ 别指望 `backdrop-filter` —— 面板在隐藏/离屏 WebView2 里渲染（CLI 预览路径还带 `--disable-gpu`），它不保证生效，还可能把重绘面积拖大。✅ 改用「分层半透明 + 高光描边 + 柔和外阴影 + 背景光斑」合成 |
| **新拟物** | 需要同色系中灰底才出双阴影；但底色越浅越危险。用 `#b9c0c9`~`#bcc3cc` 一档 |
| **瑞士国际主义** | 招牌亮红在灰底上只有 3.6:1 → **红只做规则线 / 色块，不进文字** |
| **赛博霓虹** | 原味品红 `#ff2e97` 在近黑底上 5.8:1 → 提亮成 `#ff5fae` 得 7.1:1 |
| **圆环仪表** | 用 `conic-gradient` + **内圆挖孔**（叠一个同底色实心圆），**不要依赖 CSS `mask`** |
| **热力矩阵** | 五档底色配白字，**每档都要单独过 6:1**（浅档尤其容易不达标） |
| **服务器机架** | 状态灯可**直接复用阈值类**（`.led` / `.led.warn` / `.led.danger`），不必另写逻辑 |
| **绿色磷光终端** | 段式进度条用 `repeating-linear-gradient` 拼"格子"，比真写 ASCII 字符更省事也更稳 |

### C2. 外设电量类（`/peripherals`，14–16 三套参考）

| 坑 | 原因 | 修法 |
|---|---|---|
| **`—` 被当 0 画** ⭐ | `_pct` 是字符串 `—`，`parseFloat('—')` 得 `NaN`，随手兜底成 0 就变成"0% 没电" | `__setSlot` 里**先判非数字**，非数字原样写 `—`、条宽置 0 但**不显示 0%**。与 `cpu_load` 同一条约定 |
| **只画大百分比不画状态** | 电量 3 秒一轮、无线设备会睡；只给数字会让人以为那是实时值 | `_pct` 与 `_status` **成对显示**；`离线` / `未支持` / `未连接` 都要留位置 |
| **从电量数值反推充电** ⭐ | 充电时电量为占用值、且各品牌语义不同，反推必错 | 充电状态**只看 `_status === '充电中'`**；`_pct` 只当百分比 |
| **按 `mouse1` 写死"这是哪只设备"** | 编号按快照顺序（品牌+型号排序），插拔会前移 | 只画一台就用 `mouse1_*`，但文案写"鼠标"而不是写死型号；型号要用 `_name` |
| **给 `_name` 假定长度** | 型号名从 `VGN S99` 到 `Rapoo Gaming Device` 差 3 倍 | 给足宽度或省略号；不要靠"名字短"来算排版 |
| **给 `_status` 配 `data-fmt`/`data-warn`** | 它是文本槽，不是数值 | 文本槽不配数值属性；充电图标按文本判等 |
| **按"系统电量 API"设计画面** | 数据源其实是 `index.toml` + `brands/<品牌>.toml` 的协议帧，读不到是常态 | 默认假设"能读到一部分设备"，画面必须容得下未支持状态 |

### C3. 在线形态类（托管出去的页面）

| 坑 | 原因 | 修法 |
|---|---|---|
| **画面正常、数据永远不动** ⭐ | 页面设了 CSP 没放行本机接口（`connect-src`），fetch 被拦；控制台是 `Refused to connect` | CSP 加 `connect-src 'self' http://127.0.0.1:8766`（A18 会提示） |
| **`Failed to fetch`、无任何报错** ⭐ | 浏览器 LNA（Local Network Access，原 PNA）把「公网 origin → 127.0.0.1」拦了，或被降级成 preflight 失败 | 见 `references/online_hosting.md` §LNA；局域网部署时整站同源 http 更稳 |
| **端口写死 8766** | 8766 被占时上位机会重试到 10013 等端口，页面还打旧端口 | 必须读 `?__api`：`new URLSearchParams(location.search).get('__api') || '8766'`（A16 判） |
| **本机打开正常、托管后 404/白屏** | 资源写成盘符或绝对路径（`C:\\bg.png`、`/assets/x.png`），本机 `file://` 恰好能取到 | 一律相对路径；❌ `file://`、❌ 盘符、❌ `..` 跑出站点根（A17 判） |
| **`/metrics` 失败把 CPU 画成 0%** | 同 C2 的 `—` 约定：网络失败 ≠ 空载 | 失败写 `—`、条宽 0 但**不显示 0%**；恢复后自动继续 |
| **同时被注入又自己取数** | 页面既自取又被 app 注入（当本地素材用时），两路同时写槽 | 自取代码加 `if (location.protocol !== 'file:')` 守卫 —— 本地模式是 `file://`，在线是 `http(s)`，一份代码两种模式不打架 |
| **页面里放了密钥 / 统计脚本** | 在线页面是公开可读的远程代码 | 云端只放静态页面；数据、密钥、内网地址一律不进页面 |

### D. 调试验收类

| 坑 | 原因 | 修法 |
|---|---|---|
| **素材 bug 误判成链路 bug** | 出问题先怀疑链路，其实是素材本身没写对 | **交付前先过闸门**，把素材问题挡在制作环节之前 |
| **只验包围盒不验区间** | 总包围盒合法 ≠ 元素之间不重叠 | 布局用**区间**核算，靠重叠检测兜底 |
| **只看整体不看单元素** | 单元素溢出画布，总包围盒却正常 | 逐元素量 `rect.right` / `rect.bottom` |
| **抄了"精简版"脚本却不工作** | 压缩/改写脚本时引入语义错误 | 压缩后**必须**用 `B2`（逐槽注入 `0/50/100/999`）验一遍 —— 它是脚本正确性的直接判据 |

---

## 五、参考文件

| 文件 | 什么时候看 |
|---|---|
| `references/metrics.md` | **要选数据槽 / 问用哪些传感器** —— 统一占位符字典（`cpu_load` / `gpu1_temp` … / `mouse1_pct` …）+ 本地 API（`/metrics`、`/units`、`/peripherals`）字段；**写 `data-slot` 只能从这里选** |
| `references/api_map.md` | **要确认「真机上到底谁在调 API / 拉什么 / 失败怎么办」** —— 8766 端点实况、注入脚本每次拉什么、8765 USB 移交；数字不动/数据没来时先看这里 |
| `references/online_hosting.md` | **要做在线素材 / 托管到云端或局域网** —— 托管方式（静态托管、https、CSP、缓存）、取数骨架、`?__api` 端口、LNA 风险与症状、交付清单 |
| `references/contract.md` | 要写契约字段 / 照抄 `__setSlot` / 查 `data-*` 含义 / 底图约定 |
| `references/output_format.md` | 要定**产物格式** / 抓清单块 / 解析 `--json` 报告 / 查退出码 |
| `references/self_check_gates.md` | 要过闸门 / 想知道每条检查的判据与机器编号 |
| `references/style_catalog.md` | 要选风格 / 定配色 / 不确定某风格怎么落地 |
| `references/maintenance.md` | 要改这个技能本身 / 与项目同步 / 查制作坑与安全审计 |
| `assets/material_prompt.md` | 要把"生成素材"这件事交给另一个 AI（**可直接复制的提示词**） |
| `assets/verified_materials/*.html` | 16 套能跑的参考骨架（全部通过闸门，且都带产物清单块；p14–p16 是外设电量专项） |

### 脚本

| 脚本 | 干什么 |
|---|---|
| `scripts/check_material.py` | **自检**（A1–A15 / B1–B7；在线形态 `--mode online` 另查 A16–A19）；`--json` 出机器报告、`--emit-manifest` 出清单块 |
| `scripts/screenshot.py` | **有视觉能力就自己截图看**：按 W×H 出 PNG（`--scale 2` 看小字、`--all` 全量、`--url` 截在线页面、`--param` 模拟数值） |
| `scripts/add_manifest.py` | 给已有素材**回填 / 刷新**产物清单块（幂等） |
| `scripts/sync_base.py` | 从项目刷新自检脚本的**基础部分**（技能专属扩展原样保留） |
| `scripts/describe.py` | 聚合各模块的描述块 + 校验职责边界（D1–D4）；`--md` / `--json` / `--check` |

### 环境要求

- **Python 3.8+**（验证脚本只用标准库）。
- **Edge 或 Chrome** —— 仅"运行时验证"那一层需要；`--no-render` 可完全跳过。
- **不需要联网、不需要设备** —— 全程不碰真机、不产出截图。
