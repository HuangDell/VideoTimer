"""计时面板视图"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable, List, Tuple


class TimingPanel:
    """计时面板 - 负责时间记录相关的UI"""
    
    def __init__(self, parent: tk.Widget):
        self.parent = parent
        self.frame = ttk.LabelFrame(parent, text="视频计时区域", padding="10")
        
        # 回调函数
        self.on_record: Optional[Callable] = None
        self.on_delete: Optional[Callable] = None
        self.on_clear: Optional[Callable] = None
        self.on_export: Optional[Callable] = None
        self.on_update_key: Optional[Callable] = None
        self.on_record_double_click: Optional[Callable] = None

        self._setup_ui()

    def _setup_ui(self):
        """设置UI"""
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(3, weight=1)

        # 当前时间显示
        time_display_frame = ttk.Frame(self.frame)
        time_display_frame.grid(row=0, column=0, pady=(0, 15))

        ttk.Label(time_display_frame, text="视频播放时间:", font=('Arial', 12)).pack()
        self.current_time_var = tk.StringVar(value="00:00:00.000")
        self.time_display = ttk.Label(
            time_display_frame,
            textvariable=self.current_time_var,
            font=('Arial', 20, 'bold'),
            foreground='blue'
        )
        self.time_display.pack()

        # 控制按钮
        controls = ttk.Frame(self.frame)
        controls.grid(row=1, column=0, pady=(0, 10), sticky=(tk.W, tk.E))

        record_btn = ttk.Button(controls, text="记录时间点", command=self._on_record)
        record_btn.pack(side=tk.LEFT, padx=(0, 10))

        delete_btn = ttk.Button(controls, text="删除选中", command=self._on_delete)
        delete_btn.pack(side=tk.LEFT, padx=(0, 10))

        clear_btn = ttk.Button(controls, text="清空记录", command=self._on_clear)
        clear_btn.pack(side=tk.LEFT, padx=(0, 10))

        export_btn = ttk.Button(controls, text="导出Excel", command=self._on_export)
        export_btn.pack(side=tk.LEFT)

        # 按键设置框架
        key_frame = ttk.LabelFrame(self.frame, text="快捷键设置", padding="5")
        key_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(key_frame, text="记录按键:").pack(side=tk.LEFT, padx=(0, 5))
        self.key_var = tk.StringVar(value="z")
        key_entry = ttk.Entry(key_frame, textvariable=self.key_var, width=15)
        key_entry.pack(side=tk.LEFT, padx=(0, 10))

        update_key_btn = ttk.Button(key_frame, text="更新", command=self._on_update_key)
        update_key_btn.pack(side=tk.LEFT)

        # 记录列表
        list_frame = ttk.LabelFrame(self.frame, text="时间记录点", padding="5")
        list_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # 树形视图
        columns = ('序号', '视频时间', '视频时间(秒)', '间隔时间')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)

        self.tree.heading('序号', text='序号')
        self.tree.heading('视频时间', text='视频时间')
        self.tree.heading('视频时间(秒)', text='视频时间（秒）')
        self.tree.heading('间隔时间', text='间隔时间（秒）')

        self.tree.column('序号', width=50, anchor=tk.CENTER)
        self.tree.column('视频时间', width=120, anchor=tk.CENTER)
        self.tree.column('视频时间(秒)', width=100, anchor=tk.CENTER)
        self.tree.column('间隔时间', width=100, anchor=tk.CENTER)

        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # 绑定双击事件
        self.tree.bind('<Double-Button-1>', self._on_record_double_click)

        # 统计信息
        self.stats_label = ttk.Label(self.frame, text="记录点数: 0", font=('Arial', 9))
        self.stats_label.grid(row=4, column=0, pady=(10, 0))

    def _on_record(self):
        """记录按钮点击"""
        if self.on_record:
            self.on_record()

    def _on_delete(self):
        """删除按钮点击"""
        if self.on_delete:
            self.on_delete()

    def _on_clear(self):
        """清空按钮点击"""
        if self.on_clear:
            self.on_clear()

    def _on_export(self):
        """导出按钮点击"""
        if self.on_export:
            self.on_export()

    def _on_update_key(self):
        """更新按键"""
        if self.on_update_key:
            new_key = self.key_var.get().strip().lower()
            if new_key:
                self.on_update_key(new_key)
            else:
                messagebox.showerror("错误", "按键不能为空")

    def _on_record_double_click(self, event):
        """记录双击事件"""
        if self.on_record_double_click:
            self.on_record_double_click(event)

    def update_current_time(self, time_str: str):
        """更新当前时间显示
        
        Args:
            time_str: 时间字符串
        """
        self.current_time_var.set(time_str)

    def update_stats(self, count: int, current_time: float = 0):
        """更新统计信息
        
        Args:
            count: 记录数量
            current_time: 当前视频时间
        """
        if current_time > 0:
            self.stats_label.config(
                text=f"记录点数: {count} | 当前视频时间: {current_time:.3f}秒"
            )
        else:
            self.stats_label.config(text=f"记录点数: {count}")

    def add_record(self, sequence: int, time_display: str, video_time: float, interval: float):
        """添加记录到列表
        
        Args:
            sequence: 序号
            time_display: 时间显示字符串
            video_time: 视频时间（秒）
            interval: 间隔时间（秒）
        """
        # 判断是否是成对记录的开始（奇数序号）
        sequence_display = str(sequence)
        if sequence % 2 == 1:
            sequence_display = f"[{sequence_display}"
        elif sequence % 2 == 0 and sequence > 0:
            sequence_display = f"{sequence_display}]"

        self.tree.insert('', 'end', values=(
            sequence_display,
            time_display,
            f"{video_time:.3f}",
            f"{interval:.3f}" if interval > 0 else "0.000"
        ))

        # 滚动到最新记录
        children = self.tree.get_children()
        if children:
            self.tree.see(children[-1])

    def clear_records(self):
        """清空记录列表"""
        for item in self.tree.get_children():
            self.tree.delete(item)

    def refresh_records(self, records: List[Tuple[int, str, float, float]]):
        """刷新记录列表
        
        Args:
            records: 记录列表，每个元素为 (sequence, time_display, video_time, interval)
        """
        self.clear_records()
        for record in records:
            self.add_record(*record)

    def get_selected_sequences(self) -> List[int]:
        """获取选中记录的序号列表
        
        Returns:
            序号列表
        """
        selected_items = self.tree.selection()
        sequences = []

        for item in selected_items:
            values = self.tree.item(item, 'values')
            if values:
                # 解析序号（可能包含'['或']'符号）
                sequence_str = str(values[0]).strip('[]')
                try:
                    sequence_num = int(sequence_str)
                    sequences.append(sequence_num)
                except ValueError:
                    continue

        return sequences

    def get_selected_record_time(self) -> Optional[float]:
        """获取选中记录的视频时间
        
        Returns:
            视频时间（秒），如果没有选中则返回None
        """
        selected_items = self.tree.selection()
        if not selected_items:
            return None

        item = selected_items[0]
        values = self.tree.item(item, 'values')
        if not values or len(values) < 3:
            return None

        try:
            return float(values[2])
        except (ValueError, IndexError):
            return None

    def set_record_key(self, key: str):
        """设置记录按键
        
        Args:
            key: 按键名称
        """
        self.key_var.set(key)

    def get_record_key(self) -> str:
        """获取记录按键
        
        Returns:
            按键名称
        """
        return self.key_var.get().strip().lower()

