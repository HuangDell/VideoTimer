"""导出类型选择对话框"""
import tkinter as tk
from tkinter import ttk
from typing import Optional
from enum import Enum


class ExportType(Enum):
    """导出类型枚举"""
    LOOMING = "looming"
    TRAINING = "training"  # FC (Training)
    OFC = "ofc"
    TEST = "test"


class ExportDialog:
    """导出类型选择对话框"""
    
    def __init__(self, parent: tk.Widget):
        self.parent = parent
        self.result: Optional[ExportType] = None
        
    def show(self) -> Optional[ExportType]:
        """显示对话框并返回选择的导出类型
        
        Returns:
            选择的导出类型，取消则返回None
        """
        # 创建模态对话框
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("选择导出类型")
        self.dialog.geometry("350x280")
        self.dialog.resizable(False, False)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # 居中显示
        self.dialog.update_idletasks()
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - 350) // 2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - 280) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        # 主框架
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(
            main_frame, 
            text="请选择导出类型", 
            font=('Arial', 12, 'bold')
        )
        title_label.pack(pady=(0, 15))
        
        # 说明文字
        desc_label = ttk.Label(
            main_frame,
            text="不同类型将使用不同的时间区间计算方法",
            font=('Arial', 9),
            foreground='gray'
        )
        desc_label.pack(pady=(0, 15))
        
        # 选项按钮
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Looming 按钮
        looming_btn = ttk.Button(
            buttons_frame,
            text="Looming",
            command=lambda: self._select(ExportType.LOOMING),
            width=15
        )
        looming_btn.pack(pady=5)
        
        # Training (FC) 按钮
        training_btn = ttk.Button(
            buttons_frame,
            text="FC (Training)",
            command=lambda: self._select(ExportType.TRAINING),
            width=15
        )
        training_btn.pack(pady=5)
        
        # OFC 按钮
        ofc_btn = ttk.Button(
            buttons_frame,
            text="OFC",
            command=lambda: self._select(ExportType.OFC),
            width=15
        )
        ofc_btn.pack(pady=5)
        
        # Test 按钮
        test_btn = ttk.Button(
            buttons_frame,
            text="Test",
            command=lambda: self._select(ExportType.TEST),
            width=15
        )
        test_btn.pack(pady=5)
        
        # 取消按钮
        cancel_btn = ttk.Button(
            main_frame,
            text="取消",
            command=self._cancel,
            width=10
        )
        cancel_btn.pack(pady=(10, 0))
        
        # 绑定ESC键取消
        self.dialog.bind('<Escape>', lambda e: self._cancel())
        
        # 等待对话框关闭
        self.dialog.wait_window()
        
        return self.result
    
    def _select(self, export_type: ExportType):
        """选择导出类型
        
        Args:
            export_type: 选择的导出类型
        """
        self.result = export_type
        self.dialog.destroy()
    
    def _cancel(self):
        """取消选择"""
        self.result = None
        self.dialog.destroy()
