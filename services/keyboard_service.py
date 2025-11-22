"""键盘监听服务类"""
import threading
import time
from typing import Optional, Callable
from utils.config import Config


class KeyboardService:
    """键盘监听服务类 - 负责全局键盘监听"""
    
    def __init__(self):
        self.config = Config()
        self._listening = False
        self._listener_thread: Optional[threading.Thread] = None
        self._key_callbacks: dict[str, Callable] = {}

    def register_key(self, key: str, callback: Callable):
        """注册按键回调
        
        Args:
            key: 按键名称
            callback: 回调函数
        """
        self._key_callbacks[key.lower()] = callback

    def unregister_key(self, key: str):
        """取消注册按键
        
        Args:
            key: 按键名称
        """
        key_lower = key.lower()
        if key_lower in self._key_callbacks:
            del self._key_callbacks[key_lower]

    def start_listening(self):
        """开始监听"""
        if self._listening:
            return

        self._listening = True
        self._listener_thread = threading.Thread(target=self._listener_loop, daemon=True)
        self._listener_thread.start()

    def stop_listening(self):
        """停止监听"""
        self._listening = False

    def _listener_loop(self):
        """监听循环"""
        import keyboard
        
        debounce_time = self.config.get('keyboard_debounce', 0.3)
        check_interval = self.config.get('keyboard_check_interval', 0.01)
        last_triggered = {}

        while self._listening:
            try:
                for key, callback in self._key_callbacks.items():
                    if keyboard.is_pressed(key):
                        # 防抖处理
                        current_time = time.time()
                        last_time = last_triggered.get(key, 0)
                        
                        if current_time - last_time >= debounce_time:
                            try:
                                callback()
                                last_triggered[key] = current_time
                            except Exception as e:
                                print(f"键盘回调执行错误: {e}")

                time.sleep(check_interval)
            except Exception as e:
                print(f"键盘监听错误: {e}")
                time.sleep(0.1)

