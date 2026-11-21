<!--module
id: contract
title: 素材契约
owns: 素材的形态契约 · 文本槽与注入入口 · 进度条字段 · 底图约定
not_owns: 能力的定义与边界 · 主项目链路 · 检查项与判据 · 机器可读格式 · 风格取舍
rendering: 视口锁死 W×H 贴左上 · 禁居中 · 整数像素 · 单文件且无本机路径残留
see: references/output_format.md, references/self_check_gates.md
-->

# 素材契约全文

> 本文只讲**素材该长什么样**（形态契约）。**判它合不合格** → `references/self_check_gates.md`；
> **它内嵌的机器可读清单** → `references/output_format.md`。
>
> 上位机做数据注入只认 `data-slot` / `__setSlot`，**不解析**这些字段里的图形信息；
> 但要**枚举有哪些槽**时，读的是第 6 节那块产物清单（机器可读，别手写）。

## 1. 文件与尺寸

**单文件**：一个 `.html`，CSS / JS 都写在里面。可以引用外部 CDN / 图片 / 字体
（面板在**上位机所在电脑**的 WebView2 里渲染，所以是**电脑**要能上网，不是设备），
但**不得残留本机路径**（`file:///C:/Users/...` 这类自用路径必须去掉）。

**尺寸锁死 `{W}×{H}`，贴左上铺满**：

```css
html, body {
  margin: 0; padding: 0;
  width: {W}px; height: {H}px;
  overflow: hidden; display: block;
}
```

⚠️ 这条规则块必须**同时声明 width 和 height**、且放在**样式表最前面** ——
工具是按"文档顺序取第一个同时含宽高的样式块"来推断视口的；只写一半会推断失败。

**禁止居中**：不要 `place-items:center` / `margin:auto` / `100vw` / `100vh`。
坐标一律**整数像素**（`12.5px` 在 RGB565 上会抖）。

**三层结构（建议，非强制）**：`#img`（静态底图）→ `#render`（与数据无关的图形 + 动画）→
`#text`（文字与数值），`z-index` 递增。只是可读性建议，实时流按像素差分，不依赖它。

### 背景底图：**只有三种**（开工前必须问用户选哪种）

| 选项 | 写法 | 说明 |
|---|---|---|
| **ⓐ 纯 CSS**（推荐默认） | `linear-gradient` / `radial-gradient` / `repeating-linear-gradient` | **不引任何文件**，最省事、最可控 |
| **ⓑ 本地文件** | `url("bg.png")` | 图片与 HTML **放在同一目录**，只写文件名相对引用 |
| **ⓒ 在线 URL** | `url("https://example.com/bg.png")` | 直接写完整 URL（渲染在上位机所在电脑，电脑联网即可；设备不加载页面） |

**ⓑ 的硬规则**：只写「文件名」，图片与 HTML 同目录（放进 app 的 `assets/` 时也是同一层）。
❌ 不许写盘符（`C:\...`）、❌ 不许写绝对路径、❌ 不许 `..` 往上层跑、❌ 不许 `file:///`、❌ 不许另建子目录。
**选了 ⓑ 但没有对应的图片文件 → 先问用户，不要自己编一个路径。**

选定后在产物清单的 `background` 字段里如实标注（`css` / `local` / `url`）——
自检 **A13** 会拿它和素材实际用法交叉校验。

## 2. 文字：静态 vs 动态

| 类型 | 写法 | 要不要 `data-slot` |
|---|---|---|
| **静态文字**（标题 / 单位 / 说明 / 固定标签） | 直接写死在 HTML 里 | ❌ 不要加 |
| **动态文字**（运行时会变） | 用 `{{名字}}` 占位符 | ✅ 加**同名** `data-slot` |

```html
<!-- 静态：直接写 -->
<span class="ttl">系统监控 SYSTEM</span>

<!-- 动态：占位符 + 同名 data-slot -->
<span data-slot="v1" data-fmt="0" data-suffix="%"
      data-warn="75" data-danger="90">{{v1}}</span>
```

一句话：**看到 `{{…}}` 就是要注入的文本/数值；没写占位符的就是静态文字。**

⚠️ 占位符与 `data-slot` **拼错一个字母**（`{{v1}}` ↔ `data-slot="v2"`）**不会报任何错**，
只会永远不更新 —— 这是最难查的一类问题。

**格式化由页面做**（上位机发的是原始数值字符串）：

| 属性 | 含义 |
|---|---|
| `data-fmt="N"` | 保留 N 位小数；不写则原样输出 |
| `data-group="1"` | 千分位分隔 |
| `data-unit="GB"` | **「我要什么单位」的标识符**：上位机把该槽的规范值换算成这个单位再喂进来。可换算**四族**：`B/KB/MB/GB/TB`（容量）、`B/s/KB/s/MB/s/GB/s`（速率）、`℃/℉`（温度）、`秒/分/小时/天`（时长，`s/min/h/d` 同义）。`W`（功耗，电脑只用 W，无可换算）、`%` `RPM` 原样透传。**跨族不换算**（给占用率写 GB 会被闸门 A14 拦下并列出该槽可用的单位）。**不写就按规范单位**（内存/磁盘 = GB、显存 = MB、速率 = KB/s、温度 = ℃、风扇 = RPM、开机时长 = 秒） |
| `data-suffix="%"` | 单位后缀，拼接在数值后面。**用了它就不要再放静态单位元素**（否则出现 `63%%`）；带物理单位时与 `data-unit` 保持一致；**一个槽只能声明一种单位** |
| `data-warn="75"` | ≥ 此值切 `.warn` 类 |
| `data-danger="90"` | ≥ 此值切 `.danger` 类。**必须 ≥ `data-warn`**，写反了告警色永不出现 |

⚠️ **单位以素材声明为准**：上位机的 `/metrics` 只给规范单位的值，页面要别的单位就写 `data-unit`
（例：内存想显示 `16384 MB` 就写 `data-unit="MB"`）。

上位机设置页另有「单位设置」两档：**全自动**（默认，按素材的 `data-unit`）/ **手动指定**
（用户按容量·速率·温度·时长四族统一覆盖，改完立刻生效；功耗固定 W，不在其中）。素材只管把 `data-unit` 写对 ——
手动指定是用户侧覆盖，不需要素材配合；但也**别把单位写死在别的元素上**，否则用户一改单位，
数值换了、静态标签跟不上。

配套 CSS：

```css
.warn   { color: #fbbf24 !important; }
.danger { color: #f87171 !important; }
```

## 3. 进度条

```html
<div class="bar" data-slot="bar1" data-kind="bar" data-from="v1" data-max="100"
     data-box="18,88,128,6" style="left:18px;top:88px;width:0;"></div>
```

| 属性 | 必须 | 含义 |
|---|---|---|
| `data-kind="bar"` | ✅ | 标记这是连续宽度条 |
| `data-from="v1"` | ✅ | 跟随哪个文本槽（推该槽时条一起动） |
| `data-max="100"` | ✅ | 满值 |
| `data-box="x,y,w,h"` | ✅ | **条的可用区域**：4 个整数、在画布内、且要与元素**实际的 `left/top/width` 对得上** |

⚠️ `data-box` 与元素实际坐标不一致时：条要么撑出框，要么永远填不满。A7 会交叉校验。

**轨道**建议用类名 `.bar-track`（条压在轨道上是设计意图，部分检查器按类名放行）。

## 4. 注入入口 `window.__setSlot(name, value)`

职责共 5 条，缺一不可：

1. 更新**所有** `[data-slot=name]` 的元素（条走条逻辑、文本走文本逻辑）
2. 文本按 `data-fmt` / `data-group` / `data-suffix` 格式化，非数字原样输出
3. 命中阈值切 `.warn` / `.danger`；**条从 `data-from` 的源槽继承阈值**
4. 条宽 = `clamp(值 / 上限, 0, 1) × data-box 宽度`，取整像素
5. 先给默认值（**不注入也有完整画面**），再用 URL 参数覆盖同名槽，**顺序不能反**

### 数据来源：本地 API（**面板不用自己取数**）

上位机渲染面板时会**通过 CDP 自动注入**一段脚本（不是素材里的代码）：等 `__setSlot` 就绪后，
每轮**并发** `fetch` 三个端点 —— `/metrics`（硬件指标）、`/units`（单位设置）、`/peripherals`（外设电量），
再把结果喂进 `__setSlot`。稳定期约 **1 秒一轮**（上一轮结束后再等 1s），单请求 4s 超时。

- 数值槽：注入的是**数字字符串**（`String(value)`），让素材的 `data-fmt` / `data-suffix` 生效；
  若素材写了 `data-unit` 或用户在设置里选了手动单位，注入脚本**先换算再喂**（并可能改写元素的 `data-suffix`）。
- 文本槽（`cpu_name` / `gpu1_name` / `_name` / `_status`）：注入的是 `text` 字符串，不参与数值格式化。
- `/metrics` 整轮失败：CPU 三槽（`cpu_load` / `cpu_load_p` / `cpu_load_e`）清成 `—`，其余槽保持上一轮值；
  外设请求失败时**整轮跳过**（保留上一轮），只有设备从快照消失才把对应槽清成 `—`。
- 所以素材**只负责**：① 定义 `__setSlot`；② `data-slot` / `{{占位符}}` 用**真名**
  （`cpu_load` / `gpu1_temp`…）。**不要**自己写 `fetch` / 定时器取数，
  也**不要**用 `v1` / `s1` 这类自造名（会永远不更新）。
- 真实运行时页面地址会带 `?__api=<端口>`（上位机加的标注）；**页面不需要解析它**，
  注入脚本用的是「实际绑定的回环地址」拼 URL（`127.0.0.1` 或 `[::1]`），不依赖查询参数。
  检查闸门直接用 `file://` 打开（不注入）→ 走默认值与 URL 参数，结果**确定**、可复现。
- 指标清单、编号规则、单位 → `references/metrics.md`；端点实况 / 调用关系 → `references/api_map.md`。

> **在线形态是例外**：托管出去的页面拿不到注入脚本，必须**自己** `fetch`，且**必须解析 `?__api`**。
> 详见 §8 与 `references/online_hosting.md`。

### 参考实现（可直接整段照抄，按需增删槽位）

```html
<script>
(function () {
  function tx(el, raw) {                       /* 文本槽：格式化 */
    var v = parseFloat(raw);
    if (isNaN(v)) return String(raw);
    var d = el.getAttribute('data-fmt');
    var s = (d === null) ? String(raw) : v.toFixed(parseInt(d, 10));
    if (el.getAttribute('data-group') === '1') s = s.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return s + (el.getAttribute('data-suffix') || '');
  }
  function th(el) {                            /* 阈值；条从 data-from 的源槽继承 */
    var w = el.getAttribute('data-warn'), g = el.getAttribute('data-danger');
    if (w === null && g === null && el.getAttribute('data-from')) {
      var s = document.querySelector('[data-slot="' + el.getAttribute('data-from') + '"]');
      if (s) { w = s.getAttribute('data-warn'); g = s.getAttribute('data-danger'); }
    }
    return [w === null ? null : parseFloat(w), g === null ? null : parseFloat(g)];
  }
  function cl(el, raw) {                       /* 上色 */
    var v = parseFloat(raw), t = th(el);
    el.classList.toggle('warn',   t[0] !== null && v >= t[0] && !(t[1] !== null && v >= t[1]));
    el.classList.toggle('danger', t[1] !== null && v >= t[1]);
  }
  function bar(el, raw) {                      /* 条：按 data-box 宽度换算 */
    var v = parseFloat(raw), m = parseFloat(el.getAttribute('data-max') || '100');
    var b = (el.getAttribute('data-box') || '0,0,100,4').split(',');
    el.style.width = Math.round(Math.max(0, Math.min(1, (isNaN(v) ? 0 : v) / m)) * parseFloat(b[2])) + 'px';
    cl(el, raw);
  }
  window.__setSlot = function (name, value) {
    var sp = document.querySelectorAll('[data-slot="' + name + '"]');
    for (var i = 0; i < sp.length; i++) {
      if (sp[i].getAttribute('data-kind') === 'bar') { bar(sp[i], value); continue; }
      sp[i].textContent = tx(sp[i], value); cl(sp[i], value);
    }
    var bs = document.querySelectorAll('[data-kind="bar"][data-from="' + name + '"]');
    for (var j = 0; j < bs.length; j++) bar(bs[j], value);
    return true;
  };
  window.__setSlot('v1', '42'); window.__setSlot('v2', '61');   /* 默认值：不注入也有画面 */
  new URLSearchParams(location.search).forEach(function (v, k) { window.__setSlot(k, v); });
})();
</script>
```

## 5. 扩展自定义 `data-kind`（允许，且被闸门覆盖）

契约只规定 `bar`；但页面完全可以扩展别的 `data-kind`（**实现自由度**）。
实战验证过的扩展：

| kind | 用途 | 做法 |
|---|---|---|
| `ring` | 环形表 | 把比值映射成角度，写进 CSS 变量驱动 `conic-gradient` |
| `heat` | 热力格 | 把比值映射成若干档底色 |
| `led` | 状态灯 | 只做阈值上色（直接复用 `cl()`） |

写法与 `bar` 同构：`data-kind="XXX" data-from="v1" data-max="100"`，
在 `__setSlot` 里加一个分支 + 一个"按 `data-from` 找元素"的收尾循环：

```js
function ring(el, raw) {
  var v = parseFloat(raw), m = parseFloat(el.getAttribute('data-max') || '100');
  var p = Math.max(0, Math.min(1, (isNaN(v) ? 0 : v) / m));
  el.style.setProperty('--deg', (p * 360).toFixed(1) + 'deg');
  cl(el, raw);
}
// __setSlot 内：
var rs = document.querySelectorAll('[data-kind="ring"][data-from="' + name + '"]');
for (var q = 0; q < rs.length; q++) ring(rs[q], value);
```

**为什么敢扩展**：闸门里的 **B2 会对每个槽注入 `0/50/100/999`**，
自定义 kind 抛错会立刻暴露；而静态检查 **A6 只对 `bar`/`seg` 强制必备字段**，
不认识的 kind 不会误判。所以扩展是安全的 —— 前提是**过了闸门**。

## 6. 产物清单块（`</body>` 前，**必填**）

素材要能被下游程序**直接抓取**，所以 `</body>` 之前必须有一块**惰性 JSON**：

```html
<script type="application/json" id="material-manifest">
{
  "schema": "rgb565-panel-material/1",
  "name": "p9_glass_cards",
  "size": [320, 240],
  "background": "css",
  "slots": [
    { "name": "v1", "kind": "text", "warn": 75, "danger": 90, "fmt": 0, "unit": "%" },
    { "name": "bar1", "kind": "bar", "from": "v1", "max": 100 }
  ]
}
</script>
```

要点：

- 放在 **`#stage` 之外**（运行时自检只扫 `#stage *`，放里面会被当成页面元素）。
- `type="application/json"` —— 浏览器**不执行**它，纯数据；写成 `text/javascript` 会被执行并报错。
- 每个 `data-slot` 一条，字段与素材上的 `data-*` **必须一致**（自检 **A13** 交叉校验）。
- **别手写**：`check_material.py --emit-manifest` 打印、或 `add_manifest.py` 就地回填。

> 完整字段表与 `--json` 报告 schema → `references/output_format.md`

## 7. 明确「**不**要求」的东西（避免过度设计）

- ❌ **不要求**三层结构 —— 实时流按像素差分，`#img/#render/#text` 只是可读性建议。
- ❌ **不要求** `data-box` —— 实时流不解析它，写不写都不影响下发（但闸门 A7 会校验格式）。
- ❌ **不限制 JavaScript** —— 定时器、`requestAnimationFrame`、canvas、WebGL、第三方库都可以。
- ✅ **允许**引用外部 CDN / 图片 / 字体。
- ✅ **要求**：单文件、`{W}×{H}` 贴左上、`data-slot` + `__setSlot`、**产物清单块**、**过闸门**。

> 在线形态对「外部资源」更严：只允许**相对路径**或 `https://`，❌ `file://`、❌ 盘符、❌ `..` 越界（见 §8 C10）。

## 8. 在线素材契约（C9–C12）

前面 §1–§7 在两种形态下**全部照旧**；在线形态额外多四条 —— 差别只在**取数**与**资源引用**，
画面约束、闸门、清单块一条都不放松。

### C9 页面自己取数

app **不注入**。页面在 `<script>` 里：

- 端口从 `?__api` 读（`new URLSearchParams(location.search).get('__api') || '8766'`），**不要写死 8766**；
- 并发 `GET /metrics`（数组）、`GET /units`（`{mode,units}`）、`GET /peripherals`（`{devices}`），约 1s 一轮；
- 单请求 4s 超时（`AbortController`），**上一轮结束后**再调度下一轮；
- 数值槽传**数字字符串**（`String(value)`），文本槽传 `text`；
- 失败一律 `—`，**绝不喂 0**；外设偶发超时保持上一轮读数。

### C10 可托管

| 允许 | 禁止 |
|---|---|
| `./bg.png`、`assets/x.png`（相对） | `file:///…` |
| `https://cdn…/x.woff2` | `C:\bg.png`、`D:/x.png`（盘符） |
| 数据 URL（`data:image/png;base64,…`） | `../` 跑出站点根 |
| 托管地址 https，或**私有地址** http | 公网 `http://`（上位机会拒） |

### C11 失败可见 + 不越权

- 取不到 → `—` / `离线`，**不要空白、不要假数据**；恢复后自动继续。
- ❌ 不调 `/app/show`、`/app/quit`（上位机只放行无 Origin / `Origin: null`，在线页面调用 403）。
- ❌ 页面里不放密钥（`sk-…` / `Bearer` / `api_key`）、不引不可信第三方脚本、不把指标外发。
- 设了 CSP 必须放行数据接口：`connect-src 'self' http://127.0.0.1:8766`（端口非默认时用 `http://127.0.0.1:*`）。

### C12 一份代码两种模式（推荐，不强制）

- 仍实现 `window.__setSlot` + `data-slot`，把取到的数据喂给同一个渲染函数 → 同一份页面在本地模式也能跑。
- 自取代码加 `if (location.protocol === 'file:') return;` 守卫：本地模式是 `file://`（由 app 注入），
  在线是 `http(s)`（自己取），一份代码不打架。
- 不实现 `__setSlot` 也合法：`--mode online` 自检会把 B 层"`__setSlot` 未定义 / 抛错"降级为 WARN。

> 托管步骤、CSP 写法、LNA 限制、交付清单 → `references/online_hosting.md`
> 自检：`python scripts/check_material.py page.html --mode online`（A16–A19）
