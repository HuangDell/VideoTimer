import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import datetime
import pandas as pd
import keyboard
import threading
import time
import cv2
from PIL import Image, ImageTk
import os
import math


class VideoStopwatch:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("视频计时器 - Video Timer")
        self.root.geometry("1400x900")

        # 视频相关变量
        self.video_capture = None
        self.video_playing = False
        self.video_paused = False
        self.video_fps = 30
        self.current_frame = 0
        self.total_frames = 0

        # 记录相关变量
        self.records = []
        self.record_key = 'z'

        # 用于实时更新显示的变量
        self.current_time_var = tk.StringVar(value="00:00:00.000")

        self.setup_ui()
        self.setup_keyboard_listener()
        self.start_display_update()

    def setup_ui(self):
        # 主框架
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

        # 创建左右两个主要区域
        self.setup_video_area(main_frame)
        self.setup_timing_area(main_frame)

    def setup_video_area(self, parent):
        """设置视频播放区域（左侧）"""
        video_frame = ttk.LabelFrame(parent, text="视频播放区域", padding="5")
        video_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        video_frame.columnconfigure(0, weight=1)
        video_frame.rowconfigure(1, weight=1)

        # 视频控制按钮
        video_controls = ttk.Frame(video_frame)
        video_controls.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))

        # 选择视频文件按钮
        select_video_btn = ttk.Button(video_controls, text="选择视频", command=self.select_video_file)
        select_video_btn.pack(side=tk.LEFT, padx=(0, 5))

        # 播放/暂停按钮
        self.play_pause_btn = ttk.Button(video_controls, text="播放", command=self.toggle_video_playback,
                                         state='disabled')
        self.play_pause_btn.pack(side=tk.LEFT, padx=(0, 5))

        # 停止按钮
        self.stop_btn = ttk.Button(video_controls, text="重置", command=self.stop_video, state='disabled')
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))

        fullscreen_btn = ttk.Button(video_controls, text="全屏", command=self.toggle_fullscreen)
        fullscreen_btn.pack(side=tk.LEFT, padx=(0, 5))

        # 视频显示区域
        self.video_label = ttk.Label(video_frame, text="请选择视频文件", font=('Arial', 12),
                                     relief='sunken', borderwidth=1)
        self.video_label.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))

        # 视频信息区域
        info_frame = ttk.Frame(video_frame)
        info_frame.grid(row=2, column=0, sticky=(tk.W, tk.E))
        info_frame.columnconfigure(0, weight=1)

        # 视频进度信息
        self.video_info_var = tk.StringVar(value="未加载视频")
        video_info_label = ttk.Label(info_frame, textvariable=self.video_info_var, font=('Arial', 9))
        video_info_label.grid(row=0, column=0, sticky=tk.W)

        # 视频路径显示
        self.video_path_var = tk.StringVar(value="")
        video_path_label = ttk.Label(info_frame, textvariable=self.video_path_var, font=('Arial', 8),
                                     foreground='gray')
        video_path_label.grid(row=1, column=0, sticky=tk.W)

    def setup_timing_area(self, parent):
        """设置计时区域（右侧）"""
        timing_frame = ttk.LabelFrame(parent, text="视频计时区域", padding="10")
        timing_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        timing_frame.columnconfigure(0, weight=1)
        timing_frame.rowconfigure(3, weight=1)

        # 当前时间显示
        time_display_frame = ttk.Frame(timing_frame)
        time_display_frame.grid(row=0, column=0, pady=(0, 15))

        ttk.Label(time_display_frame, text="视频播放时间:", font=('Arial', 12)).pack()
        self.time_display = ttk.Label(
            time_display_frame,
            textvariable=self.current_time_var,
            font=('Arial', 20, 'bold'),
            foreground='blue'
        )
        self.time_display.pack()

        # 控制按钮
        controls = ttk.Frame(timing_frame)
        controls.grid(row=1, column=0, pady=(0, 10), sticky=(tk.W, tk.E))

        # 记录时间点按钮
        record_btn = ttk.Button(controls, text="记录时间点", command=self.manual_record)
        record_btn.pack(side=tk.LEFT, padx=(0, 10))

        # 清空记录按钮
        clear_btn = ttk.Button(controls, text="清空记录", command=self.clear_records)
        clear_btn.pack(side=tk.LEFT, padx=(0, 10))

        # 导出按钮
        export_btn = ttk.Button(controls, text="导出Excel", command=self.export_to_excel)
        export_btn.pack(side=tk.LEFT)

        # 按键设置框架
        key_frame = ttk.LabelFrame(timing_frame, text="快捷键设置", padding="5")
        key_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(key_frame, text="记录按键:").pack(side=tk.LEFT, padx=(0, 5))
        self.key_var = tk.StringVar(value=self.record_key)
        key_entry = ttk.Entry(key_frame, textvariable=self.key_var, width=15)
        key_entry.pack(side=tk.LEFT, padx=(0, 10))

        update_key_btn = ttk.Button(key_frame, text="更新", command=self.update_key)
        update_key_btn.pack(side=tk.LEFT)

        # 记录列表
        list_frame = ttk.LabelFrame(timing_frame, text="时间记录点", padding="5")
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

        # 统计信息
        self.stats_label = ttk.Label(timing_frame, text="记录点数: 0", font=('Arial', 9))
        self.stats_label.grid(row=4, column=0, pady=(10, 0))

    def get_current_video_time(self):
        """获取当前视频播放时间（秒）"""
        if self.video_capture and self.video_fps > 0:
            return self.current_frame / self.video_fps
        return 0

    def start_display_update(self):
        """启动显示更新线程"""
        self.display_thread = threading.Thread(target=self.update_display_loop, daemon=True)
        self.display_thread.start()

    def update_display_loop(self):
        """实时更新时间显示"""
        while True:
            if self.video_capture:
                current_video_time = self.get_current_video_time()
                time_str = self.format_time(current_video_time)
                self.current_time_var.set(time_str)

                # 更新统计信息
                count = len(self.records)
                self.root.after(0, lambda: self.stats_label.config(
                    text=f"记录点数: {count} | 当前视频时间: {current_video_time:.3f}秒"
                ))

            time.sleep(0.1)  # 100ms更新一次足够了

    def setup_keyboard_listener(self):
        """设置键盘监听"""
        self.keyboard_thread = threading.Thread(target=self.keyboard_listener, daemon=True)
        self.keyboard_thread.start()

    def keyboard_listener(self):
        """键盘监听线程"""
        while True:
            try:
                if self.video_playing and keyboard.is_pressed(self.record_key):
                    self.record_time()
                    time.sleep(0.3)  # 防止重复触发
                time.sleep(0.01)
            except:
                time.sleep(0.1)

    def select_video_file(self):
        """选择视频文件"""
        file_path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[
                ("视频文件", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm"),
                ("所有文件", "*.*")
            ]
        )

        if file_path:
            self.load_video(file_path)

    def load_video(self, file_path):
        """加载视频文件"""
        try:
            # 释放之前的视频资源
            if self.video_capture:
                self.video_capture.release()

            # 清空之前的记录
            self.clear_records()

            self.video_capture = cv2.VideoCapture(file_path)

            if not self.video_capture.isOpened():
                messagebox.showerror("错误", "无法打开视频文件")
                return

            # 获取视频信息
            self.video_fps = self.video_capture.get(cv2.CAP_PROP_FPS)
            self.total_frames = int(self.video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
            video_duration = self.total_frames / self.video_fps

            # 显示视频信息
            filename = os.path.basename(file_path)
            self.video_path_var.set(f"文件: {filename}")
            self.video_info_var.set(
                f"总时长: {self.format_time(video_duration)} | 总帧数: {self.total_frames} | FPS: {self.video_fps:.2f}")

            # 重置到第一帧
            self.current_frame = 0
            self.show_current_frame()

            # 启用控制按钮
            self.play_pause_btn.config(state='normal')
            self.stop_btn.config(state='normal')

        except Exception as e:
            messagebox.showerror("错误", f"加载视频失败: {str(e)}")

    def show_current_frame(self):
        """显示当前帧"""
        if not self.video_capture:
            return

        ret, frame = self.video_capture.read()
        if ret:
            # 获取标签的实际尺寸
            self.video_label.update_idletasks()
            label_width = self.video_label.winfo_width()
            label_height = self.video_label.winfo_height()

            # 设置显示尺寸
            if label_width > 10 and label_height > 10:
                max_width = max(label_width - 10, 400)
                max_height = max(label_height - 10, 300)
            else:
                max_width, max_height = 800, 600

            # 调整图像大小
            height, width = frame.shape[:2]
            scale = min(max_width / width, max_height / height)
            new_width = int(width * scale)
            new_height = int(height * scale)

            frame = cv2.resize(frame, (new_width, new_height))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # 转换为PIL Image并显示
            image = Image.fromarray(frame)
            photo = ImageTk.PhotoImage(image)
            self.video_label.config(image=photo, text="")
            self.video_label.image = photo

    def toggle_video_playback(self):
        """切换视频播放/暂停状态"""
        if not self.video_playing:
            self.start_video_playback()
        else:
            self.pause_video_playback()

    def start_video_playback(self):
        """开始视频播放"""
        if not self.video_capture:
            return

        self.video_playing = True
        self.play_pause_btn.config(text="暂停")

        # 开始视频播放线程
        self.video_thread = threading.Thread(target=self.play_video_loop, daemon=True)
        self.video_thread.start()

    def pause_video_playback(self):
        """暂停视频播放"""
        self.video_playing = False
        self.play_pause_btn.config(text="播放")

    def stop_video(self):
        """停止视频播放"""
        self.video_playing = False
        self.current_frame = 0

        if self.video_capture:
            self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.show_current_frame()

        self.play_pause_btn.config(text="播放")

    def play_video_loop(self):
        """视频播放循环"""
        while self.video_playing and self.video_capture:
            start_time = time.time()

            ret, frame = self.video_capture.read()
            if not ret:
                # 视频播放完毕
                self.root.after(0, self.on_video_finished)
                break

            self.current_frame += 1

            # 在主线程中更新显示
            self.root.after(0, self.update_video_display, frame)

            # 控制播放速度
            elapsed = time.time() - start_time
            target_delay = 1.0 / self.video_fps
            if elapsed < target_delay:
                time.sleep(target_delay - elapsed)

    def update_video_display(self, frame):
        """更新视频显示"""
        try:
            # 获取标签的实际尺寸
            self.video_label.update_idletasks()
            label_width = self.video_label.winfo_width()
            label_height = self.video_label.winfo_height()

            # 设置显示尺寸
            if label_width > 10 and label_height > 10:
                max_width = max(label_width - 10, 400)
                max_height = max(label_height - 10, 300)
            else:
                max_width, max_height = 800, 600

            # 调整图像大小
            height, width = frame.shape[:2]
            scale = min(max_width / width, max_height / height)
            new_width = int(width * scale)
            new_height = int(height * scale)

            frame = cv2.resize(frame, (new_width, new_height))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            image = Image.fromarray(frame)
            photo = ImageTk.PhotoImage(image)
            self.video_label.config(image=photo)
            self.video_label.image = photo

            # 更新进度信息
            current_time = self.get_current_video_time()
            total_time = self.total_frames / self.video_fps
            progress_text = f"进度: {self.format_time(current_time)} / {self.format_time(total_time)}"
            self.video_info_var.set(f"{progress_text} | 帧: {self.current_frame}/{self.total_frames}")

        except Exception as e:
            print(f"更新视频显示错误: {e}")

    def toggle_fullscreen(self):
        """切换全屏模式"""
        current_state = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not current_state)

        # 按ESC键退出全屏
        if not current_state:
            self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))

    def on_video_finished(self):
        """视频播放完毕"""
        self.video_playing = False
        self.play_pause_btn.config(text="播放")
        messagebox.showinfo("提示", "视频播放完毕")

    def record_time(self):
        """记录当前视频播放时间"""
        if not self.video_capture:
            messagebox.showwarning("提示", "请先加载视频")
            return

        video_time = self.get_current_video_time()

        # 计算与上一次记录的间隔
        interval = 0
        if self.records:
            interval = video_time - self.records[-1]['video_time']

        record = {
            'sequence': len(self.records) + 1,
            'time_display': self.format_time(video_time),
            'video_time': round(video_time, 3),
            'interval': round(interval, 3)
        }

        self.records.append(record)
        self.add_record_to_tree(record)

    def manual_record(self):
        """手动记录时间点"""
        self.record_time()

    def add_record_to_tree(self, record):
        """添加记录到列表"""
        self.tree.insert('', 'end', values=(
            record['sequence'],
            record['time_display'],
            f"{record['video_time']:.3f}",
            f"{record['interval']:.3f}" if record['interval'] > 0 else "0.000"
        ))

        # 滚动到最新记录
        children = self.tree.get_children()
        if children:
            self.tree.see(children[-1])

    def clear_records(self):
        """清空记录"""
        self.records.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.stats_label.config(text="记录点数: 0")

    def update_key(self):
        """更新按键设置"""
        new_key = self.key_var.get().strip().lower()
        if new_key:
            self.record_key = new_key
            messagebox.showinfo("成功", f"记录按键已更新为: {new_key}")
        else:
            messagebox.showerror("错误", "按键不能为空")

    def format_time(self, seconds):
        """格式化时间显示"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

    def format_time_for_excel(self, seconds):
        """Excel格式时间"""
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        secs = int(remaining_seconds)
        milliseconds = int((remaining_seconds - secs) * 100)
        return f"{minutes}.{secs:02d}.{milliseconds:02d}"

    def calculate_interval_statistics(self):
        """计算区间统计信息
        返回：
        1. 所有区间的总时间
        2. 按分钟分组的区间时间字典
        """
        # 提取成对的区间
        intervals = []
        for i in range(0, len(self.records), 2):
            if i + 1 < len(self.records):
                start_time = self.records[i]['video_time']
                end_time = self.records[i + 1]['video_time']
                intervals.append({'start': start_time, 'end': end_time, 'duration': end_time - start_time})

        # 1. 计算总时间
        total_duration = sum(interval['duration'] for interval in intervals)

        # 2. 按分钟分组统计
        minute_stats = {}

        for interval in intervals:
            start_time = interval['start']
            end_time = interval['end']

            # 计算开始和结束所在的分钟
            start_minute = int(start_time // 60)
            end_minute = int(end_time // 60)

            if start_minute == end_minute:
                # 区间在同一分钟内
                if start_minute not in minute_stats:
                    minute_stats[start_minute] = 0
                minute_stats[start_minute] += (end_time - start_time)
            else:
                # 区间跨越多个分钟
                # 处理开始分钟
                next_minute_start = (start_minute + 1) * 60
                if start_minute not in minute_stats:
                    minute_stats[start_minute] = 0
                minute_stats[start_minute] += (next_minute_start - start_time)

                # 处理中间完整的分钟
                for minute in range(start_minute + 1, end_minute):
                    if minute not in minute_stats:
                        minute_stats[minute] = 0
                    minute_stats[minute] += 60

                # 处理结束分钟
                minute_start = end_minute * 60
                if end_minute not in minute_stats:
                    minute_stats[end_minute] = 0
                minute_stats[end_minute] += (end_time - minute_start)

        return total_duration, minute_stats, intervals

    def export_to_excel(self):
        """导出到Excel"""
        if not self.records:
            messagebox.showwarning("警告", "没有数据可导出")
            return

        try:
            file_path = filedialog.asksaveasfilename(
                title="保存Excel文件",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )

            if not file_path:
                return

            # ========== Sheet 1: 原始成对数据 ==========
            paired_data = []
            for i in range(0, len(self.records), 2):
                start_record = self.records[i]
                start_time_formatted = self.format_time_for_excel(start_record['video_time'])

                if i + 1 < len(self.records):
                    end_record = self.records[i + 1]
                    end_time_formatted = self.format_time_for_excel(end_record['video_time'])
                    interval_seconds = end_record['video_time'] - start_record['video_time']
                    interval_formatted = self.format_time_for_excel(interval_seconds)

                    paired_data.append({
                        '启(分)': start_time_formatted,
                        '止(分)': end_time_formatted,
                        '间隔时间': interval_formatted
                    })
                else:
                    paired_data.append({
                        '启(分)': start_time_formatted,
                        '止(分)': '未完成',
                        '间隔时间': '未完成'
                    })

            df_paired = pd.DataFrame(paired_data)

            # 汇总信息
            total_video_time = self.total_frames / self.video_fps if self.video_fps > 0 else 0
            total_time_formatted = self.format_time_for_excel(total_video_time)

            summary_data = [
                {'启(分)': '', '止(分)': '', '间隔时间': ''},
                {'启(分)': '汇总信息', '止(分)': '', '间隔时间': ''},
                {'启(分)': f'视频文件: {self.video_path_var.get()}', '止(分)': f'总记录点数: {len(self.records)}',
                 '间隔时间': f'视频总时长: {total_time_formatted}'},
                {'启(分)': f'完整配对数: {len(self.records) // 2}', '止(分)': f'未配对数: {len(self.records) % 2}',
                 '间隔时间': f'视频FPS: {self.video_fps:.2f}'}
            ]

            summary_df = pd.DataFrame(summary_data)
            final_df_paired = pd.concat([df_paired, summary_df], ignore_index=True)

            # ========== Sheet 2: 区间统计 ==========
            total_duration, minute_stats, intervals = self.calculate_interval_statistics()

            # 区间总时长统计
            stats_data = [{'统计项': '区间总数', '数值': len(intervals), '单位': '个'},
                          {'统计项': '区间总时长', '数值': f"{total_duration:.3f}", '单位': '秒'},
                          {'统计项': '区间总时长', '数值': self.format_time_for_excel(total_duration),
                           '单位': '分.秒.毫秒'},
                          {'统计项': '区间总时长', '数值': self.format_time(total_duration), '单位': '时:分:秒'},
                          {'统计项': '', '数值': '', '单位': ''}, {'统计项': '详细区间列表', '数值': '', '单位': ''}]

            df_stats = pd.DataFrame(stats_data)

            detail_data = []
            # 详细区间列表
            for idx, interval in enumerate(intervals, 1):
                detail_data.append({
                    '区间编号': f'区间 {idx}',
                    '起止时间': f"{interval['start']:.3f}s - {interval['end']:.3f}s",
                    '区间长度(s)': f"{interval['duration']:.3f}"
                })

            df_detail = pd.DataFrame(detail_data)


            # ========== Sheet 3: 按分钟统计 ==========
            minute_data = []

            # 按分钟排序
            sorted_minutes = sorted(minute_stats.keys())

            for minute in sorted_minutes:
                duration = minute_stats[minute]
                minute_data.append({
                    '分钟区间': f"第 {minute + 1} 分钟 ({minute}:00 - {minute}:59)",
                    '区间时长（秒）': f"{duration:.3f}",
                    '区间时长（格式化）': self.format_time_for_excel(duration),
                    '占该分钟比例': f"{(duration / 60 * 100):.2f}%"
                })

            # 添加总计行
            minute_data.append({
                '分钟区间': '总计',
                '区间时长（秒）': f"{total_duration:.3f}",
                '区间时长（格式化）': self.format_time_for_excel(total_duration),
                '占该分钟比例': ''
            })

            df_minute = pd.DataFrame(minute_data)

            # ========== 写入Excel ==========
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Sheet 1: 原始数据
                final_df_paired.to_excel(writer, sheet_name='原始记录', index=False)
                worksheet1 = writer.sheets['原始记录']
                worksheet1.column_dimensions['A'].width = 15
                worksheet1.column_dimensions['B'].width = 15
                worksheet1.column_dimensions['C'].width = 15

                # Sheet 2: 区间统计
                df_stats.to_excel(writer, sheet_name='区间统计', index=False)
                worksheet2 = writer.sheets['区间统计']
                worksheet2.column_dimensions['A'].width = 25
                worksheet2.column_dimensions['B'].width = 30
                worksheet2.column_dimensions['C'].width = 20

                df_detail.to_excel(writer,sheet_name='区间详情',index= False)
                worksheet2 = writer.sheets['区间详情']
                worksheet2.column_dimensions['A'].width = 25
                worksheet2.column_dimensions['B'].width = 30
                worksheet2.column_dimensions['C'].width = 20

                # Sheet 3: 按分钟统计
                df_minute.to_excel(writer, sheet_name='按分钟统计', index=False)
                worksheet3 = writer.sheets['按分钟统计']
                worksheet3.column_dimensions['A'].width = 30
                worksheet3.column_dimensions['B'].width = 18
                worksheet3.column_dimensions['C'].width = 20
                worksheet3.column_dimensions['D'].width = 18

            messagebox.showinfo("成功",
                                f"数据已导出到: {file_path}\n\n"
                                f"包含3个工作表：\n"
                                f"1. 原始记录 - 成对的时间点记录\n"
                                f"2. 区间统计 - 所有区间的总时长统计\n"
                                f"3. 按分钟统计 - 每分钟内的区间时间\n\n"
                                f"区间总数: {len(intervals)}\n"
                                f"区间总时长: {total_duration:.3f}秒\n"
                                f"涉及分钟数: {len(minute_stats)}")

        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")
            import traceback
            traceback.print_exc()

    def run(self):
        """运行程序"""
        try:
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
        except KeyboardInterrupt:
            pass

    def on_closing(self):
        """关闭程序时清理资源"""
        self.video_playing = False
        if self.video_capture:
            self.video_capture.release()
        self.root.destroy()


def main():
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

    app = VideoStopwatch()
    app.run()


if __name__ == "__main__":
    main()