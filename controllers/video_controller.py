"""视频控制器 - 协调视频模型、服务和视图"""
import cv2
from typing import Optional
from models.video_model import VideoModel
from services.video_service import VideoService
from views.video_panel import VideoPanel
from utils.time_formatter import TimeFormatter
from utils.config import Config


class VideoController:
    """视频控制器 - 负责视频播放相关的业务逻辑"""
    
    def __init__(self, video_model: VideoModel, video_service: VideoService, video_panel: VideoPanel):
        self.video_model = video_model
        self.video_service = video_service
        self.video_panel = video_panel
        self.time_formatter = TimeFormatter()
        self.config = Config()

        # 设置回调
        self._setup_callbacks()

    def _setup_callbacks(self):
        """设置回调函数"""
        self.video_panel.on_select_video = self.load_video
        self.video_panel.on_play_pause = self.toggle_playback
        self.video_panel.on_stop = self.stop_video
        self.video_panel.on_fullscreen = self.toggle_fullscreen
        self.video_panel.on_progress_changed = self.on_progress_changed
        self.video_panel.on_progress_press = self.on_progress_press
        self.video_panel.on_progress_release = self.on_progress_release
        self.video_panel.on_progress_click = self.on_progress_click

        # 设置视频服务的回调
        self.video_service.set_frame_update_callback(self._on_frame_update)
        self.video_service.set_finished_callback(self._on_video_finished)

    def load_video(self, file_path: str):
        """加载视频文件
        
        Args:
            file_path: 视频文件路径
        """
        if self.video_service.load_video(file_path):
            # 更新UI
            import os
            filename = os.path.basename(file_path)
            self.video_panel.update_video_path(f"文件: {filename}")

            duration = self.video_model.duration
            info = (
                f"总时长: {self.time_formatter.format_time(duration)} | "
                f"总帧数: {self.video_model.total_frames} | "
                f"FPS: {self.video_model.video_fps:.2f}"
            )
            self.video_panel.update_video_info(info)

            # 重置到第一帧
            self.video_model.reset()
            self.show_current_frame()

            # 更新进度条范围
            self.video_panel.set_progress_range(max(self.video_model.total_frames - 1, 1))
            self.video_panel.update_progress(0, "00:00:00.000", self.time_formatter.format_time(duration))

            # 启用控制按钮
            self.video_panel.set_controls_enabled(True)

            # 通知加载成功
            if hasattr(self, 'on_video_loaded'):
                self.on_video_loaded()
        else:
            from tkinter import messagebox
            messagebox.showerror("错误", "无法打开视频文件")

    def show_current_frame(self):
        """显示当前帧"""
        frame = self.video_service.get_current_frame()
        if frame is not None:
            self._update_frame_display(frame)

    def _update_frame_display(self, frame):
        """更新帧显示"""
        self.video_panel.video_label.update_idletasks()
        label_width = self.video_panel.video_label.winfo_width()
        label_height = self.video_panel.video_label.winfo_height()

        self.video_panel.update_video_frame(frame, label_width, label_height)

        # 更新进度条
        if not self.video_panel.get_progress_dragging() and self.video_model.total_frames > 0:
            progress = self.video_model.progress
            current_time_str = self.time_formatter.format_time(self.video_model.current_time)
            total_time_str = self.time_formatter.format_time(self.video_model.duration)
            self.video_panel.update_progress(progress, current_time_str, total_time_str)

    def _on_frame_update(self, frame, current_time: float):
        """帧更新回调"""
        root = self.video_panel.parent.winfo_toplevel()
        root.after(0, lambda: self._update_frame_display(frame))

        # 更新视频信息
        total_time = self.video_model.duration
        progress_text = (
            f"进度: {self.time_formatter.format_time(current_time)} / "
            f"{self.time_formatter.format_time(total_time)}"
        )
        info = f"{progress_text} | 帧: {self.video_model.current_frame}/{self.video_model.total_frames}"
        root.after(0, lambda: self.video_panel.update_video_info(info))

        # 更新进度条
        if not self.video_panel.get_progress_dragging() and self.video_model.total_frames > 0:
            progress = self.video_model.progress
            current_time_str = self.time_formatter.format_time(current_time)
            total_time_str = self.time_formatter.format_time(total_time)
            root.after(0, lambda: self.video_panel.update_progress(progress, current_time_str, total_time_str))

    def _on_video_finished(self):
        """视频播放完成回调"""
        root = self.video_panel.parent.winfo_toplevel()
        root.after(0, lambda: self.video_panel.set_play_button_text("播放"))
        root.after(0, lambda: self._show_finished_message())

    def _show_finished_message(self):
        """显示播放完成消息"""
        from tkinter import messagebox
        messagebox.showinfo("提示", "视频播放完毕")

    def toggle_playback(self):
        """切换播放/暂停"""
        if not self.video_model.video_playing:
            self.video_service.play()
            self.video_panel.set_play_button_text("暂停")
        else:
            self.video_service.pause()
            self.video_panel.set_play_button_text("播放")

    def stop_video(self):
        """停止视频"""
        self.video_service.stop()
        self.video_panel.set_play_button_text("播放")
        self.show_current_frame()

        if self.video_model.total_frames > 0:
            total_time_str = self.time_formatter.format_time(self.video_model.duration)
            self.video_panel.update_progress(0, "00:00:00.000", total_time_str)

    def toggle_fullscreen(self):
        """切换全屏"""
        if hasattr(self, 'on_toggle_fullscreen'):
            self.on_toggle_fullscreen()

    def on_progress_changed(self, value):
        """进度条改变"""
        if not self.video_model.video_capture or self.video_model.total_frames == 0:
            return

        if not self.video_panel.get_progress_dragging():
            return

        # value 是百分比 (0-100)，需要转换为帧数
        progress_percent = float(value)
        max_frame = max(self.video_model.total_frames - 1, 1)
        frame_number = int(progress_percent / 100.0 * max_frame)
        frame_number = max(0, min(frame_number, self.video_model.total_frames - 1))
        
        if 0 <= frame_number < self.video_model.total_frames:
            self.video_service.seek_to_frame(frame_number)
            self.show_current_frame()

            current_time = frame_number / self.video_model.video_fps
            current_time_str = self.time_formatter.format_time(current_time)
            total_time_str = self.time_formatter.format_time(self.video_model.duration)
            self.video_panel.update_progress(
                (frame_number / max_frame) * 100,
                current_time_str,
                total_time_str
            )

    def on_progress_press(self, event):
        """进度条按下"""
        scale_width = self.video_panel.progress_scale.winfo_width()
        if scale_width > 0 and not self.video_panel.get_progress_dragging():
            # 检查是否是点击跳转
            current_ratio = self.video_panel.progress_var.get() / 100.0
            click_ratio = event.x / scale_width
            if abs(click_ratio - current_ratio) > 0.05:
                self.on_progress_click(event)
                return

        self.video_panel.set_progress_dragging(True)
        if self.video_model.video_playing:
            self.video_service.pause()
            self.video_panel.set_play_button_text("播放")

    def on_progress_release(self, event):
        """进度条释放"""
        if self.video_panel.get_progress_dragging():
            # value 是百分比 (0-100)，需要转换为帧数
            progress_percent = self.video_panel.progress_var.get()
            max_frame = max(self.video_model.total_frames - 1, 1)
            frame_number = int(progress_percent / 100.0 * max_frame)
            frame_number = max(0, min(frame_number, self.video_model.total_frames - 1))
            
            if 0 <= frame_number < self.video_model.total_frames:
                self.video_service.seek_to_frame(frame_number)
                self.show_current_frame()
        self.video_panel.set_progress_dragging(False)

    def on_progress_click(self, event):
        """进度条点击"""
        if not self.video_model.video_capture or self.video_model.total_frames == 0:
            return

        # 暂停播放（如果正在播放）
        was_playing = self.video_model.video_playing
        if was_playing:
            self.video_service.pause()
            self.video_panel.set_play_button_text("播放")

        # 计算点击位置对应的帧数
        scale_width = self.video_panel.progress_scale.winfo_width()
        if scale_width > 0:
            click_x = event.x
            ratio = click_x / scale_width
            frame_number = int(ratio * (self.video_model.total_frames - 1))
            frame_number = max(0, min(frame_number, self.video_model.total_frames - 1))

            # 跳转到该帧
            self.video_service.seek_to_frame(frame_number)
            self.show_current_frame()

            # 更新进度条显示
            progress = (frame_number / max(self.video_model.total_frames - 1, 1)) * 100
            current_time = frame_number / self.video_model.video_fps
            current_time_str = self.time_formatter.format_time(current_time)
            total_time_str = self.time_formatter.format_time(self.video_model.duration)
            self.video_panel.update_progress(progress, current_time_str, total_time_str)

    def seek_to_time(self, time_seconds: float):
        """跳转到指定时间
        
        Args:
            time_seconds: 时间（秒）
        """
        self.video_service.seek_to_time(time_seconds)
        self.show_current_frame()

        if self.video_model.total_frames > 0:
            frame_number = int(time_seconds * self.video_model.video_fps)
            progress = (frame_number / max(self.video_model.total_frames - 1, 1)) * 100
            current_time_str = self.time_formatter.format_time(time_seconds)
            total_time_str = self.time_formatter.format_time(self.video_model.duration)
            self.video_panel.update_progress(progress, current_time_str, total_time_str)

    def on_window_resize(self):
        """窗口大小变化处理"""
        if self.video_model.video_capture:
            self.show_current_frame()

    def release(self):
        """释放资源"""
        self.video_service.release()

