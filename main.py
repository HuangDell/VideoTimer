"""Application entry point."""
from __future__ import annotations


def main():
    """Run the PySide6 annotation workbench."""
    try:
        from views.qt_workbench import run_qt_workbench
    except ImportError as exc:
        print(f"缺少必要依赖: {exc}")
        print("请安装依赖: pip install -r requirements.txt")
        return 1

    return run_qt_workbench()


def legacy_main():
    """Run the previous Tkinter multi-instance timer UI."""
    import threading

    from controllers.main_controller import MainController
    from views.instance_selector import InstanceSelector

    try:
        import cv2  # noqa: F401
        import keyboard  # noqa: F401
        import openpyxl  # noqa: F401
        import pandas  # noqa: F401
        from PIL import Image, ImageTk  # noqa: F401
    except ImportError as exc:
        print(f"缺少必要的包: {exc}")
        print("请安装旧版依赖: pip install opencv-python keyboard pandas openpyxl pillow")
        return 1

    instance_count, record_keys = InstanceSelector.show()
    if instance_count == 0:
        return 0

    def run_app(instance_id: int, record_key: str):
        app = MainController(instance_id=instance_id, record_key=record_key)
        app.run()

    threads = []
    for index in range(instance_count):
        thread = threading.Thread(
            target=run_app,
            args=(index + 1, record_keys[index]),
            daemon=False,
        )
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
