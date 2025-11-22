"""实例选择对话框视图"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Tuple, List
from utils.config import Config


class InstanceSelector:
    """实例选择对话框"""
    
    @staticmethod
    def show() -> Tuple[int, List[str]]:
        """显示实例选择对话框
        
        Returns:
            (实例数量, 快捷键列表)，如果取消则返回 (0, [])
        """
        config = Config()
        selection_window = tk.Tk()
        selection_window.title("选择实例数量")
        selection_window.geometry("400x280")
        selection_window.resizable(False, False)

        # 居中显示
        selection_window.update_idletasks()
        x = (selection_window.winfo_screenwidth() // 2) - (selection_window.winfo_width() // 2)
        y = (selection_window.winfo_screenheight() // 2) - (selection_window.winfo_height() // 2)
        selection_window.geometry(f"+{x}+{y}")

        result = {
            'count': config.get('default_instances', 1),
            'keys': config.get('default_keys', ['z', 'x', 'c', 'v']),
            'confirmed': False
        }

        def on_confirm():
            try:
                count = int(instance_var.get())
                max_instances = config.get('max_instances', 4)
                if 1 <= count <= max_instances:
                    result['count'] = count
                    # 获取每个实例的快捷键
                    keys = []
                    for i in range(count):
                        key = key_vars[i].get().strip().lower()
                        if not key:
                            messagebox.showerror("错误", f"实例 {i+1} 的快捷键不能为空")
                            return
                        keys.append(key)
                    result['keys'] = keys
                    result['confirmed'] = True
                    selection_window.quit()
                    selection_window.destroy()
                else:
                    messagebox.showerror("错误", f"请选择1-{max_instances}个实例")
            except ValueError:
                messagebox.showerror("错误", "请输入有效的数字")

        # 主标签
        ttk.Label(
            selection_window, 
            text="请选择要打开的实例数量:", 
            font=('Arial', 12)
        ).pack(pady=10)

        # 实例数量选择
        instance_frame = ttk.Frame(selection_window)
        instance_frame.pack(pady=5)

        instance_var = tk.StringVar(value=str(result['count']))
        max_instances = config.get('max_instances', 4)
        for i in range(1, max_instances + 1):
            ttk.Radiobutton(
                instance_frame, 
                text=str(i), 
                variable=instance_var, 
                value=str(i)
            ).pack(side=tk.LEFT, padx=10)

        # 快捷键设置框架
        keys_frame = ttk.LabelFrame(selection_window, text="快捷键设置（每个实例）", padding="5")
        keys_frame.pack(pady=10, padx=20, fill=tk.X)

        key_vars = []
        default_keys = config.get('default_keys', ['z', 'x', 'c', 'v'])
        for i in range(max_instances):
            key_frame = ttk.Frame(keys_frame)
            key_frame.pack(fill=tk.X, pady=2)
            ttk.Label(key_frame, text=f"实例 {i+1}:", width=10).pack(side=tk.LEFT)
            key_var = tk.StringVar(value=default_keys[i] if i < len(default_keys) else '')
            key_entry = ttk.Entry(key_frame, textvariable=key_var, width=10)
            key_entry.pack(side=tk.LEFT, padx=5)
            key_vars.append(key_var)

        # 确认按钮
        ttk.Button(selection_window, text="确认", command=on_confirm).pack(pady=10)

        # 处理窗口关闭事件
        def on_selection_close():
            result['confirmed'] = False
            selection_window.quit()
            selection_window.destroy()

        selection_window.protocol("WM_DELETE_WINDOW", on_selection_close)
        selection_window.mainloop()

        if result['confirmed']:
            return result['count'], result['keys']
        else:
            return 0, []

