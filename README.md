# 视频计时器 (Video Timer)

一个用于视频播放和时间点记录的工具，支持多实例运行。

## 项目结构

本项目采用模块化设计，遵循MVC架构模式和多种设计模式，具有高可扩展性。

```
VideoTimer/
├── main.py                 # 主入口文件
├── models/                  # 数据模型层
│   ├── __init__.py
│   ├── video_model.py      # 视频数据模型
│   └── record_model.py     # 记录数据模型
├── views/                   # 视图层（UI）
│   ├── __init__.py
│   ├── main_window.py       # 主窗口
│   ├── video_panel.py      # 视频播放面板
│   ├── timing_panel.py     # 计时面板
│   └── instance_selector.py # 实例选择对话框
├── controllers/             # 控制器层（业务逻辑）
│   ├── __init__.py
│   ├── video_controller.py # 视频控制器
│   ├── record_controller.py # 记录控制器
│   └── main_controller.py  # 主控制器
├── services/                # 服务层
│   ├── __init__.py
│   ├── video_service.py    # 视频服务
│   ├── keyboard_service.py # 键盘监听服务
│   └── export_service.py   # 导出服务（策略模式）
└── utils/                   # 工具类
    ├── __init__.py
    ├── time_formatter.py   # 时间格式化工具（单例模式）
    └── config.py           # 配置管理（单例模式）
```

## 设计模式

### 1. MVC架构模式
- **Model（模型）**: `models/` - 封装数据结构和业务数据
- **View（视图）**: `views/` - 负责UI展示
- **Controller（控制器）**: `controllers/` - 协调模型和视图，处理业务逻辑

### 2. 单例模式
- `TimeFormatter`: 时间格式化工具类
- `Config`: 配置管理类

### 3. 策略模式
- `ExportService`: 支持多种导出格式（Excel等），易于扩展新的导出策略

### 4. 观察者模式
- 通过回调函数实现事件通知机制
- 视频帧更新、键盘事件等

### 5. 工厂模式
- 通过`MainController`统一创建和组装各个组件

## 功能特性

1. **视频播放控制**
   - 加载视频文件
   - 播放/暂停/停止
   - 进度条拖拽和点击跳转
   - 全屏模式

2. **时间点记录**
   - 手动记录时间点
   - 键盘快捷键记录（可配置）
   - 记录列表管理（添加/删除/清空）
   - 双击记录跳转到对应视频位置

3. **数据导出**
   - 导出到Excel
   - 包含多个工作表：原始记录、区间统计、区间详情、按分钟统计

4. **多实例支持**
   - 支持同时运行多个实例
   - 每个实例可配置独立的快捷键

## 安装依赖

```bash
pip install opencv-python keyboard pandas openpyxl pillow
```

## 运行

```bash
python main.py
```

## 扩展性

### 添加新的导出格式

1. 在`services/export_service.py`中创建新的策略类，继承`ExportStrategy`
2. 实现`export`方法
3. 在`ExportService`中注册新策略：

```python
export_service.register_strategy('csv', CsvExportStrategy())
```

### 添加新的功能模块

1. 在相应的层（models/views/controllers/services）创建新模块
2. 在`MainController`中集成新模块
3. 通过依赖注入的方式连接各个组件

## 代码特点

- **高内聚低耦合**: 每个模块职责单一，模块间通过接口交互
- **易于测试**: 各层分离，便于单元测试
- **易于维护**: 清晰的目录结构和命名规范
- **类型注解**: 使用类型提示提高代码可读性
- **文档完善**: 每个类和函数都有详细的文档字符串

