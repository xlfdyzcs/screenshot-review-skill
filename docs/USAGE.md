# 使用指南

## 准备真实截图

使用项目自己的浏览器、模拟器或测试工具采集 PNG。两侧尽量保持相同视口、DPR、字体、语言、文本缩放与测试状态。长页按实际滚动顺序分段，不用重绘代替截图。

每个应用使用独立 `project`，每次修改使用新的 `revision`。页面 `id` 跨版本保留业务含义；新增页新增编号，删除页保留另一侧的真实空缺。

最小目录：

```text
captures/
  manifest.json
  old/start.png
  new/start.png
```

`manifest.json` 示例：

```json
{
  "review": {
    "project": "sample-app",
    "revision": "v2",
    "title": "Sample App 第二版审阅",
    "beforeLabel": "第一版",
    "afterLabel": "第二版"
  },
  "cases": [
    {
      "id": "A01",
      "group": "起始流程",
      "title": "初始页面",
      "width": 390,
      "height": 844,
      "before": ["old/start.png"],
      "after": ["new/start.png"]
    }
  ]
}
```

路径相对于清单所在目录，不能超出该目录。支持带 `file`、`scrollOffset` 等信息的对象；完整格式见[采集说明](../screenshot-review/references/capture.md)。

## 生成与打开

以下路径以本仓库根目录为例；安装到技能目录后，替换生成器路径即可，不依赖原项目目录结构。

```sh
python screenshot-review/scripts/review.py build --manifest captures/manifest.json --output output/sample-app/v2 --zip dist/sample-app-v2-review.zip
python screenshot-review/scripts/review.py validate --root output/sample-app/v2
python screenshot-review/scripts/review.py serve --root output/sample-app/v2 --port 8780
```

`build` 拒绝覆盖已有版本和已有 ZIP。`validate` 核对每张截图的尺寸及 SHA-256。`serve` 不指定端口时选择空闲端口，并输出实际 URL。

Windows 可以后台启动隐藏窗口：

```powershell
& './screenshot-review/scripts/open_review.ps1' -Root './output/sample-app/v2' -Port 8780 -Open
```

固定端口已有服务时，只复用内容一致的审阅包。不同项目可分别选择端口；不要结束其他项目的服务。

也可以离线打开输出目录内的 `index.html`。应整体保留目录中的 PNG、manifest 和可选 PDF；若浏览器限制本地文件访问，使用 `serve` 打开。

## 页面操作

目录可以折叠为只显示编号，完整标题也能通过悬停或页面信息查看。项目说明及采集备注在详情中展开。

截图默认适应各自可用宽度，内部独立滚动，且两侧滚动位置同步。关闭“同步滚动”可分别查看不同位置。缩放百分比以原始图片像素为基准；高倍率图片只在自身滚动区内溢出。

批注默认收起。点击“批注”或按 N 展开右侧面板；窄屏先进入独立批注视图，收起后返回截图。开启“标点”并点击截图后，自动标记为需要修改并展开意见面板。标点以相对图片的百分比存储，缩放不改变定位坐标。

| 快捷键 | 行为 |
| --- | --- |
| ← / → | 上一 / 下一分段 |
| N | 打开 / 收起批注 |
| F | 进入 / 退出全屏审图 |
| Esc | 关闭原图、目录或批注，或退出全屏 |
| Enter | 激活已聚焦的截图按钮，打开原尺寸预览；标点模式放置居中标点 |

输入框内正常输入不会触发 N/F 等快捷键。全屏 API 不可用时仍可使用扩大后的审图布局。

左右分段数不同时保留真实末尾空缺；某页只采集了一侧时保留缺图说明。缺少一侧截图的分段不能使用叠加。

## 意见、备份与版本

“导出修改意见”生成 Markdown，包含页面编号、状态、文字及标点坐标，适合发回开发者。“备份批注”生成 JSON，适合完整恢复状态、意见和标点；Markdown 不能导回成为备份。

批注按项目和版本保存在当前浏览器的 localStorage 中，也受地址来源影响。换机器、浏览器、端口或从本地文件切换到 HTTP 前先备份，之后导入。导入会核对项目、版本及标点所属截图；已有批注时提示替换确认。

新业务版本使用新目录和新 `revision`。只有迁移同一份旧审阅时才用 `--storage-key` 保留旧键，不要让不同版本共用批注身份。

仅升级审阅工具布局，不重新采集业务截图时：

```sh
python screenshot-review/scripts/review.py refresh --root output/sample-app/v2
```

该命令保留截图、manifest 和批注键，只替换查看器。随后重新加载浏览器。

## PDF 与分享

可通过 `build --pdf checked-review.pdf` 附入已有 PDF；应先通过项目自己的 PDF 工作流渲染检查。没有 PDF 时页面隐藏入口。

本机服务不向其他机器开放。确需分享审阅内容时，另行检查整个审阅包及批注；工具安装 ZIP 与包含业务截图的审阅 ZIP 是两种不同制品。发布工具仓库时遵循[分发边界](PRIVACY.md)。

## 常见问题

- **输出目录不为空**：创建新的版本目录；只想升级查看器时用 `refresh`。
- **换端口后批注为空**：这是不同来源的浏览器存储，导入此前导出的 JSON。
- **截图校验失败**：恢复原图或重新采集为新版本，不手改 SHA-256 来跳过问题。
- **另一侧留空**：检查是否故意缺图或分段已到末尾；工具不会伪造对照图。
- **本地存储不可用**：页面会提示，及时导出 Markdown 或 JSON。
