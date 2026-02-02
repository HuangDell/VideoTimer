"""视频播放面板视图"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
from PIL import Image, ImageTk
from typing import Optional, Callable


class VideoPanel:
    """视频播放面板 - 负责视频播放相关的UI"""
    
    def __init__(self, parent: tk.Widget):
        self.parent = parent
        self.frame = ttk.LabelFrame(parent, text="视频播放区域", padding="5")
        
        # 回调函数
        self.on_select_video: Optional[Callable] = None
        self.on_play_pause: Optional[Callable] = None
        self.on_stop: Optional[Callable] = None
        self.on_fullscreen: Optional[Callable] = None
        self.on_progress_changed: Optional[Callable] = None
        self.on_progress_press: Optional[Callable] = None
        self.on_progress_release: Optional[Callable] = None
        self.on_progress_click: Optional[Callable] = None
        self.on_speed_changed: Optional[Callable] = None
        
        # 内部状态
        self._max_frames: float = 1
        self._progress_dragging: bool = False

        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(2, weight=1)

        # 视频控制按钮
        video_controls = ttk.Frame(self.frame)
        video_controls.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))

        select_video_btn = ttk.Button(video_controls, text="选择视频", command=self._on_select_video)
        select_video_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.play_pause_btn = ttk.Button(
            video_controls, 
            text="播放", 
            command=self._on_play_pause,
            state='disabled'
        )
        self.play_pause_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_btn = ttk.Button(
            video_controls, 
            text="重置", 
            command=self._on_stop,
            state='disabled'
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))

        fullscreen_btn = ttk.Button(video_controls, text="全屏", command=self._on_fullscreen)
        fullscreen_btn.pack(side=tk.LEFT, padx=(0, 5))

        # 播放速度选择器
        ttk.Label(video_controls, text="倍速:").pack(side=tk.LEFT, padx=(10, 2))
        self.speed_var = tk.StringVar(value="1.0x")
        self.speed_combo = ttk.Combobox(
            video_controls,
            textvariable=self.speed_var,
            values=["0.5x", "0.8x", "1.0x", "1.5x", "2.0x", "3.0x"],
            width=5,
            state='readonly'
        )
        self.speed_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.speed_combo.bind('<<ComboboxSelected>>', self._on_speed_changed)

        # 视频进度条
        progress_frame = ttk.Frame(self.frame)
        progress_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        progress_frame.columnconfigure(0, weight=1)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_scale = ttk.Scale(
            progress_frame, 
            from_=0, 
            to=100, 
            orient=tk.HORIZONTAL,
            variable=self.progress_var,
            command=self._on_progress_changed
        )
        self.progress_scale.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        # 绑定鼠标事件
        self.progress_scale.bind('<Button-1>', self._on_progress_press)
        self.progress_scale.bind('<ButtonRelease-1>', self._on_progress_release)
        self.progress_scale.bind('<Button-3>', self._on_progress_click)
        self.progress_scale.bind('<Double-Button-1>', self._on_progress_click)

        self.progress_label = ttk.Label(
            progress_frame, 
            text="00:00:00.000 / 00:00:00.000", 
            font=('Arial', 9), 
            width=25
        )
        self.progress_label.grid(row=0, column=1)

        # 视频显示区域
        self.video_label = ttk.Label(
            self.frame, 
            text="请选择视频文件", 
            font=('Arial', 12),
            relief='sunken', 
            borderwidth=1
        )
        self.video_label.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))

        # 视频信息区域
        info_frame = ttk.Frame(self.frame)
        info_frame.grid(row=3, column=0, sticky=(tk.W, tk.E))
        info_frame.columnconfigure(0, weight=1)

        self.video_info_var = tk.StringVar(value="未加载视频")
        video_info_label = ttk.Label(info_frame, textvariable=self.video_info_var, font=('Arial', 9))
        video_info_label.grid(row=0, column=0, sticky=tk.W)

        self.video_path_var = tk.StringVar(value="")
        video_path_label = ttk.Label(
            info_frame, 
            textvariable=self.video_path_var, 
            font=('Arial', 8),
            foreground='gray'
        )
        video_path_label.grid(row=1, column=0, sticky=tk.W)

    def _on_select_video(self):
        """选择视频文件"""
        file_path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[
                ("视频文件", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm"),
                ("所有文件", "*.*")
            ]
        )
        if file_path and self.on_select_video:
            self.on_select_video(file_path)

    def _on_play_pause(self):
        """播放/暂停按钮点击"""
        if self.on_play_pause:
            self.on_play_pause()

    def _on_stop(self):
        """停止按钮点击"""
        if self.on_stop:
            self.on_stop()

    def _on_fullscreen(self):
        """全屏按钮点击"""
        if self.on_fullscreen:
            self.on_fullscreen()

    def _on_progress_changed(self, value):
        """进度条改变"""
        if self.on_progress_changed:
            self.on_progress_changed(value)

    def _on_progress_press(self, event):
        """进度条按下"""
        if self.on_progress_press:
            self.on_progress_press(event)

    def _on_progress_release(self, event):
        """进度条释放"""
        if self.on_progress_release:
            self.on_progress_release(event)

    def _on_progress_click(self, event):
        """进度条点击"""
        if self.on_progress_click:
            self.on_progress_click(event)

    def _on_speed_changed(self, event=None):
        """播放速度改变"""
        if self.on_speed_changed:
            speed_str = self.speed_var.get()
            # 解析速度值，例如 "1.5x" -> 1.5
            speed = float(speed_str.rstrip('x'))
            self.on_speed_changed(speed)

    def get_playback_speed(self) -> float:
        """获取当前播放速度
        
        Returns:
            播放速度倍率
        """
        speed_str = self.speed_var.get()
        return float(speed_str.rstrip('x'))

    def set_playback_speed(self, speed: float):
        """设置播放速度
        
        Args:
            speed: 播放速度倍率
        """
        self.speed_var.set(f"{speed}x")

    def update_video_frame(self, frame, label_width: int, label_height: int):
        """更新视频帧显示
        
        Args:
            frame: 视频帧（numpy数组）
            label_width: 标签宽度
            label_height: 标签高度
        """
        try:
            # 检查窗口是否仍然存在
            root = self.parent.winfo_toplevel()
            if not root.winfo_exists():
                return
            
            # 检查标签是否仍然存在
            try:
                self.video_label.winfo_exists()
            except tk.TclError:
                return

            # 设置显示尺寸
            if label_width > 10 and label_height > 10:
                max_width = max(label_width - 10, 400)
                max_height = max(label_height - 10, 300)
            else:
                max_width, max_height = 800, 600

            # 调整图像大小，保持宽高比
            height, width = frame.shape[:2]
            scale = min(max_width / width, max_height / height, 1.0)
            new_width = int(width * scale)
            new_height = int(height * scale)

            frame = cv2.resize(frame, (new_width, new_height))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 转换为PIL Image并显示
            # 确保在正确的Tkinter根窗口上下文中创建PhotoImage
            image = Image.fromarray(frame)
            photo = ImageTk.PhotoImage(image, master=root)
            self.video_label.config(image=photo, text="")
            # 保存引用以防止垃圾回收
            self.video_label.image = photo
        except tk.TclError:
            # 窗口已关闭，忽略错误
            pass
        except Exception as e:
            print(f"更新视频显示错误: {e}")

    def update_progress(self, progress: float, current_time_str: str, total_time_str: str):
        """更新进度条
        
        Args:
            progress: 进度值（0-100）
            current_time_str: 当前时间字符串
            total_time_str: 总时间字符串
        """
        self.progress_var.set(progress)
        self.progress_label.config(text=f"{current_time_str} / {total_time_str}")

    def update_video_info(self, info: str):
        """更新视频信息
        
        Args:
            info: 信息字符串
        """
        self.video_info_var.set(info)

    def update_video_path(self, path: str):
        """更新视频路径显示
        
        Args:
            path: 路径字符串
        """
        self.video_path_var.set(path)

    def set_play_button_text(self, text: str):
        """设置播放按钮文本
        
        Args:
            text: 按钮文本
        """
        self.play_pause_btn.config(text=text)

    def set_controls_enabled(self, enabled: bool):
        """设置控制按钮启用状态
        
        Args:
            enabled: 是否启用
        """
        state = 'normal' if enabled else 'disabled'
        self.play_pause_btn.config(state=state)
        self.stop_btn.config(state=state)

    def set_progress_range(self, max_value: float):
        """设置进度条范围（保持0-100百分比范围）
        
        Args:
            max_value: 最大帧数（用于内部计算，但不改变进度条范围）
        """
        # 进度条始终使用0-100的百分比范围
        self._max_frames = max_value

    def get_progress_dragging(self) -> bool:
        """获取是否正在拖动进度条"""
        return self._progress_dragging

    def set_progress_dragging(self, dragging: bool):
        """设置是否正在拖动进度条
        
        Args:
            dragging: 是否拖动
        """
        self._progress_dragging = dragging

