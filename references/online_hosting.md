<!--module
id: online_hosting
title: 在线素材的托管与取数
owns: 在线素材的托管方式 · 页面自取数的写法与字段 · CSP 与局域网访问限制 · 在线交付清单
not_owns: 素材的形态契约 · 检查项与判据 · 机器可读格式 · 主项目链路与端点全表 · 风格取舍
rendering: 在线页面按调用方声明的 W×H 判定（与本地素材同一套判据；自取数不影响渲染）
see: references/contract.md, references/api_map.md, references/metrics.md
-->

# 在线素材：托管与取数

本地素材是「一个 html 文件，拷进 app 的 `assets/`，数据由上位机注入」。
在线素材是「一个**能托管出去**的页面，用 URL 填进 app 的在线页，**数据由页面自己取**」。

> 上位机侧的实现与验收 → `app/ONLINE_MODE.md`（那份是软件文档，这份是给做素材的人看的）

---

## 一、什么时候用在线形态

| 情况 | 用哪种 | 原因 |
|---|---|---|
| 只想快速做一个面板、自己看 | **本地** | 零配置，注入脚本替你取数 |
| 面板要**发出去 / 远程更新** / 多人共用 | **在线** | 改一次页面，所有人刷新就变 |
| 客户自己维护页面、只连你的上位机 | **在线** | 页面归客户，数据留本机 |
| 面板要读本地文件、要跟着 exe 一起发 | **本地** | 在线页面拿不到本机文件 |

**云端托管是最合适的在线形态**：云端只放**静态页面**（没有后端、没有数据库），
数据始终从用户本机的 `127.0.0.1:8766` 取 —— 服务器上不存任何指标，也不做转发。

---

## 二、两种托管方式

### 2.1 云端静态托管（推荐）

任何能放静态文件的托管都行：GitHub Pages、Vercel、Netlify、对象存储（OSS/COS/S3）、
自有 nginx、公司内网静态站。

要求：

1. **必须是 https**（公网 `http://` 会被上位机直接拒绝，见 `app/ONLINE_MODE.md` §2）。
2. **只要静态文件** —— 不需要 Node/PHP/数据库，也不需要任何服务端逻辑。
3. **资源用相对路径**：`./bg.png`、`assets/bg.png` 可以；`C:\bg.png`、`file:///…` 不行（换台机器就 404）。
4. **带缓存版本号**：页面改动后加 `?v=2`（`./style.css?v=2`），否则用户可能看到旧页面。
5. **不要放密钥**：在线页面是公开可读的远程代码，任何 key/token/内网地址都等于公开。

### 2.2 局域网自建

上位机和页面在同一台机器或同一网段时，可以直接用局域网地址：

```bash
# 最省事的自建：把页面放进一个目录
cd panel && python -m http.server 8080
# → http://192.168.1.23:8080/panel.html  填进「在线」页
```

- 局域网 `http://` **允许**（上位机只拒绝**公网** http）。
- 允许的私有地址：`localhost`、`127.x`、`10.x`、`172.16–31.x`、`192.168.x`、`169.254.x`、
  `::1`、`fc00::/7`、`fe80::/10`、`*.local`。
- 局域网自建**不需要 https**，也就绕开了大多数混合内容问题（见 §五）。

---

## 三、页面必须自己取数（C9）

app **不会**给在线页面注入取数脚本 —— 注入脚本是给 `file://` 本地素材用的。
在线页面必须自己在 `<script>` 里轮询本机接口。

### 3.1 三个端点（真实返回形状）

| 端点 | 返回 | 用途 |
|---|---|---|
| `GET /metrics` | **数组** `[{key, value, unit, kind?, text?}, …]` | 硬件指标：CPU/GPU/内存/磁盘/网络/风扇/系统 |
| `GET /units` | `{mode:'auto'\|'manual', units:{capacity,rate,temperature,duration}}` | 单位设置（换算目标） |
| `GET /peripherals` | `{devices:[{category, supported, battery, online, charging, error, brand, model}, …]}` | 外设电量 |

- `kind === 'text'` 的项用 `text`（字符串）；其余用 `value`（数字）+ `unit`。
- 槽名必须从 `references/metrics.md` 的字典里选，**写 `data-slot` 只能从这里选**。
- 外设槽名规则：`mouse1_pct` / `mouse1_name` / `mouse1_status`，键盘 `kbd1_*`、耳机 `headset1_*`、
  手柄 `gamepad1_*`、其余 `peri1_*`，另有 `peri_count`。编号按快照顺序，插拔会前移。

### 3.2 端口：必须读 `?__api`

上位机加载在线页面时会追加 `?__api=<实际端口>`（默认 8766，被占用会重试到 10013 等端口）。
**页面不要写死 8766**，否则端口一变就全屏 `—`。

```js
var port = new URLSearchParams(location.search).get('__api') || '8766';
var BASE = 'http://127.0.0.1:' + port;
```

### 3.3 完整取数骨架（可直接照抄）

```html
<script>
(function () {
  // 本地模式（file://）由 app 注入取数，别自己再拉一遍，否则两路同时写槽
  if (location.protocol === 'file:') return;

  var port = new URLSearchParams(location.search).get('__api') || '8766';
  var BASE = 'http://127.0.0.1:' + port;
  var SLOTS = { cpu_load: 1, cpu_temp: 1, mem_pct: 1 };   // 只列页面真用到的槽
  var CPU = ['cpu_load', 'cpu_load_p', 'cpu_load_e'];

  function put(k, v) { if (window.__setSlot) window.__setSlot(k, v); else draw(k, v); }

  function req(path) {
    var ac = new AbortController(), t = setTimeout(function () { ac.abort(); }, 4000);
    return fetch(BASE + path, { cache: 'no-store', signal: ac.signal })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .catch(function () { return null; })
      .finally(function () { clearTimeout(t); });
  }

  function applyMetrics(list) {
    if (!Array.isArray(list)) {                       // 整轮失败：CPU 三槽清成「—」
      CPU.forEach(function (k) { if (SLOTS[k]) put(k, '—'); });
      return;
    }
    list.forEach(function (m) {
      if (!SLOTS[m.key]) return;
      if (m.kind === 'text') { if (m.text != null) put(m.key, String(m.text)); return; }
      if (m.value == null) return;
      put(m.key, String(m.value));                    // 数值槽一律传字符串
    });
  }

  function tick() {
    req('/metrics').then(applyMetrics);
    // /units、/peripherals 同理：req('/peripherals').then(function (s) { … })
  }
  tick();
  setInterval(tick, 1000);                            // 约 1s 一轮，下一轮在上一轮结束后再发
})();
</script>
```

要点：

- **数值槽传字符串**（`String(m.value)`），文本槽传 `text`。
- **失败一律 `—`，绝不喂 0** —— `0%` 是"空载"，`—` 才是"不知道"。
- 单请求 4s 超时，且**上一轮结束后**再调度下一轮，避免堆积与旧响应覆盖。
- 外设是 3 秒一轮的慢通道，偶发超时**不要清屏**，保持上一轮读数。

---

## 四、CSP：页面设了就得放行本机接口

如果页面带 CSP（`<meta http-equiv="Content-Security-Policy" …>` 或托管平台的响应头），
必须放行本机数据接口，否则 fetch 会被静默拦掉、画面永远不动：

```html
<meta http-equiv="Content-Security-Policy"
      content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline';
               script-src 'self' 'unsafe-inline'; connect-src 'self' http://127.0.0.1:8766">
```

- 端口写死 8766 的 `connect-src` 只覆盖默认端口；如果页面同时读 `?__api`，
  用 `connect-src 'self' http://127.0.0.1:*`（或干脆不设 CSP，本技能的自检会把缺 `connect-src` 判成 WARN）。
- 症状：控制台出现 `Refused to connect to 'http://127.0.0.1:8766/metrics'`。

---

## 五、局域网访问限制（LNA / 原 PNA）

浏览器（含 WebView2）对「**公网页面 → 私网地址**」的请求有额外限制，
即 Local Network Access（旧名 Private Network Access）。

**症状**（三种都可能是它）：

- `Failed to fetch` / `TypeError: Failed to fetch`，页面**没有任何其他报错**；
- 控制台出现 `Permission denied for local network access` / `Access to fetch at 'http://127.0.0.1:8766' from origin 'https://…' has been blocked`；
- 请求根本没发出去（8766 侧日志无记录），或先发一个 `OPTIONS` 预检然后失败。

**应对顺序**：

1. **优先局域网部署**：页面和上位机同网段（§2.2），整站同源 `http`，不触发跨私网判定。
2. **云端 + 用户本机**：靠 `localhost` 的"安全上下文豁免"通常可用；被拦时由上位机侧放行
   （见 `app/ONLINE_MODE.md` §5.1，属软件侧工作，不是素材能解决的）。
3. **长期方案**：本机起 https 反代，把 `127.0.0.1:8766` 映射成 `https://localhost:8767`，
   页面连 https 就没有混合内容与 LNA 问题。

素材侧能做的只有两件事：**用 `127.0.0.1`（或 `localhost`）而不是局域网 IP**、
**失败时明确显示 `—`**，让问题可见而不是白屏。

---

## 六、安全清单（C11）

| 项 | 要求 |
|---|---|
| 控制接口 | ❌ 不调 `/app/show`、`/app/quit`（上位机只放行无 Origin / `Origin: null`，在线页面调用一律 403） |
| 密钥 | ❌ 页面里不放 `sk-…` / `Bearer …` / `api_key` 之类；数据只在本机 |
| 第三方脚本 | ❌ 不引不可信的 CDN/统计脚本（在线页面等于公开代码，等于把用户数据面暴露给第三方） |
| Tauri 能力 | ❌ 页面不能获得任何 Tauri capability（在线页面不是 app 的一部分） |
| 数据外发 | ❌ 不把指标 POST 到任何远端（这已超出"监控面板"的范围） |

---

## 七、交付清单

在线素材交付时，除了 html 本身，还要给出：

1. **托管地址**（https，或局域网私有地址 http）+ 一句「怎么更新」。
2. **页面自检结论**：`python scripts/check_material.py page.html --mode online`。
3. **清单块**里写 `"mode": "online"`（见 `references/output_format.md`）。
4. **两种尺寸的地址**（V1P 320×170 / V2 320×240 各一份，或用同一个页面按视口自适应 —— 不推荐，
   小屏素材按固定视口排版更稳）。
5. 一句**取不到数据时会显示什么**（`—` / `离线`），方便现场判断是"没数据"还是"页面坏了"。

---

## 八、自检：`--mode online`

```bash
python scripts/check_material.py page.html --mode online
```

在 A1–A15（本地契约）之外多查四条：

| 编号 | 判据 | 不过会怎样 |
|---|---|---|
| **A16** | 页面**自己取数**：出现 `fetch`，读 `?__api` 或出现 `8766`，且有 `.catch` / 失败兜底 | 托管后数据永远不动 |
| **A17** | **可托管**：无 `file://`、无盘符路径（`C:\`、`D:/`）、无 `..` 越界；资源是相对路径或 `https://` | 本机能开、托管后 404 |
| **A18** | **失败可见**：有 catch/兜底；设了 CSP 但缺 `connect-src` → WARN | 失败时白屏，现场无法判断 |
| **A19** | **不越权**：出现 `/app/show`、`/app/quit` → FAIL；疑似密钥（`sk-`、`Bearer`、`api_key`）→ FAIL | 安全问题 |

另外，在线模式**允许**页面不实现 `window.__setSlot`（它自己取数）：
B 层里 `window.__setSlot 未定义` / `__setSlot(...)` 抛错 这类失败会**降级为 WARN**，
其余 B 层判据（越界、残留占位符、重叠、字号、对比度）照旧是 FAIL。

---

## 九、症状对照表

| 症状 | 最可能的原因 | 去哪看 |
|---|---|---|
| 画面正常、数字永远不动 | CSP 拦了 fetch / LNA 拦了 / 端口写死 | §四、§五、§3.2 |
| `Failed to fetch`，无其他报错 | LNA（公网 → 私网） | §五 |
| 本机打开正常，托管后 404/白屏 | 资源用了盘符或绝对路径 | §2.1 第 3 条、A17 |
| 全屏 `—`，恢复不了 | 页面没做失败恢复（一次失败后停止轮询） | §3.3 `setInterval` + 失败继续 |
| CPU 显示 0% 但机器在跑 | 把"取不到"当成了 0 | §3.3 要点 2 |
| 端口换了就连不上 | 写死 8766 | §3.2 |
| 本地素材也用同一份页面时数据打架 | 页面既自取又被注入 | §3.3 开头的 `file://` 守卫 |
