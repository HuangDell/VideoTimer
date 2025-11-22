"""记录数据模型"""
from typing import List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class TimeRecord:
    """时间记录数据类"""
    sequence: int
    video_time: float  # 视频时间（秒）
    interval: float = 0.0  # 与上一条记录的间隔（秒）
    frame: int = 0  # 帧号

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'sequence': self.sequence,
            'video_time': self.video_time,
            'interval': self.interval,
            'frame': self.frame,
        }


class RecordModel:
    """记录数据模型 - 管理所有时间记录"""
    
    def __init__(self):
        self._records: List[TimeRecord] = []

    @property
    def records(self) -> List[TimeRecord]:
        """获取所有记录"""
        return self._records.copy()

    @property
    def count(self) -> int:
        """获取记录数量"""
        return len(self._records)

    def add_record(self, video_time: float, frame: int = 0) -> TimeRecord:
        """添加记录
        
        Args:
            video_time: 视频时间（秒）
            frame: 帧号
            
        Returns:
            创建的记录对象
        """
        # 计算间隔
        interval = 0.0
        if self._records:
            interval = video_time - self._records[-1].video_time

        sequence = len(self._records) + 1
        record = TimeRecord(
            sequence=sequence,
            video_time=round(video_time, 3),
            interval=round(interval, 3),
            frame=frame
        )

        self._records.append(record)
        return record

    def delete_record(self, sequence: int) -> bool:
        """删除指定序号的记录
        
        Args:
            sequence: 记录序号（从1开始）
            
        Returns:
            是否删除成功
        """
        index = sequence - 1
        if 0 <= index < len(self._records):
            self._records.pop(index)
            self._recalculate_sequences()
            return True
        return False

    def delete_records(self, sequences: List[int]) -> int:
        """批量删除记录
        
        Args:
            sequences: 记录序号列表
            
        Returns:
            删除的记录数量
        """
        # 按降序排序，避免删除时索引错乱
        sequences = sorted(set(sequences), reverse=True)
        deleted_count = 0

        for seq in sequences:
            if self.delete_record(seq):
                deleted_count += 1

        return deleted_count

    def clear(self):
        """清空所有记录"""
        self._records.clear()

    def _recalculate_sequences(self):
        """重新计算序号和间隔时间"""
        for i, record in enumerate(self._records):
            record.sequence = i + 1
            if i == 0:
                record.interval = 0.0
            else:
                record.interval = round(record.video_time - self._records[i - 1].video_time, 3)

    def get_paired_intervals(self) -> List[Dict[str, Any]]:
        """获取成对的区间
        
        Returns:
            区间列表，每个区间包含 start, end, duration
        """
        intervals = []
        for i in range(0, len(self._records), 2):
            if i + 1 < len(self._records):
                start_time = self._records[i].video_time
                end_time = self._records[i + 1].video_time
                intervals.append({
                    'start': start_time,
                    'end': end_time,
                    'duration': end_time - start_time
                })
        return intervals

    def calculate_minute_statistics(self) -> Dict[int, float]:
        """计算按分钟分组的统计信息
        
        Returns:
            字典，键为分钟数，值为该分钟内的区间总时长
        """
        intervals = self.get_paired_intervals()
        minute_stats = {}

        for interval in intervals:
            start_time = interval['start']
            end_time = interval['end']

            # 计算开始和结束所在的分钟
            start_minute = int(start_time // 60)
            end_minute = int(end_time // 60)

            if start_minute == end_minute:
                # 区间在同一分钟内
                if start_minute not in minute_stats:
                    minute_stats[start_minute] = 0
                minute_stats[start_minute] += interval['duration']
            else:
                # 区间跨越多个分钟
                # 处理开始分钟
                next_minute_start = (start_minute + 1) * 60
                if start_minute not in minute_stats:
                    minute_stats[start_minute] = 0
                minute_stats[start_minute] += (next_minute_start - start_time)

                # 处理中间完整的分钟
                for minute in range(start_minute + 1, end_minute):
                    if minute not in minute_stats:
                        minute_stats[minute] = 0
                    minute_stats[minute] += 60

                # 处理结束分钟
                minute_start = end_minute * 60
                if end_minute not in minute_stats:
                    minute_stats[end_minute] = 0
                minute_stats[end_minute] += (end_time - minute_start)

        return minute_stats

