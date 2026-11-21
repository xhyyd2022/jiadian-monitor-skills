<!--module
id: output-format
title: 产物格式
owns: 产物清单块字段表 · 自检报告的机器可读格式 · 退出码
not_owns: 能力的定义与边界 · 主项目链路 · 素材的形态契约 · 检查项与判据 · 风格取舍
rendering: 与渲染约束无关（纯数据格式）；但清单块必须放在 #stage 之外、不参与画面
see: references/contract.md, references/self_check_gates.md
-->

# 产物格式约束（机器可读）

> 本文只讲**产物长什么格式**：素材内嵌的清单块、自检报告的机器可读形态、退出码。
> **素材本身的形态契约** → `references/contract.md`；**检查项** → `references/self_check_gates.md`。

**为什么有这份文档**：技能交付的东西要能被**下游程序直接抓取**，不靠人眼看、不靠猜。
所以技能规定了两样**有固定格式**的产物：

| 产物 | 是什么 | 抓取方式 |
|---|---|---|
| **素材文件** | 一个 `.html`，内含**产物清单块** | 读 `<script id="material-manifest">` 里的 JSON |
| **自检报告** | 一次自检的结论 | `check_material.py --json` 的 JSON（或末行固定文案） |

> 两者都用 **`schema` 字段**声明格式版本，便于以后演进时不破坏下游解析。

---

## 一、素材文件

### 1.1 命名与存放

- 文件名：`^[a-z0-9][a-z0-9_-]*\.html$` —— **小写字母 / 数字 / `_` / `-`**，扩展名 `.html`。
- 一份素材 = **一个文件**（CSS / JS 内联）。
- 底图若用本地图片，与 HTML **放同一目录**，只写文件名相对路径 `xxx.png`。

### 1.2 清单块（唯一抓取入口）

在 `</body>` **之前**（即 `#stage` **之外**）放一块**惰性 JSON**：

```html
<script type="application/json" id="material-manifest">
{
  "schema": "rgb565-panel-material/1",
  "name": "p9_glass_cards",
  "size": [320, 240],
  "background": "css",
  "mode": "local",
  "slots": [
    { "name": "v1", "kind": "text", "warn": 75, "danger": 90, "fmt": 0, "unit": "%" },
    { "name": "bar1", "kind": "bar", "from": "v1", "max": 100 }
  ]
}
</script>
```

**为什么放在 `#stage` 之外**：它是**数据，不是画面**。运行时自检的判定范围是 `#stage *`，
把数据块放进画面树里语义不对，也容易被 `#stage *` 这类选择器一并选中。
`type="application/json"` 保证浏览器**不执行**它（写成 `text/javascript` 会被当 JS 执行并报错，
A13 会判），它纯粹是给机器读的数据。

### 1.3 字段表

顶层：

| 字段 | 类型 | 必须 | 说明 |
|---|---|---|---|
| `schema` | string | ✅ | 固定 `"rgb565-panel-material/1"`；格式演进时换版本号 |
| `name` | string | ✅ | 素材名 = 文件名去掉 `.html` |
| `size` | `[w, h]` | ✅ | 视口尺寸，必须与样式里声明的一致 |
| `background` | string | ✅ | `"css"` / `"local"` / `"url"` —— 与素材实际用法一致 |
| `slots` | array | ✅ | 每个 `data-slot` 一条（见下） |
| `mode` | string | 可选 | `"local"`（缺省）/ `"online"` —— 交付形态。在线素材写 `"online"`；不写按 local 处理，下游不依赖它 |

> `schema` 是**格式 id，不是路径**：技能目录已改名为 `jiadian-monitor-skills`，但这个串沿用历史 id
> `rgb565-panel-material/1` 不变 —— 改它要动所有素材与下游抓取，而下游 `assets.rs` 也不校验它。

`slots[]` 里每一项：

| 字段 | 类型 | 必须 | 说明 |
|---|---|---|---|
| `name` | string | ✅ | 注入名，与 `data-slot` 一致 |
| `kind` | string | ✅ | `text` / `bar`，或自定义（`ring` / `heat` / `led` …） |
| `from` | string | 条必填 | 跟随哪个文本槽（对应 `data-from`） |
| `max` | number | 条必填 | 满值（对应 `data-max`） |
| `warn` / `danger` | number | 可选 | 阈值（对应 `data-warn` / `data-danger`），**`danger ≥ warn`** |
| `fmt` | number | 可选 | 保留小数位（对应 `data-fmt`） |
| `group` | true | 可选 | 千分位（对应 `data-group="1"`） |
| `unit` | string | 可选 | 单位后缀（对应 `data-suffix`，**已去掉首尾空格**） |

> **`slots` 必须把素材里**每一个** `data-slot` 都列上**（包括只当标签用的槽）。
> 少列 / 多列 / 字段与素材不符 → 自检 **A13 FAIL**。

### 1.4 怎么生成它（别手写）

清单是**从素材派生**的，所以别手抄 —— 手抄必然与素材漂移：

```bash
# 打印派生好的清单块，粘进 </body> 前
python scripts/check_material.py my.html --emit-manifest

# 或者直接就地回填 / 刷新（幂等，可反复跑）
python scripts/add_manifest.py my.html
python scripts/add_manifest.py --all          # 技能自带的 16 套参考素材
python scripts/add_manifest.py --all --check  # 只报哪些缺清单
```

---

## 二、自检报告

### 2.1 机器可读（推荐给程序）

```bash
python scripts/check_material.py --all --json
```

输出**一个** JSON 对象（stdout 上只有它，人读输出被吞掉）：

```json
{
  "schema": "rgb565-material-check/1",
  "size": "320x240",
  "mode": "local",
  "total": 16,
  "pass": 16,
  "fail": 0,
  "files_with_warn": 0,
  "results": [
    {
      "file": "p8_glass_cards.html",
      "path": "D:\\...\\assets\\verified_materials\\p8_glass_cards.html",
      "status": "PASS",
      "fail": [],
      "warn": [],
      "info": ["A1 尺寸 320x240", "A4 占位符 6 个 / data-slot 9 个", "A13 清单 …"]
    }
  ]
}
```

- `status` ∈ `PASS` / `FAIL`；`fail` / `warn` / `info` 都是**字符串数组**，
  每条以**检查编号**开头（`A1…A13` / `B1…B7` / `B0`），下游可按编号分类。
- `files_with_warn`：`status=PASS` 但带告警的文件数（**告警不算失败，但要记录在案**）。
- `mode`：本次用的交付形态（`local` 缺省 / `online`，来自 `--mode online`），下游可据此决定是否要求 `__setSlot`。

### 2.2 人读

```bash
python scripts/check_material.py --all
```

- 每个文件一行：`[PASS] xxx.html` 或 `[FAIL] xxx.html  —— N 个问题`
- 明细行前缀固定：`✗` 失败 / `!` 告警 / `·` 信息
- **末行固定文案**（可正则抓）：
  `合计：{pass} 通过 / {fail} 失败（共 {total} 个文件）`

### 2.3 退出码（脚本判据，最省事）

| 退出码 | 含义 |
|---|---|
| `0` | 无 FAIL（可能带 WARN） |
| `1` | 存在 FAIL |
| `2` | 参数错误（如 `--emit-manifest` 没给文件） |

> 只要**无 FAIL** 就该是 `0`。**不要**为了拿到 `0` 而放宽判据 —— 判据是踩过坑之后定的。

---

## 三、下游程序的最小抓取姿势

```python
import json, re, subprocess

html = open('p8_glass_cards.html', encoding='utf-8').read()
m = re.search(r'<script[^>]*id="material-manifest"[^>]*>(.*?)</script>', html, re.S)
manifest = json.loads(m.group(1))          # → 有哪些槽、范围、阈值、单位

rep = json.loads(subprocess.run(
    ['python', 'scripts/check_material.py', '--all', '--json'],
    capture_output=True, text=True).stdout)
assert rep['fail'] == 0, rep
```

**一句话**：抓素材看 `#material-manifest`，抓结论看 `--json` 的 `schema` + `fail`。

### 已知的真实下游（v0.9.1 实测）

- 上位机 `app/src-tauri/src/assets.rs` 在扫描主题时会**先**从 CSS 里推断画布尺寸，
  **推断不到才回退**到清单里的 `"size": [W, H]`（只认这个字段，不读 `slots`）。
  所以清单的 `size` 必须与样式声明一致 —— 这也是 **A13** 会交叉校验的项。
- 其余字段（`slots[]` / `threshold` / `background`）目前是**给工具与未来功能**抓的，
  上位机运行时不会解析它们；但既然写进契约，就要保证与素材实际一致（别手抄）。
- 面板取数不经过清单（走 8766 注入脚本，见 `references/api_map.md`）。
