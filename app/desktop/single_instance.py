from __future__ import annotations

import ctypes
import sys


ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    def __init__(self, name="Local\\RLabResearchAssistant"):
        self.name = name
        self.handle = None
        self.already_running = False

    def acquire(self):
        if sys.platform != "win32":
            return True
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        self.handle = kernel32.CreateMutexW(None, False, self.name)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "无法创建应用单实例锁")
        self.already_running = kernel32.GetLastError() == ERROR_ALREADY_EXISTS
        return not self.already_running

    def release(self):
        if self.handle and sys.platform == "win32":
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *_args):
        self.release()
