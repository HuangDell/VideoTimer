"""主窗口视图"""
import tkinter as tk
from tkinter import ttk
from views.video_panel import VideoPanel
from views.timing_panel import TimingPanel
from utils.config import Config


class MainWindow:
    """主窗口 - 组合视频面板和计时面板"""
    
    def __init__(self, instance_id: int = 1):
        self.instance_id = instance_id
        self.config = Config()
        self.root = tk.Tk()
        self.root.title(f"视频计时器 - Video Timer (实例 {instance_id})")
        self.root.geometry(
            f"{self.config.get('window_width')}x{self.config.get('window_height')}"
        )
        self.root.minsize(
            self.config.get('min_window_width'),
            self.config.get('min_window_height')
        )

        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # 标题
        title_label = ttk.Label(main_frame, text="视频计时器", font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))

        # 创建视频面板和计时面板
        self.video_panel = VideoPanel(main_frame)
        self.video_panel.frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))

        self.timing_panel = TimingPanel(main_frame)
        self.timing_panel.frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))

        # 绑定窗口大小变化事件
        self.root.bind('<Configure>', self._on_window_resize)

    def _on_window_resize(self, event):
        """窗口大小变化事件处理"""
        if event.widget == self.root:
            # 延迟更新，避免频繁刷新
            if hasattr(self, '_resize_timer'):
                self.root.after_cancel(self._resize_timer)
            self._resize_timer = self.root.after(100, self._on_resize_timeout)

    def _on_resize_timeout(self):
        """窗口大小变化超时处理"""
        if hasattr(self, 'on_window_resize'):
            self.on_window_resize()

    def set_window_resize_callback(self, callback):
        """设置窗口大小变化回调
        
        Args:
            callback: 回调函数
        """
        self.on_window_resize = callback

    def toggle_fullscreen(self):
        """切换全屏模式"""
        current_state = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not current_state)

        # 按ESC键退出全屏
        if not current_state:
            self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))

    def run(self):
        """运行主循环"""
        self.root.mainloop()

    def destroy(self):
        """销毁窗口"""
        self.root.destroy()

    def get_root(self) -> tk.Tk:
        """获取根窗口
        
        Returns:
            Tk根窗口
        """
        return self.root

