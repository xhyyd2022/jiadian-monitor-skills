# 佳点监控面板素材技能

给 **320×240 / 320×170 RGB565 小屏**生成和校验单文件 HTML 监控面板的 AI 技能。

佳点监控（Jiadian Monitor）会把 HTML 面板放在隐藏的 WebView2 里渲染，抓帧、做脏矩形差分，再通过 USB 增量推给设备。这个技能把「面板怎么写、数据怎么注入、哪些地方最容易翻车」整理成一套可执行流程，并附带静态检查和真实浏览器运行检查。

## 适合做什么

- 从零生成一块小而清晰的监控面板
- 校验已有 HTML 是否符合面板契约
- 检查数据槽、单位、文字可读性、变化面积
- 生成深色 / 浅色 / 终端风等风格库
- 本地素材与在线托管素材两种交付形态

## 安装

把本仓库链接直接丢给 AI，让它按 `SKILL.md` 安装到技能目录即可。

也可以手动克隆后，把整个文件夹放进你的技能目录；不需要改代码，也不需要额外依赖。

## 使用

1. 先确定交付形态：**本地素材**（app 注入数据）还是**在线素材**（页面自己请求本机 API）。
2. 按 `SKILL.md` 的流程生成 HTML。
3. 运行自检：

```bash
python scripts/check_material.py 你的素材.html
python scripts/check_material.py 你的素材.html --mode online
```

4. 有视觉能力的模型可以再用 `scripts/screenshot.py` 截图做视觉闸门。

## 目录

```text
SKILL.md                    技能入口 / 工作流 / 边界
assets/material_prompt.md   可直接交给另一个 AI 的完整提示词
assets/verified_materials/ 16 套已验证参考素材
references/                 指标、契约、样式、在线托管、维护约定
scripts/                    检查、描述、截图、同步脚本
```

## 自检

```bash
cd jiadian-monitor-skills
python scripts/check_material.py --all
python scripts/describe.py --check
```

技能只依赖 Python 标准库；运行时检查需要本机安装 Edge / Chrome。

## 相关项目

主程序：[佳点监控](https://github.com/xhyyd2022/jiadian-monitor)

## 许可

本技能随主项目发布，使用前请阅读主项目的 [LICENSE](https://github.com/xhyyd2022/jiadian-monitor/blob/main/LICENSE)（PolyForm Noncommercial 1.0.0，禁止商业使用）。
