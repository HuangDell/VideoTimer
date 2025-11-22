"""主入口文件"""
import threading
from views.instance_selector import InstanceSelector
from controllers.main_controller import MainController


def main():
    """主函数"""
    # 检查依赖
    try:
        import cv2
        import keyboard
        import pandas
        import openpyxl
        from PIL import Image, ImageTk
    except ImportError as e:
        print(f"缺少必要的包: {e}")
        print("请安装必要的包:")
        print("pip install opencv-python keyboard pandas openpyxl pillow")
        return

    # 显示实例选择对话框
    instance_count, record_keys = InstanceSelector.show()

    if instance_count == 0:
        return

    # 创建多个实例并在不同线程中运行
    def run_app(instance_id: int, record_key: str):
        """在独立线程中运行应用实例
        
        Args:
            instance_id: 实例ID
            record_key: 记录按键
        """
        app = MainController(instance_id=instance_id, record_key=record_key)
        app.run()

    threads = []
    for i in range(instance_count):
        thread = threading.Thread(
            target=run_app,
            args=(i + 1, record_keys[i]),
            daemon=False
        )
        thread.start()
        threads.append(thread)

    # 等待所有线程完成（实际上会一直运行直到窗口关闭）
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()

