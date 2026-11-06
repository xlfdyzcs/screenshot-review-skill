# 开发、验证与发布

## 目录

```text
screenshot-review/       可直接安装的独立技能
  assets/                查看器模板、样式与交互
  scripts/               标准库生成器与 Windows 启动入口
  references/            截图采集及清单说明
docs/                    使用及分发说明
  images/                六张虚构示例实拍及来源哈希
examples/create_demo.py  生成本地抽象色块示例
examples/fictional-app.html  专门拍摄文档截图的虚构任务应用
tests/                   生成器、状态及分发边界回归
scripts/                 检查和构建安装包
```

技能运行依赖 Python 标准库，无需 npm 安装。开发测试另需支持 `node:test` 的 Node.js；CI 使用 Python 3.12 与 Node.js 22。

## 验证

```sh
python -m unittest discover -s tests -p "test_*.py"
node --check screenshot-review/assets/review.js
node --test tests/test_review_state.cjs
python scripts/check_distribution.py
python scripts/build_release.py
```

布局变更应在独立示例中验证 1920×1080、1366×768 及窄屏。重点检查批注不遮图、整页不横向溢出、长图末尾可达、双图同步/独立滚动、缩放、叠加、原图、分段、全屏退出、搜索概览、自动状态及导出/备份恢复。

不要用真实产品页面或用户已有批注进行回归。测试使用临时生成的色块 PNG，结束后保留用户数据、清理测试意见。回归测试覆盖新行为及配置边界，避免仅断言实现文字。

## 保持兼容

- `refresh` 只能替换查看器，不改变 manifest、截图字节、项目/版本及批注身份。
- 保留已有页面 ID、标点百分比坐标、Markdown 和 JSON 备份格式。
- 新应用通过清单和参数接入，不在查看器里写应用名、品牌或开发者机器路径。
- 说明和示例只使用通用数据。实际截图与审阅输出留在所属项目。

## 构建发布包

修改 `VERSION`，运行全部检查，再执行：

```sh
python scripts/build_release.py
```

输出 `dist/screenshot-review-v<VERSION>.zip` 与 `dist/SHA256SUMS.txt`。ZIP 根目录是 `screenshot-review/`，仅包含安装所需的九个文本资源，不包含业务图片或审阅记录。ZIP 条目使用固定时间戳和权限，便于在相同源码下重复校验。

发布到与 `VERSION` 一致的 GitHub tag，在 Release 中附上这两个文件，并说明实际测试范围。不要把 `output/`、`build/`、完整项目目录或业务审阅 ZIP 当作安装附件上传。

文档图只允许使用 `examples/fictional-app.html` 生成的虚构页面，在审阅工具中真实操作后截图。更新六张文档图时同步更新 `docs/images/provenance.json` 的源码哈希、图片尺寸与哈希，逐张检查后运行分发测试。完整采集目录和审阅包留在本地，安装 ZIP 不收录文档图。

新增分发文件时同时更新白名单及相关测试，检查[隐私边界](docs/PRIVACY.md)。
