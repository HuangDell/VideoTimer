"""时间格式化工具类"""
from typing import Union


class TimeFormatter:
    """时间格式化工具类 - 单例模式"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TimeFormatter, cls).__new__(cls)
        return cls._instance

    @staticmethod
    def format_time(seconds: float) -> str:
        """格式化时间为 HH:MM:SS.mmm 格式
        
        Args:
            seconds: 秒数
            
        Returns:
            格式化后的时间字符串，格式：HH:MM:SS.mmm
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

    @staticmethod
    def format_time_for_excel(seconds: float) -> str:
        """Excel格式时间（分.秒.毫秒）
        
        Args:
            seconds: 秒数
            
        Returns:
            Excel格式时间字符串，格式：分.秒.毫秒
        """
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        secs = int(remaining_seconds)
        milliseconds = int((remaining_seconds - secs) * 100)
        return f"{minutes}.{secs:02d}.{milliseconds:02d}"

    @staticmethod
    def parse_time_string(time_str: str) -> float:
        """解析时间字符串为秒数
        
        Args:
            time_str: 时间字符串，格式：HH:MM:SS.mmm
            
        Returns:
            秒数
        """
        try:
            parts = time_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        except (ValueError, IndexError):
            return 0.0

