"""主控制器 - 协调所有控制器和组件"""
from models.video_model import VideoModel
from models.record_model import RecordModel
from services.video_service import VideoService
from services.keyboard_service import KeyboardService
from services.export_service import ExportService
from views.main_window import MainWindow
from controllers.video_controller import VideoController
from controllers.record_controller import RecordController
from utils.config import Config


class MainController:
    """主控制器 - 负责整体协调和生命周期管理"""
    
    def __init__(self, instance_id: int = 1, record_key: str = 'z'):
        self.instance_id = instance_id
        self.record_key = record_key
        self.config = Config()

        # 创建模型
        self.video_model = VideoModel()
        self.record_model = RecordModel()

        # 创建服务
        self.video_service = VideoService(self.video_model)
        self.keyboard_service = KeyboardService()
        self.export_service = ExportService()

        # 创建视图
        self.main_window = MainWindow(instance_id)

        # 创建控制器
        self.video_controller = VideoController(
            self.video_model,
            self.video_service,
            self.main_window.video_panel
        )
        self.record_controller = RecordController(
            self.record_model,
            self.video_model,
            self.keyboard_service,
            self.export_service,
            self.main_window.timing_panel
        )

        # 设置控制器之间的回调
        self._setup_controller_callbacks()

        # 设置窗口回调
        self.main_window.set_window_resize_callback(self.video_controller.on_window_resize)

        # 启动服务
        self.record_controller.start_display_update()
        self.keyboard_service.start_listening()
        self.record_controller.setup_keyboard_listener(record_key)

    def _setup_controller_callbacks(self):
        """设置控制器之间的回调"""
        # 视频加载时清空记录
        self.video_controller.on_video_loaded = self.record_controller.clear_records_on_video_load

        # 记录双击时跳转视频
        self.record_controller.on_seek_to_time = self.video_controller.seek_to_time
        self.record_controller.on_pause_video = self.video_controller.video_service.pause

        # 全屏切换
        self.video_controller.on_toggle_fullscreen = self.main_window.toggle_fullscreen

    def run(self):
        """运行应用"""
        try:
            root = self.main_window.get_root()
            root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.main_window.run()
        except KeyboardInterrupt:
            pass

    def on_closing(self):
        """关闭程序时清理资源"""
        self.record_controller.stop_display_update()
        self.keyboard_service.stop_listening()
        self.video_controller.release()
        self.main_window.destroy()

