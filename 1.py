import threading
import time
import tkinter as tk
from PIL import Image, ImageDraw
import pystray
import ctypes
import logging
import os
import sys
from ctypes import wintypes, c_void_p, POINTER, byref, c_ulong, WINFUNCTYPE

# ==================== 配置区 ====================
CHECK_INTERVAL = 0.8
DOT_SIZE = 18
DOT_COLOR = "#FF0000"
MARGIN_RIGHT = 20
MARGIN_TOP = 60
LOG_FILE = "camera_guard.log"
# ================================================

def setup_logging():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(base_dir, LOG_FILE)
    logger = logging.getLogger("CameraGuard")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s | %(levelname)-7s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        fh = logging.FileHandler(log_path, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        logger.info(f"✅ 日志初始化成功: {log_path}")
    return logger

logger = setup_logging()

# HRESULT 常量
S_OK = 0
MF_E_DEVICE_IN_USE = 0xC00D36D9
E_ACCESSDENIED = 0x80070005
COINIT_APARTMENTTHREADED = 0x2
COINIT_DISABLE_OLE1DDE = 0x4


def is_camera_in_use_mf():
    """
    Media Foundation Capture Engine 检测
    在独立线程中运行，使用 STA 模式初始化 COM
    MFCreateCaptureEngine 成功 = 空闲
    返回 MF_E_DEVICE_IN_USE / E_ACCESSDENIED = 占用
    """
    hr_com = None
    hr_startup = None
    capture_engine = c_void_p()
    
    try:
        # ⭐ STA 模式 + 禁用 OLE1DDE，避免与 tkinter 的 MTA 冲突
        hr_com = ctypes.windll.ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE)
        logger.debug(f"[MF] CoInitializeEx(STA) = 0x{hr_com & 0xFFFFFFFF:08X}")
        
        mfplat = ctypes.windll.mfplat
        hr_startup = mfplat.MFStartup(0x00020070, 0)  # MF_VERSION_WIN7
        logger.debug(f"[MF] MFStartup = 0x{hr_startup & 0xFFFFFFFF:08X}")
        
        if hr_startup != S_OK:
            logger.warning(f"[MF] MFStartup 失败，跳过")
            return False
        
        hr_create = ctypes.windll.mfreadwrite.MFCreateCaptureEngine(byref(capture_engine))
        logger.debug(f"[MF] MFCreateCaptureEngine = 0x{hr_create & 0xFFFFFFFF:08X}, handle={capture_engine.value}")
        
        if hr_create == MF_E_DEVICE_IN_USE or hr_create == E_ACCESSDENIED:
            logger.info(f"[MF] ✅ 摄像头被占用 (HRESULT=0x{hr_create & 0xFFFFFFFF:08X})")
            return True
        
        if hr_create == S_OK:
            logger.debug("[MF] 引擎创建成功 → 摄像头空闲")
            return False
        
        # 其他错误（如设备不存在）视为空闲
        logger.warning(f"[MF] 非预期返回值: 0x{hr_create & 0xFFFFFFFF:08X}，视为空闲")
        return False
        
    except AttributeError as e:
        logger.error(f"[MF] DLL函数缺失: {e}")
        return False
    except Exception as e:
        logger.error(f"[MF] 异常: {type(e).__name__}: {e}", exc_info=True)
        return False
    finally:
        # 安全释放
        try:
            if capture_engine.value:
                vtable_ptr = ctypes.cast(capture_engine.value, POINTER(c_void_p))[0]
                vtable = ctypes.cast(vtable_ptr, POINTER(c_void_p))
                release_fn = WINFUNCTYPE(c_ulong)(vtable[2])
                ref = release_fn(capture_engine.value)
                logger.debug(f"[MF] Release refcount={ref}")
        except Exception as e:
            logger.debug(f"[MF] Release 异常: {e}")
        
        try:
            if hr_startup == S_OK:
                mfplat.MFShutdown()
        except Exception: pass
        
        try:
            if hr_com is not None and hr_com != 1:  # S_FALSE=1 表示已初始化
                ctypes.windll.ole32.CoUninitialize()
        except Exception: pass


class CameraIndicator:
    def __init__(self):
        self.root = None
        self.dot_window = None
        self.is_showing = False
        self.running = True
        logger.info("CameraIndicator 实例已创建")

    def _create_dot(self):
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.95)
        win.configure(bg=DOT_COLOR)
        win.geometry(f"{DOT_SIZE}x{DOT_SIZE}")
        screen_w = win.winfo_screenwidth()
        x = screen_w - MARGIN_RIGHT - DOT_SIZE
        y = MARGIN_TOP
        win.geometry(f"+{x}+{y}")
        logger.info(f"🔴 红点显示 @ ({x}, {y})")
        return win

    def show_dot(self):
        if not self.is_showing:
            self.dot_window = self._create_dot()
            self.is_showing = True

    def hide_dot(self):
        if self.is_showing and self.dot_window:
            self.dot_window.destroy()
            self.dot_window = None
            self.is_showing = False
            logger.info("⚫ 红点隐藏")

    def _monitor_loop(self):
        logger.info(f"🔄 监控启动，间隔={CHECK_INTERVAL}s")
        cycle = 0
        while self.running:
            cycle += 1
            try:
                in_use = is_camera_in_use_mf()
                self.root.after(0, self.show_dot if in_use else self.hide_dot)
            except Exception as e:
                logger.critical(f"❌ 循环异常 (cycle={cycle}): {e}", exc_info=True)
            time.sleep(CHECK_INTERVAL)
        logger.info("🛑 监控退出")

    def _create_tray_icon_image(self):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle([8, 16, 48, 48], fill="white", outline="black", width=2)
        draw.polygon([(48, 24), (58, 18), (58, 46), (48, 40)], fill="white", outline="black")
        return img

    def _on_quit(self, icon=None, item=None):
        logger.info("🚪 退出程序")
        self.running = False
        self.root.after(0, self.root.quit)
        if icon: icon.stop()

    def run(self):
        logger.info("🚀 CameraGuard 启动")
        self.root = tk.Tk()
        self.root.withdraw()
        monitor = threading.Thread(target=self._monitor_loop, daemon=True)
        monitor.start()
        menu = pystray.Menu(pystray.MenuItem("退出", self._on_quit, default=True))
        icon = pystray.Icon("CameraGuard", self._create_tray_icon_image(), "📷 摄像头守护", menu)
        tray_thread = threading.Thread(target=icon.run, daemon=True)
        tray_thread.start()
        logger.info("✅ 托盘就绪")
        self.root.mainloop()
        icon.stop()
        logger.info("👋 程序退出")


if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception: pass
    app = CameraIndicator()
    app.run()