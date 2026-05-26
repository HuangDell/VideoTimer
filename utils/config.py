"""配置管理类 - 单例模式"""
from typing import Dict, Any


class Config:
    """配置管理类"""
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialize_defaults()
        return cls._instance

    def _initialize_defaults(self):
        """初始化默认配置"""
        self._config = {
            'window_width': 1400,
            'window_height': 900,
            'min_window_width': 800,
            'min_window_height': 600,
            'default_record_key': 'z',
            'update_interval': 0.1,  # 显示更新间隔（秒）
            'keyboard_check_interval': 0.01,  # 键盘检查间隔（秒）
            'keyboard_debounce': 0.3,  # 键盘防抖时间（秒）
            'max_instances': 4,
            'default_instances': 1,
            'default_keys': ['z', 'x', 'c', 'v'],
            'freezing_sample_rate': 10.0,
            'freezing_analysis_width': 320,
            'freezing_pixel_diff_threshold': 25,
            'freezing_motion_threshold': 0.0004,
            'freezing_min_duration': 0.5,
            'freezing_merge_gap': 0.3,
            'freezing_min_non_freeze_gap': 0.2,
            'freezing_smoothing_window': 0.3,
        }

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        """设置配置值
        
        Args:
            key: 配置键
            value: 配置值
        """
        self._config[key] = value

    def update(self, config_dict: Dict[str, Any]):
        """批量更新配置
        
        Args:
            config_dict: 配置字典
        """
        self._config.update(config_dict)

