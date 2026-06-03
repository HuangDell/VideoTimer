"""Application entry point."""
from __future__ import annotations


def main():
    """Run the PySide6 annotation workbench."""
    try:
        from views.qt import run_qt_workbench
    except ImportError as exc:
        print(f"缺少必要依赖: {exc}")
        print("请安装依赖: pip install -r requirements.txt")
        return 1

    return run_qt_workbench()


if __name__ == "__main__":
    raise SystemExit(main())
