# 重构说明

## 重构目标

将原有的单一模块 `Timer.py` 重构为模块化、高可扩展性的架构，遵循设计模式最佳实践。

## 重构前后对比

### 重构前
- 单一文件 `Timer.py` (1124行)
- 所有功能耦合在一个类中
- 难以扩展和维护
- 缺乏清晰的职责分离

### 重构后
- 模块化架构，分为5个主要层次
- 每个模块职责单一
- 易于扩展和维护
- 遵循MVC架构和多种设计模式

## 架构设计

### 1. 分层架构（MVC）

#### Models（数据模型层）
- `VideoModel`: 封装视频相关数据（路径、FPS、帧数等）
- `RecordModel`: 管理时间记录数据，提供统计功能

#### Views（视图层）
- `MainWindow`: 主窗口容器
- `VideoPanel`: 视频播放UI组件
- `TimingPanel`: 时间记录UI组件
- `InstanceSelector`: 实例选择对话框

#### Controllers（控制器层）
- `VideoController`: 协调视频相关的模型、服务和视图
- `RecordController`: 协调记录相关的模型、服务和视图
- `MainController`: 主控制器，组装所有组件

#### Services（服务层）
- `VideoService`: 视频播放逻辑服务
- `KeyboardService`: 全局键盘监听服务
- `ExportService`: 导出服务（使用策略模式）

#### Utils（工具层）
- `TimeFormatter`: 时间格式化工具（单例模式）
- `Config`: 配置管理（单例模式）

## 设计模式应用

### 1. MVC模式
- **Model**: 数据模型层，封装业务数据
- **View**: 视图层，负责UI展示
- **Controller**: 控制器层，协调模型和视图

### 2. 单例模式
- `TimeFormatter`: 确保全局只有一个时间格式化实例
- `Config`: 确保全局配置一致性

### 3. 策略模式
- `ExportService`: 支持多种导出格式，易于扩展
  - 当前实现：`ExcelExportStrategy`
  - 可扩展：`CsvExportStrategy`, `JsonExportStrategy` 等

### 4. 观察者模式
- 通过回调函数实现事件通知
- 视频帧更新、键盘事件、窗口事件等

### 5. 依赖注入
- 控制器通过构造函数接收依赖
- 便于测试和替换实现

## 改进点

### 1. 可扩展性
- **新增导出格式**: 只需实现新的策略类并注册
- **新增功能模块**: 在相应层创建新模块，通过控制器集成
- **替换实现**: 通过接口和依赖注入，易于替换实现

### 2. 可维护性
- **职责分离**: 每个类职责单一，易于理解
- **模块化**: 相关功能集中在同一模块
- **文档完善**: 每个类和函数都有详细文档

### 3. 可测试性
- **依赖注入**: 便于mock和单元测试
- **分层架构**: 可以独立测试每一层
- **接口清晰**: 明确的输入输出

### 4. 代码质量
- **类型注解**: 使用类型提示提高代码可读性
- **错误处理**: 完善的异常处理机制
- **代码复用**: 工具类和服务可复用

## 文件结构

```
VideoTimer/
├── main.py                    # 入口文件（简化）
├── models/                    # 数据模型（2个文件）
├── views/                     # 视图层（4个文件）
├── controllers/               # 控制器层（3个文件）
├── services/                  # 服务层（3个文件）
└── utils/                     # 工具类（2个文件）
```

## 使用方式

运行方式保持不变：
```bash
python main.py
```

功能完全兼容原有版本，但内部架构更加清晰和可扩展。

## 扩展示例

### 添加CSV导出格式

1. 在 `services/export_service.py` 中添加：

```python
class CsvExportStrategy(ExportStrategy):
    def export(self, records, video_model, file_path):
        # 实现CSV导出逻辑
        pass
```

2. 注册策略：
```python
export_service.register_strategy('csv', CsvExportStrategy())
```

3. 使用：
```python
export_service.export('csv', records, video_model, file_path)
```

## 总结

通过这次重构，项目从单一文件转变为模块化架构，具有：
- ✅ 高可扩展性
- ✅ 清晰的职责分离
- ✅ 遵循设计模式最佳实践
- ✅ 易于测试和维护
- ✅ 保持原有功能完整性

