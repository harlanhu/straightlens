# StraightLens · 自动镜头校正

本地 Web 应用。导入一张 JPG / PNG / WebP 后自动检测曲线边缘、估计径向镜头畸变、检查几何改善，再生成可下载图片。无需相机信息、手动选线或参数调整。图片不发送到第三方服务。

## 当前能力

- 基于 IPOL 双参数 polynomial / division 模型，自动尝试两档边缘阈值，并在证据支持时优化畸变中心。
- 使用曲线分组的系数重拟合检查、线条覆盖、映射单调性和候选形状一致性进行保守判断。
- 原有强畸变路径未通过时，自动尝试有界单参数弱畸变分支：无序轮廓排序、端点连续合并、重叠双边去重、整条轮廓的鲁棒共识拟合与留出检查。用户无需选择分支或调参。
- 已校正结果按完整解码分辨率重映射，再裁去无效边缘；未校正时原上传文件按字节保留，可直接下载。
- 原图、结果及并排查看；100% 查看加载完整尺寸图像，适应窗口使用预览。
- 校正成功后可分别下载裁切版和未裁切版 PNG。未裁切版是自动裁边前的完整 FIT_WIDTH 画布，可能带黑边。
- 可在外部编辑后上传整张不透明图片，也可上传未修改的参考图或其他同画布比例图片，按当前任务参数反算。提供正向和反算两组对比；反算区可切换“上传图片对比”和“原图对比”，上传后默认展示上传图与反算结果，支持完整上传图的 100% 查看。不开发绘画功能、不提取涂鸦差分。
- 输入限制 20 MiB / 2000 万像素，一次处理一张；一个运行任务和最多两个排队任务。
- 任务文件默认保留 24 小时；重启保留已完成记录，中断任务会显示失败。

## 安装与运行

需要 Python 3.11+、Node.js 22+、pnpm、C++ 编译器和 libpng 开发库。本机已在 macOS Apple Silicon / Python 3.14 / clang++ 上验证。

首次安装可以直接执行：

```bash
bash setup.sh
```

如果需要手动控制 Python 环境，也可以在项目根目录执行：

```bash
uv venv --python 3.14 .venv-local
uv pip install --python .venv-local/bin/python -r backend/requirements-lock.txt
bash scripts/build_ipol.sh
```

macOS 若缺少 libpng，可自行用 Homebrew 安装 `libpng`；Debian/Ubuntu 通常需要 `build-essential libpng-dev pkg-config`。构建脚本优先通过 pkg-config 定位，否则尝试 Apple Silicon Homebrew 目录或系统库。

构建前端：

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm run build
```

回到项目根目录启动：

```bash
bash scripts/run_local.sh
```

打开 http://127.0.0.1:8765 。按 Ctrl+C 停止。默认仅绑定本机回环地址。

可通过 `PORT=8766 bash scripts/run_local.sh` 更换端口。`STRAIGHTLENS_PYTHON` 指定其他 Python 环境；`STRAIGHTLENS_DATA` 指定任务目录（默认项目内 `.runtime/jobs`）。旧版本的 `LENSLINE_PYTHON` 和 `LENSLINE_DATA` 仍可作为兼容变量使用。无需运行另一个 Vite 服务；FastAPI 会托管构建后的前端。

### Docker

Docker 会在镜像构建阶段编译 IPOL 原生程序、安装 Python 依赖并构建前端，运行时只启动一个 FastAPI 容器。需要 Docker Engine 24+ 和 Compose v2：

```bash
docker compose build
docker compose up -d
curl http://127.0.0.1:8765/api/health
```

打开 http://127.0.0.1:8765 。默认端口只绑定本机回环地址；需要更换端口时执行 `STRAIGHTLENS_PORT=8766 docker compose up -d`。

Dockerfile 支持 `linux/amd64` 和 `linux/arm64`。在 Apple Silicon 上本地构建当前架构镜像；发布多架构镜像时使用 Buildx，并将结果推送到镜像仓库：

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag ghcr.io/harlanhu/straightlens:latest \
  --push .
```

如果只需要在当前机器上验证 amd64 构建，可以执行：

```bash
docker buildx build --platform linux/amd64 --load --tag straightlens:amd64 .
```

任务目录保存在名为 `straightlens-jobs` 的 Docker volume 中，因此容器重启或重新创建后，已完成任务仍可读取。查看服务状态和日志：

```bash
docker compose ps
docker compose logs -f straightlens
```

停止服务但保留任务数据：

```bash
docker compose down
```

如果确认要同时删除任务数据，再执行：

```bash
docker compose down -v
```

镜像内包含 IPOL 算法实现，使用和发布时仍须遵守项目及上游的 CC BY-NC-SA 3.0 许可和署名要求。

Python 锁文件记录了本次验证环境。若在不同 Python 版本上无法解析锁定版本，可用 `uv pip install --python .venv-local/bin/python './backend[test]'` 安装声明的兼容依赖后重新运行测试。

## 验证

```bash
PYTHONPATH=backend .venv-local/bin/python -m pytest backend/tests -q
.venv-local/bin/python scripts/evaluate.py --phase policy
```

评估脚本自动生成合成样例，在 `evaluation/results` 保存每张图片的输出、参数、诊断和汇总报告。可用 `--output-dir evaluation/weak-results --verify-controls` 指定独立输出并在受保护正反对照回退时返回非零退出码；示例按实际图像内容解码，不依赖扩展名正确。真实截图没有真值，只能报告算法决策，不能据此证明它们没有畸变。

评估说明和可复现样例见 `evaluation/README.md`。已运行服务时，可在 `frontend` 内执行 `node scripts/verify-examples.mjs`，通过真实浏览器复测合成样例的上传、对比和下载。

浏览器端到端测试需要本地应用已运行，并安装 Chrome。先运行评估脚本生成测试图片，然后执行：

```bash
cd frontend
pnpm test
```

测试包含实际算法上传、完成状态、对比、原尺寸查看、下载、再次上传、损坏图片错误和手机视口。

## 整图反算的使用方式

校正完成后下载裁切版或未裁切版，在外部绘制、编辑或替换图片内容，然后在同一结果页的“反向映射”区域上传整张图。系统按尺寸或宽高比识别参考版本；无法唯一识别时再选择“基于裁切图”或“基于未裁切图”。支持等比例缩放，比例误差容限 0.1%；不自动猜测额外旋转、任意裁剪或拉伸。

输出始终采用原图统一方向后的尺寸，上传图覆盖区域整体映射到原始坐标，范围外保留原图。未修改的图也会处理，不会出现“未检测到涂鸦”拦截。仅成功采纳校正模型的任务支持反算；保留原图的任务不能使用被拒绝的模型。

反算不是无损撤销，重复插值会损失细节，裁掉的信息不会补全。边界采用保守覆盖保护，会多保留少量原图像素；外部缩图或有损编码已经融入有效内容的色差不能保证消除。当前没有额外的透视模型。反算输入须为不透明 JPG/PNG/WebP 静态图，仍受 20 MiB / 2000 万像素限制。每次上传产生独立任务，使用同一有界队列。

旧任务在记录齐全时可由保存模型生成未裁切版，不重新估计。任务及几何文件默认保留 24 小时；需要继续编辑时请在过期前完成上传，或重新导入原图创建任务。

可执行 `scripts/evaluate_reverse.py` 生成反算矩阵；应用运行时，在 frontend 内执行 `node scripts/verify-reverse.mjs` 验证整图上传并保存页面截图。

## 算法边界

这不是通用图像修复模型。它依赖画面中有足够的实际直线结构，对建筑、室内和规则结构通常更适用；自然风景、人像或天然曲线可能缺少可靠依据。字幕和画面叠加也可能干扰估计。

全自动结果分为“已校正”“保留原图”“处理失败”。依据不足、改善不明显或候选不一致时保留原图。保留原图不等于已证明图片无畸变。图片含非不透明 alpha 时，当前版本保留原图，避免透明边界被误当作场景直线。

只处理径向镜头畸变；不自动消除正常透视，不把球场展开成俯视图，不补全画面外内容，也不保证适配任意鱼眼投影。

质量阈值是工程启发式，未校准成准确率或概率。虽然按整条曲线留出检查，初始线条检测及共识轮廓发现仍使用整张图片；它不是独立的真值验证。弱分支优先使用固定几何中心和单径向参数，限制最大位移并保护原本较直的长边；不能保证识别所有天然圆弧或后加图形。自动裁切也会损失部分视野。

每次原生估计有超时限制，参数估计总预算 120 秒，全任务预算 180 秒（在处理阶段与映射分块检查）。小样本实测不代表所有图片的处理速度。

## 来源与许可

算法来自 IPOL：
https://www.ipol.im/pub/art/2016/130/

使用 `ldm_pq2p_io-20220510.tar.gz`，校验和、原始许可和本地最小修正记录见 `third_party/ipol/UPSTREAM.md`。其许可为 CC BY-NC-SA 3.0，仅限非商业用途，并要求署名和相同方式共享。保留所有上游声明。本封装也按 CC BY-NC-SA 3.0 提供；其他依赖保持各自许可。

上游建筑图保留原作者的许可与署名，仅作为算法验证样例。公开仓库不包含用户提供的真实图片或相关页面截图；本地可自行放入 `examples/` 进行评估。

StraightLens 当前整体使用 CC BY-NC-SA 3.0。这个许可允许非商业使用、署名和相同方式共享；它不是 MIT 或 Apache-2.0。原因是项目包含同样受 CC BY-NC-SA 3.0 约束的 IPOL 算法实现。其他依赖和示例图片仍按各自的版权和许可处理。

## 开发结构

- `backend/app/engine`：原生程序边界、模型与映射、自动决策及处理流水线。
- `backend/app/images.py`：解码、方向、ICC、透明度与预览。
- `backend/app/jobs.py`：队列、生命周期和任务文件清理。
- `backend/app/main.py`：任务 API 与同源静态页面。
- `frontend/src`：React 图片工作台。
- `scripts/evaluate.py`：可重复的本地评估。

当前为个人本机版本，尚未设计多用户权限和公网部署。欢迎通过 GitHub issue 或 pull request 提交问题和改进，开发命令见 `CONTRIBUTING.md`。
