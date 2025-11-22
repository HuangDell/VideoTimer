"""视频服务类 - 处理视频播放逻辑"""
import threading
import time
import cv2
import numpy as np
from typing import Optional, Callable
from models.video_model import VideoModel
from utils.config import Config


class VideoService:
    """视频服务类 - 负责视频播放控制"""
    
    def __init__(self, video_model: VideoModel):
        self.video_model = video_model
        self.config = Config()
        self._play_thread: Optional[threading.Thread] = None
        self._frame_update_callback: Optional[Callable] = None
        self._finished_callback: Optional[Callable] = None

    def set_frame_update_callback(self, callback: Callable):
        """设置帧更新回调
        
        Args:
            callback: 回调函数，参数为 (frame, current_time)
        """
        self._frame_update_callback = callback

    def set_finished_callback(self, callback: Callable):
        """设置播放完成回调
        
        Args:
            callback: 回调函数
        """
        self._finished_callback = callback

    def load_video(self, file_path: str) -> bool:
        """加载视频文件
        
        Args:
            file_path: 视频文件路径
            
        Returns:
            是否加载成功
        """
        return self.video_model.load_video(file_path)

    def play(self):
        """开始播放"""
        if not self.video_model.video_capture:
            return

        self.video_model.video_playing = True

        # 启动播放线程
        if self._play_thread is None or not self._play_thread.is_alive():
            self._play_thread = threading.Thread(target=self._play_loop, daemon=True)
            self._play_thread.start()

    def pause(self):
        """暂停播放"""
        self.video_model.video_playing = False

    def stop(self):
        """停止播放并重置"""
        self.video_model.video_playing = False
        self.video_model.reset()

    def seek_to_frame(self, frame_number: int):
        """跳转到指定帧"""
        self.video_model.seek_to_frame(frame_number)

    def seek_to_time(self, time_seconds: float):
        """跳转到指定时间"""
        self.video_model.seek_to_time(time_seconds)

    def get_current_frame(self) -> Optional[np.ndarray]:
        """获取当前帧
        
        Returns:
            当前帧（numpy数组），如果失败则返回None
        """
        if not self.video_model.video_capture:
            return None

        self.video_model.video_capture.set(
            cv2.CAP_PROP_POS_FRAMES, 
            self.video_model.current_frame
        )
        ret, frame = self.video_model.video_capture.read()
        return frame if ret else None

    def _play_loop(self):
        """播放循环"""
        # 确保从当前帧开始播放
        if self.video_model.video_capture:
            self.video_model.video_capture.set(
                cv2.CAP_PROP_POS_FRAMES,
                self.video_model.current_frame
            )

        while self.video_model.video_playing and self.video_model.video_capture:
            start_time = time.time()

            ret, frame = self.video_model.read_frame()
            if not ret:
                # 视频播放完毕
                self.video_model.video_playing = False
                if self._finished_callback:
                    self._finished_callback()
                break

            # 调用帧更新回调
            if self._frame_update_callback:
                current_time = self.video_model.current_time
                self._frame_update_callback(frame, current_time)

            # 控制播放速度
            elapsed = time.time() - start_time
            target_delay = 1.0 / self.video_model.video_fps
            if elapsed < target_delay:
                time.sleep(target_delay - elapsed)

    def release(self):
        """释放资源"""
        self.video_model.video_playing = False
        if self._play_thread and self._play_thread.is_alive():
            # 等待线程结束
            time.sleep(0.1)
        self.video_model.release()

