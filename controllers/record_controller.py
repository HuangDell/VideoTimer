"""记录控制器 - 协调记录模型、服务和视图"""
import threading
import time
from typing import List, Optional
import tkinter as tk
from models.record_model import RecordModel
from models.video_model import VideoModel
from services.keyboard_service import KeyboardService
from services.export_service import ExportService
from services.freezing_detection_service import (
    FreezingDetectionParams,
    FreezingDetectionService,
    FreezingInterval,
)
from views.timing_panel import TimingPanel
from views.export_dialog import ExportDialog, ExportType
from utils.time_formatter import TimeFormatter
from utils.config import Config
from tkinter import filedialog, messagebox


class RecordController:
    """记录控制器 - 负责时间记录相关的业务逻辑"""
    
    def __init__(self, record_model: RecordModel, video_model: VideoModel,
                 keyboard_service: KeyboardService, export_service: ExportService,
                 timing_panel: TimingPanel,
                 freezing_detection_service: Optional[FreezingDetectionService] = None):
        self.record_model = record_model
        self.video_model = video_model
        self.keyboard_service = keyboard_service
        self.export_service = export_service
        self.freezing_detection_service = freezing_detection_service or FreezingDetectionService()
        self.timing_panel = timing_panel
        self.time_formatter = TimeFormatter()
        self.config = Config()

        # 显示更新线程
        self._display_thread: Optional[threading.Thread] = None
        self._display_running = False
        self._detection_thread: Optional[threading.Thread] = None
        self._detection_running = False

        # 设置回调
        self._setup_callbacks()

    def _setup_callbacks(self):
        """设置回调函数"""
        self.timing_panel.on_record = self.manual_record
        self.timing_panel.on_delete = self.delete_selected_records
        self.timing_panel.on_clear = self.clear_records
        self.timing_panel.on_export = self.export_to_excel
        self.timing_panel.on_auto_detect = self.auto_detect_freezing
        self.timing_panel.on_update_key = self.update_record_key
        self.timing_panel.on_record_double_click = self.on_record_double_click

    def start_display_update(self):
        """启动显示更新线程"""
        if self._display_running:
            return

        self._display_running = True
        self._display_thread = threading.Thread(target=self._update_display_loop, daemon=True)
        self._display_thread.start()

    def stop_display_update(self):
        """停止显示更新"""
        self._display_running = False

    def _update_display_loop(self):
        """显示更新循环"""
        update_interval = self.config.get('update_interval', 0.1)
        root = self.timing_panel.parent.winfo_toplevel()

        while self._display_running:
            if self.video_model.video_capture:
                current_video_time = self.video_model.current_time
                time_str = self.time_formatter.format_time(current_video_time)
                root.after(0, lambda: self.timing_panel.update_current_time(time_str))

                # 更新统计信息
                count = self.record_model.count
                root.after(0, lambda: self.timing_panel.update_stats(count, current_video_time))

            time.sleep(update_interval)

    def setup_keyboard_listener(self, record_key: str):
        """设置键盘监听
        
        Args:
            record_key: 记录按键
        """
        self.keyboard_service.register_key(record_key, self._on_keyboard_record)
        self.timing_panel.set_record_key(record_key)

    def _on_keyboard_record(self):
        """键盘记录回调"""
        if self.video_model.video_playing and self.video_model.video_capture:
            self.record_time()

    def record_time(self):
        """记录当前视频播放时间"""
        if not self.video_model.video_capture:
            messagebox.showwarning("提示", "请先加载视频")
            return

        video_time = self.video_model.current_time
        frame = self.video_model.current_frame

        record = self.record_model.add_record(video_time, frame)
        self._add_record_to_view(record)

    def manual_record(self):
        """手动记录时间点"""
        self.record_time()

    def _add_record_to_view(self, record):
        """添加记录到视图"""
        time_display = self.time_formatter.format_time(record.video_time)
        self.timing_panel.add_record(
            record.sequence,
            time_display,
            record.video_time,
            record.interval
        )

    def delete_selected_records(self):
        """删除选中的记录"""
        sequences = self.timing_panel.get_selected_sequences()
        if not sequences:
            messagebox.showwarning("提示", "请先选择要删除的记录")
            return

        deleted_count = self.record_model.delete_records(sequences)
        if deleted_count > 0:
            self._refresh_records_view()

    def clear_records(self):
        """清空记录"""
        self.record_model.clear()
        self.timing_panel.clear_records()
        self.timing_panel.update_stats(0)

    def _refresh_records_view(self):
        """刷新记录视图"""
        self.timing_panel.clear_records()
        records = self.record_model.records
        for record in records:
            time_display = self.time_formatter.format_time(record.video_time)
            self.timing_panel.add_record(
                record.sequence,
                time_display,
                record.video_time,
                record.interval
            )

    def auto_detect_freezing(self):
        """自动检测视频中的停止区间并作为候选记录导入。"""
        if self._detection_running:
            return

        if not self.video_model.video_capture or not self.video_model.video_path:
            messagebox.showwarning("提示", "请先加载视频")
            return

        if self.video_model.video_playing and hasattr(self, 'on_pause_video'):
            self.on_pause_video()

        params = self._create_freezing_detection_params()
        video_path = self.video_model.video_path
        fps = self.video_model.video_fps
        total_frames = self.video_model.total_frames

        self._detection_running = True
        self.timing_panel.set_auto_detect_running(True)
        self.timing_panel.update_auto_detect_status("自动检测中: 0%")

        self._detection_thread = threading.Thread(
            target=self._run_freezing_detection,
            args=(video_path, fps, total_frames, params),
            daemon=True
        )
        self._detection_thread.start()

    def _create_freezing_detection_params(self) -> FreezingDetectionParams:
        """从配置创建自动检测参数。"""
        return FreezingDetectionParams(
            sample_rate=float(self.config.get('freezing_sample_rate', 10.0)),
            analysis_width=int(self.config.get('freezing_analysis_width', 320)),
            pixel_diff_threshold=int(self.config.get('freezing_pixel_diff_threshold', 25)),
            motion_threshold=float(self.config.get('freezing_motion_threshold', 0.0004)),
            min_freeze_duration=float(self.config.get('freezing_min_duration', 0.5)),
            merge_gap=float(self.config.get('freezing_merge_gap', 0.3)),
            min_non_freeze_gap=float(self.config.get('freezing_min_non_freeze_gap', 0.2)),
            smoothing_window=float(self.config.get('freezing_smoothing_window', 0.3)),
        )

    def _run_freezing_detection(
        self,
        video_path: str,
        fps: float,
        total_frames: int,
        params: FreezingDetectionParams
    ):
        """在后台线程执行自动检测。"""
        last_progress = -1.0

        def progress_callback(progress: float):
            nonlocal last_progress
            if progress < 1.0 and progress - last_progress < 0.02:
                return
            last_progress = progress
            self._run_on_ui_thread(
                lambda value=progress: self.timing_panel.update_auto_detect_status(
                    f"自动检测中: {value * 100:.0f}%"
                )
            )

        try:
            intervals = self.freezing_detection_service.detect_freezing(
                video_path,
                fps,
                total_frames,
                params,
                progress_callback
            )
        except Exception as exc:
            self._run_on_ui_thread(
                lambda message=str(exc): self._on_freezing_detection_failed(message)
            )
            return

        def finish_on_ui_thread(
            detected_intervals=intervals,
            source_path=video_path
        ):
            self._on_freezing_detection_completed(detected_intervals, source_path)

        self._run_on_ui_thread(finish_on_ui_thread)

    def _on_freezing_detection_completed(
        self,
        intervals: List[FreezingInterval],
        source_video_path: str
    ):
        """处理自动检测完成事件。"""
        self._detection_running = False
        self.timing_panel.set_auto_detect_running(False)

        if self.video_model.video_path != source_video_path:
            self.timing_panel.update_auto_detect_status("检测结果已丢弃: 视频已更换")
            messagebox.showinfo("自动检测完成", "视频已更换，旧视频的检测结果未导入。")
            return

        interval_count = len(intervals)
        if interval_count == 0:
            self.timing_panel.update_auto_detect_status("检测完成: 未发现候选区间")
            messagebox.showinfo("自动检测完成", "未检测到符合条件的停止区间。")
            return

        total_duration = sum(interval.duration for interval in intervals)
        self.timing_panel.update_auto_detect_status(
            f"检测完成: {interval_count} 个候选区间"
        )

        message = (
            f"检测到 {interval_count} 个停止区间，"
            f"总时长 {total_duration:.3f} 秒。\n\n"
        )
        if self.record_model.count > 0:
            message += f"当前已有 {self.record_model.count} 个记录点，导入会清空并覆盖。\n\n"
        message += "是否导入为记录点？"

        if messagebox.askyesno("自动检测完成", message):
            self._import_freezing_intervals(intervals)
            self.timing_panel.update_auto_detect_status(
                f"已导入 {interval_count} 个区间，共 {self.record_model.count} 个记录点"
            )
        else:
            self.timing_panel.update_auto_detect_status("检测结果未导入")

    def _on_freezing_detection_failed(self, error_message: str):
        """处理自动检测失败事件。"""
        self._detection_running = False
        self.timing_panel.set_auto_detect_running(False)
        self.timing_panel.update_auto_detect_status("自动检测失败")
        messagebox.showerror("错误", f"自动检测失败: {error_message}")

    def _import_freezing_intervals(self, intervals: List[FreezingInterval]):
        """将检测区间覆盖导入为成对时间点记录。"""
        self.record_model.clear()
        self.timing_panel.clear_records()

        for interval in sorted(intervals, key=lambda item: item.start):
            start_record = self.record_model.add_record(interval.start, interval.start_frame)
            self._add_record_to_view(start_record)

            end_record = self.record_model.add_record(interval.end, interval.end_frame)
            self._add_record_to_view(end_record)

        self.timing_panel.update_stats(self.record_model.count, self.video_model.current_time)

    def _run_on_ui_thread(self, callback):
        """安全地把后台线程结果切回 Tk 主线程。"""
        try:
            root = self.timing_panel.parent.winfo_toplevel()
            if root.winfo_exists():
                root.after(0, callback)
        except tk.TclError:
            pass

    def update_record_key(self, new_key: str):
        """更新记录按键
        
        Args:
            new_key: 新按键
        """
        old_key = self.timing_panel.get_record_key()
        if old_key:
            self.keyboard_service.unregister_key(old_key)

        self.keyboard_service.register_key(new_key, self._on_keyboard_record)
        self.timing_panel.set_record_key(new_key)
        messagebox.showinfo("成功", f"记录按键已更新为: {new_key}")

    def on_record_double_click(self, event):
        """记录双击事件 - 跳转到对应视频位置"""
        video_time = self.timing_panel.get_selected_record_time()
        if video_time is None or not self.video_model.video_capture:
            return

        # 暂停播放（如果正在播放）
        if self.video_model.video_playing:
            if hasattr(self, 'on_pause_video'):
                self.on_pause_video()

        # 跳转到该时间
        if hasattr(self, 'on_seek_to_time'):
            self.on_seek_to_time(video_time)

    def export_to_excel(self):
        """导出到Excel"""
        if self.record_model.count == 0:
            messagebox.showwarning("警告", "没有数据可导出")
            return

        # 显示导出类型选择对话框
        root = self.timing_panel.parent.winfo_toplevel()
        export_dialog = ExportDialog(root)
        export_type = export_dialog.show()
        
        # 如果用户取消选择，直接返回
        if export_type is None:
            return

        # 选择保存路径
        file_path = filedialog.asksaveasfilename(
            title="保存Excel文件",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )

        if not file_path:
            return

        records = self.record_model.records
        success = self.export_service.export('excel', records, self.video_model, file_path, export_type)

        if success:
            intervals = self.record_model.get_paired_intervals()
            total_duration = sum(interval['duration'] for interval in intervals)

            # 根据导出类型显示不同的成功消息
            type_names = {
                ExportType.LOOMING: "Looming",
                ExportType.TRAINING: "FC (Training)",
                ExportType.OFC: "OFC",
                ExportType.TEST: "Test"
            }
            type_name = type_names.get(export_type, "未知")

            messagebox.showinfo(
                "成功",
                f"数据已导出到: {file_path}\n\n"
                f"导出类型: {type_name}\n\n"
                f"包含4个工作表：\n"
                f"1. 原始记录 - 成对的时间点记录\n"
                f"2. 区间统计 - 所有区间的总时长统计\n"
                f"3. 区间详情 - 详细区间列表\n"
                f"4. Freezing统计 - 按自定义区间统计\n\n"
                f"区间总数: {len(intervals)}\n"
                f"区间总时长: {total_duration:.3f}秒"
            )
        else:
            messagebox.showerror("错误", "导出失败")

    def clear_records_on_video_load(self):
        """视频加载时清空记录"""
        self.clear_records()

