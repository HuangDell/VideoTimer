# 重构说明

## 当前目标

项目已移除旧 Tkinter UI，只保留 PySide6 标注工作台。原先集中在 `views/qt_workbench.py` 的 Qt 实现被拆分为 `views/qt/` 子包，降低单文件复杂度，并把 UI 组件、后台任务、撤销命令和会话状态分开维护。

## 架构概览

### Models
- `VideoModel`: 视频路径、FPS、帧数、当前帧和 OpenCV capture 状态。
- `AnnotationModel`: 旁路 JSON 标注文档、区间校验、保存和加载。
- `RecordModel`: 复用旧 Excel 导出所需的成对时间点模型。
- `ExportType`: 共享导出类型枚举，避免服务层依赖 UI 对话框。

### Services
- `ExportService`: Excel 导出策略和实验类型时间段统计。
- `FreezingDetectionService`: freezing 候选区间检测。
- `video_crop_service`: 上下鼠逻辑视频名、虚拟裁剪和分割比例处理。
- `annotation_export_adapter`: 将区间标注适配为旧 Excel 导出记录。

### Views
- `views/qt/workbench.py`: 主窗口、菜单、工具栏、跨组件协调和业务流程。
- `views/qt/widgets/video_canvas.py`: 视频帧转 pixmap 和等比画布。
- `views/qt/widgets/split_preview.py`: 上下鼠分割线预览对话框。
- `views/qt/widgets/timeline.py`: 进度轨、区间轨、缩放和平移。
- `views/qt/widgets/file_panel.py`: 视频文件浏览面板。
- `views/qt/widgets/player_panel.py`: 视频标签页、播放控制和时间轴组合面板。
- `views/qt/widgets/interval_panel.py`: 右侧区间表格与操作按钮。
- `views/qt/commands.py`: `QUndoStack` 使用的标注命令。
- `views/qt/workers.py`: Qt 线程中的自动检测 worker。
- `views/qt/session.py`: 每个逻辑视频标签页的会话状态和元数据。
- `views/qt/time_parsing.py`: 区间表格时间文本解析。

`views/qt_workbench.py` 仅作为兼容导入层保留，实际实现位于 `views/qt/`。

## 设计原则

- UI 层只保留 PySide6，不再维护 Tkinter 入口或旧控制器。
- 服务层不依赖具体 UI 框架；导出类型等共享概念放入 `models/`。
- Qt 控件通过 signals 暴露交互，主窗口负责连接业务逻辑。
- 标注变更统一走 `QUndoStack` 命令，保持撤销、dirty 状态和视图刷新一致。
- 与已有旁路 JSON、自动检测、上下鼠拆分和 Excel 导出格式保持兼容。

## 验证

```bash
python3 -m unittest discover -s tests -v
PYTHONPYCACHEPREFIX=/private/tmp/videotimer-pycache python3 -m compileall -q main.py models services utils views tests
```
