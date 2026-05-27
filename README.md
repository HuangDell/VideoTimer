# VideoTimer

VideoTimer 是一个用于小鼠视频 freezing 区间标注的桌面工具。当前默认入口是 PySide6 标注工作台：左侧浏览视频文件夹，中间播放和编辑时间轴，右侧查看与修改已标注区间。

## 功能

- 递归浏览文件夹，双击视频加载。
- 播放、暂停、重置、倍速和全屏查看视频。
- 在时间轴中显示绿色 freezing 区间。
- 拖动区间左右端点修改起止帧。
- 在右侧表格单击起止时间跳转，双击起止时间编辑。
- 按 `Z` 记录区间起止点，也可以在时间轴空白处拖拽创建区间。
- 鼠标悬停时间轴显示该时刻缩略图。
- 自动检测 freezing 候选区间，确认后覆盖导入并支持撤销。
- 标注保存为同名旁路 JSON，例如 `mouse.avi` 对应 `mouse.videotimer.json`。
- 复用旧版 Excel 导出格式。
- 支持 `Ctrl+S` 保存、`Ctrl+Z` 撤销、`Ctrl+Y` 重做。

## 安装

```bash
pip install -r requirements.txt
```

依赖包括：

- PySide6
- opencv-python
- numpy
- pandas
- openpyxl
- pillow

## 运行

```bash
python main.py
```

旧 Tkinter 多实例界面仍保留在 `legacy_main()` 中，可在 Python 交互或临时脚本中调用：

```python
from main import legacy_main

legacy_main()
```

旧版界面额外依赖 `keyboard` 包。

## 标注数据

旁路 JSON 使用帧坐标保存区间，避免毫秒浮点误差。核心结构如下：

```json
{
  "schema_version": 1,
  "video_metadata": {
    "filename": "mouse.avi",
    "fps": 30.0,
    "total_frames": 18000,
    "duration": 600.0
  },
  "intervals": [
    {
      "id": "uuid",
      "label": "freezing",
      "start_frame": 120,
      "end_frame": 180
    }
  ],
  "updated_at": "2026-05-27T00:00:00+00:00"
}
```

首版只开放单一 `freezing` 标签，区间不允许重叠。

## 测试

```bash
python -m unittest discover -s tests -v
```

当前仓库包含自动检测服务测试和标注模型测试。若 Windows 终端提示找不到 `python` 或 `py`，请先安装 Python 并确认它在 `PATH` 中。
