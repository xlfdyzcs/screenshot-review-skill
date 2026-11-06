# Screenshot Review

跨应用、跨项目的截图对照审阅技能，适用于已经能够采集实际页面的 Flutter、Web 和桌面项目。

用同一个页面完成逐项比对、长页分段、定位标点、填写意见与导出反馈。生成的审阅包可以离线使用，运行时无需前端依赖、CDN 或外部服务。

本仓库维护工具源码、文档和可自动生成的通用示例。实际项目的设计图、开发截图、审阅记录及批注不随技能分发。

## 功能

- 左右对照、透明叠加、原图预览和全部缩略图。
- 长页分段、两侧悬浮切换按钮、稳定的页面编号与分段链接。
- 双图同步或独立滚动、适应宽度、按原图像素缩放、全屏审图。
- 可折叠目录、搜索、待修改/未审阅筛选。
- 右侧按需展开的批注面板；窄屏使用独立批注视图。
- 自动审阅状态、定位标点、Markdown 修改意见、JSON 备份与恢复。
- 可选附入已经检查过的 PDF；生成器本身不制作 PDF。
- 项目、版本和浏览器存储键隔离；保留缺失的对照图，不补造截图。

| 桌面区域 | 默认行为 |
| --- | --- |
| 页面目录 | 216px，可收起至 48px |
| 全局栏 / 页面工具栏 | 约 54px / 56px |
| 对照截图 | 平分剩余宽度，各自滚动 |
| 批注 | 默认收起；展开后独立占用右侧约 350px |

## 安装

要求：Python 3.10+、支持现代 HTML/CSS/JavaScript 的浏览器。已使用 Python 3.12 验证。Node.js 只用于开发测试，不影响生成和查看审阅包。

### 在 Codex 中安装

可以直接提出：

> 使用 skill-installer 安装 https://github.com/xlfdyzcs/screenshot-review-skill/tree/main/screenshot-review 。

或从 [Releases](https://github.com/xlfdyzcs/screenshot-review-skill/releases) 下载 `screenshot-review-v1.0.0.zip`，解压后把整个 `screenshot-review` 文件夹放入 `$CODEX_HOME/skills/`；未设置 `CODEX_HOME` 时使用 `~/.codex/skills/`。私有仓库需要当前账号已具备访问权限。

首次手动安装也可以克隆仓库后执行：

```powershell
git clone https://github.com/xlfdyzcs/screenshot-review-skill.git
Set-Location screenshot-review-skill
$reviewSkillRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
New-Item -ItemType Directory -Path $reviewSkillRoot -Force | Out-Null
Copy-Item -LiteralPath './screenshot-review' -Destination $reviewSkillRoot -Recurse
```

macOS / Linux：

```sh
git clone https://github.com/xlfdyzcs/screenshot-review-skill.git
cd screenshot-review-skill
review_skill_root="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$review_skill_root"
cp -R screenshot-review "$review_skill_root/"
```

已有同名技能时，先备份原文件夹，再用新版本替换。安装后在下一轮对话中使用 `$screenshot-review`。

## 开始使用

在任意项目中提出：

> 使用 $screenshot-review，为当前项目生成修改前后的完整截图对照，保持页面编号，支持逐项标点和导出意见。

再次修改时：

> 根据这份复查意见修改并更新截图，左侧保留上一版原图，生成新的审阅版本。

技能会整理项目已有采集工具生成的真实 PNG；它本身不操作业务页面、不执行支付等业务交易。

### 运行不含产品页面的示例

下面的示例仅在本地生成几张抽象色块 PNG，不包含设计稿或真实应用截图：

```sh
python examples/create_demo.py --output build/demo-capture
python screenshot-review/scripts/review.py build --manifest build/demo-capture/manifest.json --output output/demo/v1
python screenshot-review/scripts/review.py validate --root output/demo/v1
python screenshot-review/scripts/review.py serve --root output/demo/v1
```

最后一条命令会输出实际本机地址。默认选择空闲端口；服务仅监听 `127.0.0.1`，按 Ctrl+C 停止。

## 审阅状态

| 操作 | 结果 |
| --- | --- |
| 从详情切换到另一项，当前项没有文字意见或标点 | 刚离开的未审阅项自动变为已核对 |
| 填写非空意见，或添加标点 | 立即变为需要修改 |
| 切换截图分段，或打开概览 | 不自动完成该项 |
| 清空全部意见和标点 | 回到未审阅，离开时再自动核对 |
| 只打开下一项 | 下一项保留自身状态 |

手动标记的“需要修改”会保留。批注保存在当前浏览器，换浏览器、机器或端口前先导出 JSON 备份。

## 文档与开发

- [使用、升级与问题处理](docs/USAGE.md)
- [截图采集与清单格式](screenshot-review/references/capture.md)
- [发布内容与隐私边界](docs/PRIVACY.md)
- [开发、验证与发布](CONTRIBUTING.md)
- [技能指令](screenshot-review/SKILL.md)

```sh
python -m unittest discover -s tests -p "test_*.py"
node --test tests/test_review_state.cjs
python scripts/check_distribution.py
python scripts/build_release.py
```

发布脚本按固定清单生成只有技能文本资源的安装包；源码仓库、安装包都经过分发检查。CI 使用相同命令验证。
