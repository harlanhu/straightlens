# StraightLens 页面优化与镜头畸变报告

## 目标

StraightLens 处理完成后，用户可以知道图片是否发生了可靠的镜头畸变校正、畸变属于哪一类、系统修正了多少，以及校正后保留了多少画面。

页面展示的是根据当前图片估计出的几何畸变。它不把估计值包装成真实焦距、镜头型号或传感器参数。图片 EXIF 中存在的相机与镜头信息单独归入照片元数据。

## 一阶段：页面与报告

页面保留黑色工作台和荧光绿色状态色，视觉层级调整为“处理结果 → 镜头畸变报告 → 下载 → 自动处理流程”。顶部删除“仅在本机处理”，底部删除“本地处理”等部署描述，工作区底部只保留文件名、文件大小和支持格式。

处理完成后，右侧显示镜头畸变报告：

- 畸变方向：桶形、枕形、胡须形或轻微畸变。
- 校正强度：轻微、低、中等、明显或强烈。
- 估计畸变中心：像素坐标和相对位置。
- 边缘最大修正比例。
- 画面保留比例。
- 输入尺寸、输出尺寸和处理耗时。

“查看技术参数”展开后显示模型类型、径向系数、估计画布、渲染缩放、自动裁切和模型版本。

没有可靠模型时显示原因，例如“没有找到足够可靠的直线结构”，不显示空白参数或伪造数值。

## 二阶段：畸变可视化与照片元数据

报告提供“显示畸变网格”操作，用于帮助用户理解畸变中心和校正趋势。网格是辅助示意，不作为精确测量结果。

如果图片包含 EXIF，则单独显示相机、镜头、焦距和光圈等照片元数据。EXIF 信息与算法估计的畸变信息分开，避免把照片元数据和估计模型混为一谈。

## API

任务接口 `GET /api/jobs/{id}` 新增 `distortion` 字段。校正成功时的核心结构如下：

```json
{
  "distortion": {
    "available": true,
    "profile": "barrel",
    "profile_label": "桶形畸变",
    "strength": "medium",
    "strength_label": "中等",
    "edge_correction_percent": 4.6,
    "center": {
      "x": 401.6,
      "y": 270.1,
      "x_percent": 50.2,
      "y_percent": 49.7,
      "offset_x": 1.6,
      "offset_y": 0.1
    },
    "model": {
      "type": "div",
      "label": "径向除法模型",
      "coefficients": [0.0123, -0.0011],
      "estimation_size": {"width": 1200, "height": 816},
      "render_scale": 1.003,
      "version": 1
    },
    "crop": {
      "left": 8,
      "top": 4,
      "right": 9,
      "bottom": 5,
      "retained_area": 0.914
    }
  }
}
```

未应用校正时 `available` 为 `false`，并返回 `reason_code`。前端不直接读取或展示完整 `diagnostics.json`。

## 实现位置

- `backend/app/distortion_report.py`：读取最终变换记录，计算畸变方向、强度、中心、裁切和 EXIF 摘要。
- `backend/app/schemas.py`：为任务响应增加 `distortion` 字段。
- `backend/app/main.py`：在任务查询接口中生成报告。
- `frontend/src/DistortionReport.tsx`：报告摘要和技术参数。
- `frontend/src/DistortionGrid.tsx`：畸变网格示意。
- `frontend/src/App.tsx`：页面文案、结果层级和报告入口。
- `frontend/src/styles.css`：报告卡片、网格、响应式布局和无障碍焦点样式。

## 计算约定

畸变方向通过以估计畸变中心为中心的多半径采样得到，不仅根据单个系数的正负判断。边缘修正比例来自采样点在校正前后的径向变化。画面保留比例来自实际裁切框与原始画布面积的比值。

“估计畸变中心”表示模型参数中的中心，不等同于经过硬件标定得到的真实光学中心。焦距、传感器尺寸、真实视场角和通用镜头配置文件不从单张图片中推断。

## 验收

使用以下样例验证：

- `evaluation/generated/grid_barrel.png`：显示桶形畸变报告。
- `evaluation/generated/grid_pincushion.png`：显示枕形畸变报告。
- `evaluation/generated/grid_offcenter.png`：显示偏移畸变中心。
- `evaluation/generated/grid_identity.png`：显示轻微畸变或保留原图。
- `evaluation/generated/blank.png`：显示没有可靠模型的原因。

还需要验证：

- 报告技术参数默认折叠并可通过键盘展开。
- 网格示意不会产生横向滚动。
- 375px 宽度下报告和下载操作可用。
- `prefers-reduced-motion` 开启时不播放处理动画。
- 原图、结果、裁切下载、未裁切下载和反向映射继续正常。
- 容器重启后历史任务仍能读取报告。
