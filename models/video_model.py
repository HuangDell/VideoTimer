"""视频数据模型"""
from typing import Optional, Tuple
import cv2
import numpy as np


class VideoModel:
    """视频数据模型 - 封装视频相关数据"""
    
    def __init__(self):
        self.video_capture: Optional[cv2.VideoCapture] = None
        self.video_path: str = ""
        self.video_fps: float = 30.0
        self.total_frames: int = 0
        self.current_frame: int = 0
        self.video_playing: bool = False
        self.video_paused: bool = False
        self.playback_speed: float = 1.0  # 播放速度倍率

    @property
    def duration(self) -> float:
        """获取视频总时长（秒）"""
        if self.video_fps > 0:
            return self.total_frames / self.video_fps
        return 0.0

    @property
    def current_time(self) -> float:
        """获取当前播放时间（秒）"""
        if self.video_capture and self.video_fps > 0:
            return self.current_frame / self.video_fps
        return 0.0

    @property
    def progress(self) -> float:
        """获取播放进度（0-100）"""
        if self.total_frames > 0:
            return (self.current_frame / max(self.total_frames - 1, 1)) * 100
        return 0.0

    def load_video(self, file_path: str) -> bool:
        """加载视频文件
        
        Args:
            file_path: 视频文件路径
            
        Returns:
            是否加载成功
        """
        try:
            # 释放之前的视频资源
            if self.video_capture:
                self.video_capture.release()

            self.video_capture = cv2.VideoCapture(file_path)

            if not self.video_capture.isOpened():
                return False

            # 获取视频信息
            self.video_path = file_path
            self.video_fps = self.video_capture.get(cv2.CAP_PROP_FPS)
            self.total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
            self.current_frame = 0

            return True
        except Exception:
            return False

    def seek_to_frame(self, frame_number: int) -> bool:
        """跳转到指定帧
        
        Args:
            frame_number: 帧号
            
        Returns:
            是否成功
        """
        if not self.video_capture or not (0 <= frame_number < self.total_frames):
            return False

        self.current_frame = frame_number
        return self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

    def seek_to_time(self, time_seconds: float) -> bool:
        """跳转到指定时间
        
        Args:
            time_seconds: 时间（秒）
            
        Returns:
            是否成功
        """
        if self.video_fps > 0:
            frame_number = int(time_seconds * self.video_fps)
            return self.seek_to_frame(frame_number)
        return False

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """读取当前帧
        
        Returns:
            (是否成功, 帧数据)
        """
        if not self.video_capture:
            return False, None

        # 读取前获取当前帧位置（read()后会指向下一帧）
        current_pos = int(self.video_capture.get(cv2.CAP_PROP_POS_FRAMES))
        
        ret, frame = self.video_capture.read()
        if ret:
            # 读取成功后，当前帧号就是读取前的帧位置
            # 因为read()读取当前帧后，位置会自动移动到下一帧
            self.current_frame = current_pos

        return ret, frame

    def release(self):
        """释放视频资源"""
        if self.video_capture:
            self.video_capture.release()
            self.video_capture = None
        self.video_playing = False
        self.current_frame = 0

    def reset(self):
        """重置到开始位置"""
        self.current_frame = 0
        if self.video_capture:
            self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.video_playing = False

