"""导出服务类 - 使用策略模式支持多种导出格式"""
import pandas as pd
from typing import List, Dict, Any, Tuple, Optional
from abc import ABC, abstractmethod
from models.record_model import RecordModel, TimeRecord
from models.video_model import VideoModel
from utils.time_formatter import TimeFormatter
from views.export_dialog import ExportType


# 各导出类型的时间区间配置（秒）
EXPORT_INTERVALS: Dict[ExportType, List[Tuple[float, float]]] = {
    ExportType.LOOMING: [
        (0, 60),      # 0:00:00 - 1:00:00
        (60, 120),    # 1:00:00 - 2:00:00
        (120, 180),   # 2:00:00 - 3:00:00
        (181, 244),   # 3:01:00 - 4:04:00
        (244, 307),   # 4:04:00 - 5:07:00
        (307, 370),   # 5:07:00 - 6:10:00
    ],
    ExportType.TRAINING: [
        (0, 60),      # 0:00:00 - 1:00:00
        (60, 120),    # 1:00:00 - 2:00:00
        (120, 180),   # 2:00:00 - 3:00:00
        (180, 242),   # 3:00:00 - 4:02:00
        (242, 304),   # 4:02:00 - 5:04:00
        (304, 366),   # 5:04:00 - 6:06:00
    ],
    ExportType.OFC: [
        (0, 60),      # 0:00:00 - 1:00:00
        (60, 120),    # 1:00:00 - 2:00:00
        (120, 180),   # 2:00:00 - 3:00:00
        (180, 240),   # 3:00:00 - 4:00:00
        (240, 300),   # 4:00:00 - 5:00:00
        (300, 360),   # 5:00:00 - 6:00:00
        (360, 420),   # 6:00:00 - 7:00:00
        (420, 480),   # 7:00:00 - 8:00:00
        (480, 540),   # 8:00:00 - 9:00:00
    ],
    ExportType.TEST: [
        (0, 60),      # 0:00:00 - 1:00:00
        (60, 120),    # 1:00:00 - 2:00:00
        (120, 180),   # 2:00:00 - 3:00:00
        (180, 240),   # 3:00:00 - 4:00:00
        (240, 300),   # 4:00:00 - 5:00:00
    ],
}

# 需要计算前3分钟额外统计的导出类型
EXPORT_TYPES_WITH_FIRST_3MIN = {ExportType.LOOMING, ExportType.TRAINING}


class ExportStrategy(ABC):
    """导出策略抽象基类"""
    
    @abstractmethod
    def export(self, records: List[TimeRecord], video_model: VideoModel, file_path: str,
               export_type: Optional[ExportType] = None) -> bool:
        """导出数据
        
        Args:
            records: 记录列表
            video_model: 视频模型
            file_path: 文件路径
            export_type: 导出类型（用于自定义时间区间计算）
            
        Returns:
            是否导出成功
        """
        pass


class ExcelExportStrategy(ExportStrategy):
    """Excel导出策略"""
    
    def __init__(self):
        self.time_formatter = TimeFormatter()

    def export(self, records: List[TimeRecord], video_model: VideoModel, file_path: str,
               export_type: Optional[ExportType] = None) -> bool:
        """导出到Excel"""
        try:
            record_model = RecordModel()
            # 临时设置记录以便计算统计
            record_model._records = records

            # Sheet 1: 原始成对数据
            paired_data = self._create_paired_data(records)
            df_paired = pd.DataFrame(paired_data)

            # 添加汇总信息
            summary_data = self._create_summary_data(records, video_model)
            summary_df = pd.DataFrame(summary_data)
            final_df_paired = pd.concat([df_paired, summary_df], ignore_index=True)

            # Sheet 2: 区间统计
            total_duration, intervals = self._calculate_interval_statistics(record_model)
            stats_data = self._create_stats_data(total_duration, intervals)
            df_stats = pd.DataFrame(stats_data)

            # 区间详情
            detail_data = self._create_detail_data(intervals)
            df_detail = pd.DataFrame(detail_data)

            # Sheet 3: 按自定义区间统计（根据导出类型）
            if export_type and export_type in EXPORT_INTERVALS:
                custom_intervals = EXPORT_INTERVALS[export_type]
                include_first_3min = export_type in EXPORT_TYPES_WITH_FIRST_3MIN
                custom_stats = record_model.calculate_custom_interval_statistics(custom_intervals)
                custom_data = self._create_custom_interval_data(
                    custom_stats, custom_intervals, record_model, include_first_3min
                )
                df_custom = pd.DataFrame(custom_data)
                sheet_name = f'Freezing统计({export_type.value})'
            else:
                # 默认使用原来的按分钟统计
                minute_stats = record_model.calculate_minute_statistics()
                custom_data = self._create_minute_data(minute_stats, total_duration)
                df_custom = pd.DataFrame(custom_data)
                sheet_name = '按分钟统计'

            # 写入Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Sheet 1: 原始记录
                final_df_paired.to_excel(writer, sheet_name='原始记录', index=False)
                worksheet1 = writer.sheets['原始记录']
                worksheet1.column_dimensions['A'].width = 15
                worksheet1.column_dimensions['B'].width = 15
                worksheet1.column_dimensions['C'].width = 15

                # Sheet 2: 区间统计
                df_stats.to_excel(writer, sheet_name='区间统计', index=False)
                worksheet2 = writer.sheets['区间统计']
                worksheet2.column_dimensions['A'].width = 25
                worksheet2.column_dimensions['B'].width = 30
                worksheet2.column_dimensions['C'].width = 20

                # Sheet 3: 区间详情
                df_detail.to_excel(writer, sheet_name='区间详情', index=False)
                worksheet3 = writer.sheets['区间详情']
                worksheet3.column_dimensions['A'].width = 25
                worksheet3.column_dimensions['B'].width = 30
                worksheet3.column_dimensions['C'].width = 20

                # Sheet 4: 自定义区间统计
                df_custom.to_excel(writer, sheet_name=sheet_name, index=False)
                worksheet4 = writer.sheets[sheet_name]
                worksheet4.column_dimensions['A'].width = 25
                worksheet4.column_dimensions['B'].width = 30
                worksheet4.column_dimensions['C'].width = 15

            return True
        except Exception as e:
            print(f"导出错误: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _create_paired_data(self, records: List[TimeRecord]) -> List[Dict[str, Any]]:
        """创建成对数据"""
        paired_data = []
        for i in range(0, len(records), 2):
            start_record = records[i]
            start_time_formatted = self.time_formatter.format_time_for_excel(start_record.video_time)

            if i + 1 < len(records):
                end_record = records[i + 1]
                end_time_formatted = self.time_formatter.format_time_for_excel(end_record.video_time)
                interval_seconds = end_record.video_time - start_record.video_time
                interval_formatted = self.time_formatter.format_time_for_excel(interval_seconds)

                paired_data.append({
                    '启(分)': start_time_formatted,
                    '止(分)': end_time_formatted,
                    '间隔时间': interval_formatted
                })
            else:
                paired_data.append({
                    '启(分)': start_time_formatted,
                    '止(分)': '未完成',
                    '间隔时间': '未完成'
                })
        return paired_data

    def _create_summary_data(self, records: List[TimeRecord], video_model: VideoModel) -> List[Dict[str, Any]]:
        """创建汇总数据"""
        total_video_time = video_model.duration
        total_time_formatted = self.time_formatter.format_time_for_excel(total_video_time)

        return [
            {'启(分)': '', '止(分)': '', '间隔时间': ''},
            {'启(分)': '汇总信息', '止(分)': '', '间隔时间': ''},
            {'启(分)': f'视频文件: {video_model.video_path}', '止(分)': f'总记录点数: {len(records)}',
             '间隔时间': f'视频总时长: {total_time_formatted}'},
            {'启(分)': f'完整配对数: {len(records) // 2}', '止(分)': f'未配对数: {len(records) % 2}',
             '间隔时间': f'视频FPS: {video_model.video_fps:.2f}'}
        ]

    def _calculate_interval_statistics(self, record_model: RecordModel) -> Tuple[float, List[Dict[str, Any]]]:
        """计算区间统计"""
        intervals = record_model.get_paired_intervals()
        total_duration = sum(interval['duration'] for interval in intervals)
        return total_duration, intervals

    def _create_stats_data(self, total_duration: float, intervals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """创建统计数据"""
        return [
            {'统计项': '区间总数', '数值': len(intervals), '单位': '个'},
            {'统计项': '区间总时长', '数值': f"{total_duration:.3f}", '单位': '秒'},
            {'统计项': '区间总时长', '数值': self.time_formatter.format_time_for_excel(total_duration),
             '单位': '分.秒.毫秒'},
            {'统计项': '区间总时长', '数值': self.time_formatter.format_time(total_duration), '单位': '时:分:秒'},
            {'统计项': '', '数值': '', '单位': ''},
            {'统计项': '详细区间列表', '数值': '', '单位': ''}
        ]

    def _create_detail_data(self, intervals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """创建详情数据"""
        detail_data = []
        for idx, interval in enumerate(intervals, 1):
            detail_data.append({
                '区间编号': f'区间 {idx}',
                '起止时间': f"{interval['start']:.3f}s - {interval['end']:.3f}s",
                '区间长度(s)': f"{interval['duration']:.3f}"
            })
        return detail_data

    def _create_minute_data(self, minute_stats: Dict[int, float], total_duration: float) -> List[Dict[str, Any]]:
        """创建分钟统计数据"""
        minute_data = []
        sorted_minutes = sorted(minute_stats.keys())

        for minute in sorted_minutes:
            duration = minute_stats[minute]
            minute_data.append({
                '分钟区间': f"第 {minute + 1} 分钟 ({minute}:00 - {minute}:59)",
                '区间时长（秒）': f"{duration:.3f}",
                '区间时长（格式化）': self.time_formatter.format_time_for_excel(duration),
                '占该分钟比例': f"{(duration / 60 * 100):.2f}%"
            })

        # 添加总计行
        minute_data.append({
            '分钟区间': '总计',
            '区间时长（秒）': f"{total_duration:.3f}",
            '区间时长（格式化）': self.time_formatter.format_time_for_excel(total_duration),
            '占该分钟比例': ''
        })

        return minute_data

    def _format_interval_range(self, start_sec: float, end_sec: float) -> str:
        """格式化时间区间范围
        
        Args:
            start_sec: 开始秒数
            end_sec: 结束秒数
            
        Returns:
            格式化的时间范围字符串，如 "0:00:00-1:00:00"
        """
        def sec_to_time_str(seconds: float) -> str:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours}:{minutes:02d}:{secs:02d}"
        
        return f"{sec_to_time_str(start_sec)}-{sec_to_time_str(end_sec)}"

    def _format_freezing_time(self, seconds: float) -> str:
        """格式化freezing时间（秒.毫秒，毫秒两位数）
        
        Args:
            seconds: 秒数
            
        Returns:
            格式化的时间字符串，如 "45.32"
        """
        whole_seconds = int(seconds)
        # 取两位小数（相当于百分之一秒/10毫秒精度）
        centiseconds = int((seconds - whole_seconds) * 100)
        return f"{whole_seconds}.{centiseconds:02d}"

    def _create_custom_interval_data(self, custom_stats: Dict[Tuple[float, float], float],
                                     intervals: List[Tuple[float, float]],
                                     record_model: RecordModel,
                                     include_first_3min: bool = False) -> List[Dict[str, Any]]:
        """创建自定义区间统计数据
        
        Args:
            custom_stats: 自定义区间统计结果
            intervals: 区间列表
            record_model: 记录模型
            include_first_3min: 是否包含前3分钟额外统计
            
        Returns:
            统计数据列表
        """
        result_data = []
        total_freezing = 0.0
        
        for start_sec, end_sec in intervals:
            interval_duration = end_sec - start_sec
            freezing_time = custom_stats.get((start_sec, end_sec), 0.0)
            total_freezing += freezing_time
            
            # 计算百分比
            percentage = (freezing_time / interval_duration * 100) if interval_duration > 0 else 0.0
            
            result_data.append({
                '时间区间': self._format_interval_range(start_sec, end_sec),
                'freezing总时间（秒.毫秒）': self._format_freezing_time(freezing_time),
                '百分比': f"{percentage:.2f}%"
            })
        
        # 添加总计行
        result_data.append({
            '时间区间': '总',
            'freezing总时间（秒.毫秒）': self._format_freezing_time(total_freezing),
            '百分比': ''
        })
        
        # 如果需要计算前3分钟额外统计
        if include_first_3min:
            # 计算前3分钟（0-180秒）的freezing总时间
            first_3min_freezing = record_model.calculate_freezing_in_range(0, 180)
            first_3min_percentage = (first_3min_freezing / 180 * 100) if first_3min_freezing > 0 else 0.0
            
            result_data.append({
                '时间区间': '',
                'freezing总时间（秒.毫秒）': '',
                '百分比': ''
            })
            result_data.append({
                '时间区间': '前3分钟合计',
                'freezing总时间（秒.毫秒）': self._format_freezing_time(first_3min_freezing),
                '百分比': f"{first_3min_percentage:.2f}%"
            })
        
        return result_data


class ExportService:
    """导出服务类 - 使用策略模式"""
    
    def __init__(self):
        self._strategies: Dict[str, ExportStrategy] = {
            'excel': ExcelExportStrategy()
        }

    def register_strategy(self, name: str, strategy: ExportStrategy):
        """注册导出策略
        
        Args:
            name: 策略名称
            strategy: 策略实例
        """
        self._strategies[name] = strategy

    def export(self, format_type: str, records: List[TimeRecord], 
               video_model: VideoModel, file_path: str,
               export_type: Optional[ExportType] = None) -> bool:
        """导出数据
        
        Args:
            format_type: 导出格式（如 'excel'）
            records: 记录列表
            video_model: 视频模型
            file_path: 文件路径
            export_type: 导出类型（用于自定义时间区间计算）
            
        Returns:
            是否导出成功
        """
        if format_type not in self._strategies:
            raise ValueError(f"不支持的导出格式: {format_type}")

        return self._strategies[format_type].export(records, video_model, file_path, export_type)

