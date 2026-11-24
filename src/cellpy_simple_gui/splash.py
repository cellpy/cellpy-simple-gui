"""Starting window for the windowed Windows build (#183).

Shown before the heavy imports, so a first launch does not look frozen.
Other platforms do nothing. This module imports none of the rest of the app.
"""

from __future__ import annotations

import sys
import threading

_TITLE = "Starting cellpy simple GUI"
_TEXT = "Starting cellpy simple GUI\n\nThe first launch can take a minute."

_lock = threading.Lock()
_thread: threading.Thread | None = None
_hwnd: int | None = None
_ready = threading.Event()


def show() -> None:
    """Open the starting window. Returns once it is up, or immediately if it cannot be."""
    if sys.platform != "win32":
        return
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        _ready.clear()
        _thread = threading.Thread(target=_run, name="csg-starting", daemon=True)
        _thread.start()
    _ready.wait(timeout=2.0)


def close() -> None:
    """Close the starting window. Safe when it was never shown, and safe twice."""
    if sys.platform != "win32":
        return
    with _lock:
        hwnd = _hwnd
        thread = _thread
    if not hwnd or thread is None:
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.PostMessageW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        ]
        user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
    except Exception:  # noqa: BLE001 - a missing window must not block startup
        return
    thread.join(timeout=2.0)


def _run() -> None:
    global _hwnd
    try:
        hwnd = _open_window()
        with _lock:
            _hwnd = hwnd
        _ready.set()
        if hwnd:
            _message_loop()
    except Exception:  # noqa: BLE001 - no splash is better than no app
        _ready.set()
    finally:
        with _lock:
            _hwnd = None
        _ready.set()


def _open_window() -> int | None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    comctl32 = ctypes.WinDLL("comctl32", use_last_error=True)

    user32.DefWindowProcW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    ]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.RegisterClassW.argtypes = [ctypes.c_void_p]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.PostQuitMessage.argtypes = [ctypes.c_int]
    user32.SendMessageW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    ]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UpdateWindow.argtypes = [wintypes.HWND]

    wndproc_type = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    )

    @wndproc_type
    def wnd_proc(hwnd, msg, wparam, lparam):
        if msg == 0x0010:  # WM_CLOSE
            user32.DestroyWindow(hwnd)
            return 0
        if msg == 0x0002:  # WM_DESTROY
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # The thread must keep this alive for as long as the window exists.
    _open_window.proc = wnd_proc  # type: ignore[attr-defined]

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", wndproc_type),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]

    class INITCOMMONCONTROLSEX(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("dwICC", wintypes.DWORD)]

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    icc = INITCOMMONCONTROLSEX(ctypes.sizeof(INITCOMMONCONTROLSEX), 0x20)  # progress
    comctl32.InitCommonControlsEx(ctypes.byref(icc))

    instance = kernel32.GetModuleHandleW(None)
    wc = WNDCLASSW()
    wc.lpfnWndProc = wnd_proc
    wc.hInstance = instance
    wc.hbrBackground = 6  # COLOR_WINDOW + 1
    wc.lpszClassName = "CsgStarting"
    user32.RegisterClassW(ctypes.byref(wc))

    style = 0x00C00000 | 0x00080000 | 0x10000000  # CAPTION | SYSMENU | VISIBLE
    ex_style = 0x00000008 | 0x00040000  # TOPMOST | APPWINDOW
    rect = RECT(0, 0, 440, 140)
    user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, ex_style)
    width, height = rect.right - rect.left, rect.bottom - rect.top
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 2)

    hwnd = user32.CreateWindowExW(
        ex_style, "CsgStarting", _TITLE, style,
        x, y, width, height,
        0, 0, instance, None,
    )
    if not hwnd:
        return None

    user32.CreateWindowExW(
        0, "STATIC", _TEXT, 0x40000000 | 0x10000000,  # CHILD | VISIBLE
        16, 16, 408, 72,
        hwnd, 0, instance, None,
    )
    bar = user32.CreateWindowExW(
        0, "msctls_progress32", None, 0x40000000 | 0x10000000 | 0x08,  # + PBS_MARQUEE
        16, 100, 408, 18,
        hwnd, 0, instance, None,
    )
    if bar:
        user32.SendMessageW(bar, 0x040A, 1, 30)  # PBM_SETMARQUEE, on, 30 ms
    user32.ShowWindow(hwnd, 5)  # SW_SHOW
    user32.UpdateWindow(hwnd)
    return hwnd


def _message_loop() -> None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt_x", ctypes.c_long),
            ("pt_y", ctypes.c_long),
        ]

    msg = MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
