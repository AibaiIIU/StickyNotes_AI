import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta
import json
import math
import os
import re
import shutil
import socket
import ssl
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import urllib.error
import urllib.request

# ----------------- 零锁死单实例通信机制 -----------------
SINGLE_INSTANCE_PORT = 58763
server_socket = None
try:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
    server_socket.listen(1)
except OSError:
    try:
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.settimeout(1.5)
        client_sock.connect(("127.0.0.1", SINGLE_INSTANCE_PORT))
        client_sock.sendall(b"SHOW")
        client_sock.close()
    except Exception:
        pass
    sys.exit(0)

# 尝试导入托盘与图标渲染库
try:
    import pystray
    from PIL import Image, ImageDraw

    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False

# 尝试导入 Windows 系统声音模块
try:
    import winsound

    WINSOUND_AVAILABLE = True
except ImportError:
    WINSOUND_AVAILABLE = False

# 启用 Windows 逐屏幕 DPI 感知
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# 确保无论是以源码运行（如 src/square_notes.py），还是打包成 exe 运行，根目录都指向项目/程序物理文件夹
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    RESOURCE_DIR = getattr(sys, '_MEIPASS', BASE_DIR)
else:
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(_script_dir).lower() == "src":
        BASE_DIR = os.path.dirname(_script_dir)
    else:
        BASE_DIR = _script_dir
    RESOURCE_DIR = BASE_DIR

DATA_DIR = os.path.join(BASE_DIR, "notes_data")
DATA_FILE = os.path.join(DATA_DIR, "notes_state.json")

DEFAULT_API_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
DEFAULT_API_MODEL = "glm-4-flash"


def resolve_app_path(path):
    """将相对路径解析为运行期可用的真实路径，支持运行目录与内置资源目录"""
    if not path:
        return ""
    norm = str(path).replace("/", os.sep).replace("\\", os.sep)
    if os.path.isabs(norm):
        return norm
    for base in (BASE_DIR, RESOURCE_DIR, DATA_DIR):
        candidate = os.path.abspath(os.path.join(base, norm))
        if os.path.exists(candidate):
            return candidate
    return os.path.abspath(os.path.join(BASE_DIR, norm))


def to_relative_app_path(path):
    """若路径位于运行根目录或内置资源目录下，转换为可移植相对路径存储，避免写入本机绝对路径"""
    if not path:
        return ""
    norm = str(path).replace("/", os.sep).replace("\\", os.sep)
    if not os.path.isabs(norm):
        return str(path).replace("\\", "/")
    abs_path = os.path.abspath(norm)
    for base in (BASE_DIR, RESOURCE_DIR):
        abs_base = os.path.abspath(base)
        try:
            rel = os.path.relpath(abs_path, abs_base)
            if not rel.startswith("..") and not os.path.isabs(rel):
                return rel.replace("\\", "/")
        except ValueError:
            pass
    return abs_path


def get_app_icon_path():
    """获取应用程序图标路径，兼容源码运行与 PyInstaller _MEIPASS 解包目录"""
    return resolve_app_path(os.path.join("assets", "app.ico"))


def apply_window_icon(win):
    """为 Tkinter 窗口及其所有子弹窗设置默认应用图标"""
    try:
        ico_path = get_app_icon_path()
        if ico_path and os.path.exists(ico_path):
            win.iconbitmap(default=ico_path)
    except Exception:
        pass


def detect_system_lang():
    """检测 Windows 系统当前显示语言，非中文环境默认返回 'en'"""
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        if (lang_id & 0xFF) == 0x04:  # LANG_CHINESE
            return "zh"
    except Exception:
        pass
    try:
        import locale

        loc = locale.getdefaultlocale()[0]
        if loc and loc.lower().startswith("zh"):
            return "zh"
    except Exception:
        pass
    return "en"


I18N = {
    "zh": {
        "app_title": "便签主控制台",
        "task": "事项:",
        "time": "时间:",
        "btn_new": " + 新建 (N) ",
        "max_per_row": "每行最多:",
        "unit_notes": "个",
        "screen": "显示屏幕:",
        "btn_h": " 横排 (H) ",
        "btn_v": " 竖排 (V) ",
        "top_on": " 置顶:开 (T) ",
        "top_off": " 置顶:关 (T) ",
        "mode_box": " 模式:默认排列 (M) ",
        "mode_free": " 模式:自由排列 (M) ",
        "lock_on": " 穿透:开 (L) ",
        "lock_off": " 穿透:关 (L) ",
        "opacity": "透明:",
        "btn_sound": " 铃声设置 ",
        "btn_pref": " 偏好设置 ",
        "ai_memo": "AI 速记:",
        "btn_parse": " 智能拆解 (J) ",
        "btn_api": " API设置 ",
        "status_ready": "就绪",
        "status_parsing": "AI 思考拆解中...",
        "status_done": "处理完成",
        "status_failed": "拆解失败",
        "tip_double_click": "[双击时间可修改]",
        "tip_pending": "[待定事项-双击设时间]",
        "tip_fuzzy": "[待定日程-双击改时间]",
        "tip_expired": "[已到期-双击改时间]",
        "tip_due_soon": "[即将截止-双击改时间]",
        "pending_label": "待定",
        "fuzzy_default": "待定日程",
        "unit_d": "天",
        "unit_h": "时",
        "unit_m": "分",
        "unit_s": "秒",
        "toast_warn_title": "⏳ 临期提醒 · 剩 5 分钟",
        "toast_warn_msg": "事项【{task}】即将截止！请注意时间。",
        "toast_due_title": "🚨 到期提醒 · 时间已截止",
        "toast_due_msg": "事项【{task}】已到期！",
        "tray_toggle_console": "显示 / 隐藏控制台",
        "tray_new_note": "新建待办便签",
        "tray_toggle_notes": "显示 / 隐藏所有便签",
        "tray_toggle_lock": "切换鼠标穿透",
        "tray_toggle_layout": "切换排版方向 (横排/竖排)",
        "tray_sound": "🔔 铃声设置",
        "tray_api": "⚙️ API设置",
        "tray_pref": "🛠️ 偏好设置",
        "tray_exit": "彻底退出软件",
        "pref_title": "系统偏好设置",
        "pref_lang_frame": " 界面语言选择 (Language) ",
        "pref_lang_auto": "跟随操作系统 (Auto)",
        "pref_lang_zh": "简体中文",
        "pref_lang_en": "English",
        "pref_close_frame": " 主控制台关闭按钮 [×] 行为 ",
        "pref_close_tray": "最小化至系统托盘小图标 (默认，不退出)",
        "pref_close_exit": "直接彻底退出应用程序",
        "pref_save": "保存偏好设置",
        "pref_cancel": "取消",
        "pref_saved_tip": "偏好设置已成功保存并立即生效！",
    },
    "en": {
        "app_title": "Sticky Notes Console",
        "task": "Task:",
        "time": "Time:",
        "btn_new": " + New (N) ",
        "max_per_row": "Max/Row:",
        "unit_notes": "cards",
        "screen": "Screen:",
        "btn_h": " Horizontal (H) ",
        "btn_v": " Vertical (V) ",
        "top_on": " Topmost:On (T) ",
        "top_off": " Topmost:Off (T) ",
        "mode_box": " Mode:Grid (M) ",
        "mode_free": " Mode:Free (M) ",
        "lock_on": " Click-Thru:On (L) ",
        "lock_off": " Click-Thru:Off (L) ",
        "opacity": "Opacity:",
        "btn_sound": " Ringtone ",
        "btn_pref": " Settings ",
        "ai_memo": "AI Memo:",
        "btn_parse": " Parse (J) ",
        "btn_api": " API Config ",
        "status_ready": "Ready",
        "status_parsing": "AI Parsing...",
        "status_done": "Completed",
        "status_failed": "Failed",
        "tip_double_click": "[Double-click to edit]",
        "tip_pending": "[Pending · Double-click]",
        "tip_fuzzy": "[Schedule · Double-click]",
        "tip_expired": "[Expired · Double-click]",
        "tip_due_soon": "[Due Soon · Double-click]",
        "pending_label": "Pending",
        "fuzzy_default": "Schedule",
        "unit_d": "d",
        "unit_h": "h",
        "unit_m": "m",
        "unit_s": "s",
        "toast_warn_title": "⏳ Reminder · 5 Min Left",
        "toast_warn_msg": "Task [{task}] is due soon! Check your schedule.",
        "toast_due_title": "🚨 Time's Up · Task Expired",
        "toast_due_msg": "Task [{task}] has expired!",
        "tray_toggle_console": "Show / Hide Console",
        "tray_new_note": "New Sticky Note",
        "tray_toggle_notes": "Show / Hide All Notes",
        "tray_toggle_lock": "Toggle Click-Through",
        "tray_toggle_layout": "Toggle Layout (H/V)",
        "tray_sound": "🔔 Ringtone Settings",
        "tray_api": "⚙️ AI API Config",
        "tray_pref": "🛠️ Preferences",
        "tray_exit": "Exit Application",
        "pref_title": "Preferences",
        "pref_lang_frame": " Interface Language ",
        "pref_lang_auto": "Follow System (Auto)",
        "pref_lang_zh": "Simplified Chinese",
        "pref_lang_en": "English",
        "pref_close_frame": " Main Window [×] Close Button Action ",
        "pref_close_tray": "Minimize to system tray (Default, keep running)",
        "pref_close_exit": "Exit application completely",
        "pref_save": "Save Preferences",
        "pref_cancel": "Cancel",
        "pref_saved_tip": "Preferences saved and applied immediately!",
    },
}


def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR)
        except Exception:
            pass


def get_short_path(path):
    try:
        buf = ctypes.create_unicode_buffer(512)
        res = ctypes.windll.kernel32.GetShortPathNameW(path, buf, 512)
        if res > 0 and buf.value:
            return buf.value
    except Exception:
        pass
    return path


def mci_send(command):
    try:
        buf = ctypes.create_unicode_buffer(256)
        err = ctypes.windll.winmm.mciSendStringW(command, buf, 255, 0)
        return err, buf.value
    except Exception as e:
        return -1, str(e)


def mci_open_audio(filepath, alias):
    mci_send(f"stop {alias}")
    mci_send(f"close {alias}")
    short_p = get_short_path(filepath)
    err, _ = mci_send(f'open "{short_p}" type mpegvideo alias {alias}')
    if err != 0:
        err, _ = mci_send(f'open "{short_p}" alias {alias}')
    if err == 0:
        mci_send(f"set {alias} time format milliseconds")
    return err == 0


def auto_fit_window(win, min_w=400, min_h=100, pad_w=24, pad_h=16, center_on=None, default_mon=None):
    win.update_idletasks()
    req_w = max(min_w, win.winfo_reqwidth() + pad_w)
    req_h = max(min_h, win.winfo_reqheight() + pad_h)

    if center_on is not None:
        try:
            state = getattr(center_on, "state", lambda: "normal")()
            if state == "normal" and center_on.winfo_viewable():
                cx = center_on.winfo_x() + (center_on.winfo_width() - req_w) // 2
                cy = center_on.winfo_y() + (center_on.winfo_height() - req_h) // 2
                win.geometry(f"{req_w}x{req_h}+{max(10, cx)}+{max(10, cy)}")
                return
        except Exception:
            pass

    if default_mon:
        cx = default_mon["left"] + (default_mon["width"] - req_w) // 2
        cy = default_mon["top"] + (default_mon["height"] - req_h) // 2
        win.geometry(f"{req_w}x{req_h}+{max(10, cx)}+{max(10, cy)}")
    else:
        win.geometry(f"{req_w}x{req_h}")


def get_screen_monitors():
    monitors = []
    try:

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class MONITORINFOEX(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
                ("szDevice", wintypes.WCHAR * 32),
            ]

        def enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
            info = MONITORINFOEX()
            info.cbSize = ctypes.sizeof(MONITORINFOEX)
            if ctypes.windll.user32.GetMonitorInfoW(
                hMonitor, ctypes.byref(info)
            ):
                r = info.rcWork
                monitors.append(
                    {
                        "left": r.left,
                        "top": r.top,
                        "right": r.right,
                        "bottom": r.bottom,
                        "width": r.right - r.left,
                        "height": r.bottom - r.top,
                        "is_primary": bool(info.dwFlags & 1),
                    }
                )
            return True

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            getattr(wintypes, "HMONITOR", wintypes.HANDLE),
            getattr(wintypes, "HDC", wintypes.HANDLE),
            ctypes.POINTER(RECT),
            wintypes.LPARAM,
        )
        ctypes.windll.user32.EnumDisplayMonitors(
            None, None, MonitorEnumProc(enum_proc), 0
        )
    except Exception:
        pass

    if not monitors:
        w = ctypes.windll.user32.GetSystemMetrics(0)
        h = ctypes.windll.user32.GetSystemMetrics(1)
        monitors.append(
            {
                "left": 0,
                "top": 0,
                "right": w,
                "bottom": h,
                "width": w,
                "height": h,
                "is_primary": True,
            }
        )
    return monitors


def set_window_mouse_transparent(win, enable=True, alpha=1.0):
    try:
        win.update_idletasks()
        hwnd = win.winfo_id()
        root_hwnd = ctypes.windll.user32.GetAncestor(hwnd, 2)
        target_hwnd = root_hwnd if root_hwnd else hwnd

        GWL_EXSTYLE = -20
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_LAYERED = 0x00080000
        LWA_ALPHA = 0x00000002

        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_FRAMECHANGED = 0x0020

        style = ctypes.windll.user32.GetWindowLongW(target_hwnd, GWL_EXSTYLE)
        alpha_byte = int(max(0.1, min(1.0, alpha)) * 255)

        if enable:
            ctypes.windll.user32.SetWindowLongW(
                target_hwnd,
                GWL_EXSTYLE,
                style | WS_EX_TRANSPARENT | WS_EX_LAYERED,
            )
            ctypes.windll.user32.SetLayeredWindowAttributes(
                target_hwnd, 0, alpha_byte, LWA_ALPHA
            )
        else:
            new_style = style & ~WS_EX_TRANSPARENT
            if alpha >= 1.0:
                new_style &= ~WS_EX_LAYERED
            ctypes.windll.user32.SetWindowLongW(
                target_hwnd, GWL_EXSTYLE, new_style
            )
            if alpha < 1.0:
                ctypes.windll.user32.SetLayeredWindowAttributes(
                    target_hwnd, 0, alpha_byte, LWA_ALPHA
                )

        ctypes.windll.user32.SetWindowPos(
            target_hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
        )
    except Exception:
        pass


def add_context_menu(widget, lang="zh"):
    menu = tk.Menu(widget, tearoff=0)
    cut_lbl = "Cut" if lang == "en" else "剪切"
    copy_lbl = "Copy" if lang == "en" else "复制"
    paste_lbl = "Paste" if lang == "en" else "粘贴"
    sel_lbl = "Select All" if lang == "en" else "全选"

    menu.add_command(
        label=cut_lbl, command=lambda: widget.event_generate("<<Cut>>")
    )
    menu.add_command(
        label=copy_lbl, command=lambda: widget.event_generate("<<Copy>>")
    )
    menu.add_command(
        label=paste_lbl, command=lambda: widget.event_generate("<<Paste>>")
    )
    menu.add_separator()
    menu.add_command(
        label=sel_lbl,
        command=lambda: (widget.select_range(0, tk.END), widget.icursor(tk.END)),
    )

    def show_menu(event):
        widget.focus_set()
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    widget.bind("<Button-3>", show_menu)


def convert_cn_numbers(text):
    text = str(text)
    text = re.sub(r"一个半\s*(小时|时|h)", "1.5小时", text)
    text = re.sub(r"两个半\s*(小时|时|h)", "2.5小时", text)
    text = re.sub(r"半个?\s*(小时|时|h)", "30分钟", text)
    text = re.sub(r"一刻钟", "15分钟", text)
    text = re.sub(r"半\s*(天|日)", "0.5天", text)

    cn_map = {
        "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
        "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    }

    def _replace_match(m):
        s = m.group(1)
        unit = m.group(2)
        if s == "十":
            val = 10
        elif s.startswith("十"):
            val = 10 + cn_map.get(s[1:], 0)
        elif s.endswith("十"):
            val = cn_map.get(s[0], 1) * 10
        elif "十" in s:
            parts = s.split("十")
            val = cn_map.get(parts[0], 1) * 10 + cn_map.get(parts[1], 0)
        else:
            val = cn_map.get(s, s)
        return f"{val}{unit}"

    return re.sub(
        r"([一二两三四五六七八九十]+)\s*(个?\s*(?:天|日|小时|时|分钟|分|秒))",
        _replace_match,
        text,
    )


def parse_time_input(text):
    text = convert_cn_numbers(text).strip().lower()
    total_seconds = 0.0
    days = re.findall(r"(\d+(?:\.\d+)?)\s*(?:d|days?|个?天|日)", text)
    hours = re.findall(r"(\d+(?:\.\d+)?)\s*(?:h|hours?|hrs?|个?小时|时)", text)
    mins = re.findall(
        r"(\d+(?:\.\d+)?)\s*(?:m|mins?|minutes?|个?分钟|分)(?!s)", text
    )
    secs = re.findall(r"(\d+(?:\.\d+)?)\s*(?:s|secs?|seconds?|秒)", text)

    if days or hours or mins or secs:
        if days:
            total_seconds += sum(float(x) for x in days) * 86400
        if hours:
            total_seconds += sum(float(x) for x in hours) * 3600
        if mins:
            total_seconds += sum(float(x) for x in mins) * 60
        if secs:
            total_seconds += sum(float(x) for x in secs)
        return max(1, int(round(total_seconds)))

    try:
        return max(1, int(round(float(text) * 60)))
    except ValueError:
        return 900


def parse_delta_seconds(text):
    text = convert_cn_numbers(text).strip().lower()
    sign = -1 if text.startswith("-") else 1
    clean_text = text.lstrip("+-")
    secs = parse_time_input(clean_text)
    return sign * secs


def extract_clause_for_task(task, raw_text):
    clauses = [
        c.strip() for c in re.split(r"[，,。；;！!\n]+", str(raw_text)) if c.strip()
    ]
    core_chars = [c for c in task if c not in "的了去把在到给上"]
    best_clause = ""
    best_score = 0
    for cl in clauses:
        if task in cl:
            return cl
        score = sum(1 for c in core_chars if c in cl)
        if score > best_score and score >= min(1, len(core_chars)):
            best_score = score
            best_clause = cl
    return best_clause


def parse_fuzzy_date_anchor(label):
    label = str(label).strip()
    today = datetime.now().date()
    period = ""
    for p in [
        "早上", "早晨", "上午", "中午", "下午", "傍晚", "晚上", "夜间", "深夜",
        "morning", "afternoon", "evening", "night",
    ]:
        if p in label.lower():
            period = p
            break

    offset_days = None
    l_lower = label.lower()
    if "大后天" in label or "in 3 days" in l_lower:
        offset_days = 3
    elif "后天" in label or "day after tomorrow" in l_lower or "in 2 days" in l_lower:
        offset_days = 2
    elif "明天" in label or "明日" in label or "tomorrow" in l_lower:
        offset_days = 1
    elif "今天" in label or "今日" in label or "today" in l_lower:
        offset_days = 0
    elif "昨天" in label or "昨日" in label or "yesterday" in l_lower:
        offset_days = -1
    else:
        m_days = re.search(r"(\d+)\s*(?:天后|days?\s*later)", convert_cn_numbers(label))
        if m_days:
            offset_days = int(m_days.group(1))
        else:
            wk_map = {
                "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6,
                "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
            }
            m_next = re.search(r"下周([一二三四五六日天])", label) or re.search(
                r"next\s*(mon|tue|wed|thu|fri|sat|sun)", l_lower
            )
            m_this = re.search(r"(?:本周|周|星期)([一二三四五六日天])", label) or re.search(
                r"(?:this\s*)?(mon|tue|wed|thu|fri|sat|sun)", l_lower
            )
            if m_next:
                target_wk = wk_map[m_next.group(1)[:3]]
                offset_days = (7 - today.weekday()) + target_wk
            elif m_this:
                target_wk = wk_map[m_this.group(1)[:3]]
                diff = target_wk - today.weekday()
                offset_days = diff if diff >= 0 else diff + 7

    if offset_days is not None:
        target_date = (today + timedelta(days=offset_days)).strftime("%Y-%m-%d")
        return target_date, period
    return "", period


def compute_dynamic_fuzzy_label(fuzzy_target_date, fuzzy_period, fallback_label, lang="zh"):
    if not fuzzy_target_date:
        return fallback_label or ("Schedule" if lang == "en" else "待定日程")
    try:
        today = datetime.now().date()
        tgt = datetime.strptime(fuzzy_target_date, "%Y-%m-%d").date()
        diff = (tgt - today).days
        p = fuzzy_period or ""
        p_en = f" {p.title()}" if p else ""

        if lang == "en":
            if diff == 3:
                return f"In 3 days{p_en}"
            elif diff == 2:
                return f"In 2 days{p_en}"
            elif diff == 1:
                return f"Tomorrow{p_en}"
            elif diff == 0:
                return f"Today{p_en}"
            elif diff == -1:
                return f"Yesterday{p_en}"
            elif diff < -1:
                return f"Expired ({-diff}d)"
            else:
                return f"In {diff} days{p_en}"
        else:
            if diff == 3:
                return f"大后天{p}"
            elif diff == 2:
                return f"后天{p}"
            elif diff == 1:
                return f"明天{p}"
            elif diff == 0:
                return f"今天{p}"
            elif diff == -1:
                return f"昨天{p}(已过)"
            elif diff < -1:
                return f"已过期{-diff}天"
            else:
                return f"{diff}天后{p}"
    except Exception:
        return fallback_label or ("Schedule" if lang == "en" else "待定日程")


def get_fuzzy_rank_seconds(label, fuzzy_target_date="", fuzzy_period=""):
    period_sec = 3600 * 12
    p_str = (fuzzy_period or str(label)).lower()
    if any(k in p_str for k in ["早", "上午", "morning"]):
        period_sec = 3600 * 9
    elif any(k in p_str for k in ["中午", "noon"]):
        period_sec = 3600 * 12
    elif any(k in p_str for k in ["下午", "afternoon"]):
        period_sec = 3600 * 15
    elif any(k in p_str for k in ["晚", "夜", "evening", "night"]):
        period_sec = 3600 * 20

    if fuzzy_target_date:
        try:
            today = datetime.now().date()
            tgt = datetime.strptime(fuzzy_target_date, "%Y-%m-%d").date()
            diff = (tgt - today).days
            return diff * 86400 + period_sec
        except Exception:
            pass

    label = str(label)
    if "大后天" in label or "3 days" in label.lower():
        return 86400 * 3 + period_sec
    elif "后天" in label or "2 days" in label.lower() or "after tomorrow" in label.lower():
        return 86400 * 2 + period_sec
    elif "明天" in label or "tomorrow" in label.lower():
        return 86400 * 1 + period_sec
    elif "今天" in label or "today" in label.lower():
        return period_sec
    return 86400 * 2


def create_tray_image():
    try:
        ico_path = get_app_icon_path()
        if ico_path and os.path.exists(ico_path):
            with Image.open(ico_path) as im:
                return im.convert("RGBA").resize((64, 64), Image.LANCZOS)
    except Exception:
        pass

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [4, 4, 60, 60], radius=12, fill="#FBC02D", outline="#F57F17", width=3
    )
    draw.line([16, 20, 48, 20], fill="#3E2723", width=4)
    draw.line([16, 32, 48, 32], fill="#3E2723", width=4)
    draw.line([16, 44, 38, 44], fill="#3E2723", width=4)
    return img


class ToastNotification:

    def __init__(self, manager, title, message, level="warning"):
        self.manager = manager
        self.level = level
        self.width = 330
        self.height = 90
        self._is_closed = False
        self._timer_id = None

        self.win = tk.Toplevel(self.manager.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)

        if level == "due":
            self.bar_color = "#E53935"
            self.bg_color = "#FFEBEE"
            self.title_fg = "white"
            self.msg_fg = "#C62828"
        else:
            self.bar_color = "#FFA000"
            self.bg_color = "#FFF8E1"
            self.title_fg = "white"
            self.msg_fg = "#E65100"

        self._build_ui(title, message)
        self.reposition(0)

        self.manager.current_sound_toast = self
        self.manager.play_alert_sound(level=level)

        self._timer_id = self.win.after(10000, lambda: self.close(manual=False))

    def _build_ui(self, title, message):
        main_frame = tk.Frame(self.win, bg=self.bg_color, bd=1, relief=tk.SOLID)
        main_frame.pack(fill=tk.BOTH, expand=True)

        top_bar = tk.Frame(main_frame, bg=self.bar_color, height=26)
        top_bar.pack(fill=tk.X, side=tk.TOP)
        top_bar.pack_propagate(False)

        lbl_title = tk.Label(
            top_bar,
            text=title,
            bg=self.bar_color,
            fg=self.title_fg,
            font=("Microsoft YaHei", 9, "bold"),
        )
        lbl_title.pack(side=tk.LEFT, padx=8)

        btn_close = tk.Button(
            top_bar,
            text="×",
            command=lambda: self.close(manual=True),
            bg=self.bar_color,
            fg=self.title_fg,
            bd=0,
            font=("Arial", 10, "bold"),
            activebackground=self.bar_color,
            activeforeground="black",
            cursor="hand2",
        )
        btn_close.pack(side=tk.RIGHT, padx=4)

        lbl_msg = tk.Label(
            main_frame,
            text=message,
            bg=self.bg_color,
            fg=self.msg_fg,
            font=("Microsoft YaHei", 9, "bold"),
            wraplength=300,
            justify=tk.LEFT,
        )
        lbl_msg.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        for w in (main_frame, top_bar, lbl_title, lbl_msg):
            w.bind("<Button-1>", lambda e: self.close(manual=True))

    def reposition(self, stack_index):
        mon = self.manager.monitors[0]
        x = mon["right"] - self.width - 20
        y = mon["bottom"] - self.height - 20 - stack_index * (self.height + 10)
        self.win.geometry(f"{self.width}x{self.height}+{x}+{y}")

    def close(self, manual=True):
        if self._is_closed:
            return
        self._is_closed = True

        if self._timer_id is not None:
            try:
                self.win.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None

        try:
            self.win.destroy()
        except Exception:
            pass

        self.manager.remove_toast(self)

        if (
            manual
            or self.manager.current_sound_toast == self
            or not self.manager.active_toasts
        ):
            self.manager.stop_alert_sound()


class StickyNoteWindow:

    def __init__(
        self,
        manager,
        task_text,
        total_seconds,
        note_id,
        target_timestamp=None,
        init_pos=None,
        is_fuzzy=False,
        fuzzy_label="",
        fuzzy_target_date="",
        fuzzy_period="",
        is_pending=False,
        warned_5m=False,
        warned_due=False,
    ):
        self.manager = manager
        self.note_id = note_id
        self.size = 175
        self.rank_num = 1
        self.is_fuzzy = is_fuzzy
        self.fuzzy_label = fuzzy_label
        self.fuzzy_target_date = fuzzy_target_date
        self.fuzzy_period = fuzzy_period
        self.is_pending = is_pending

        if self.is_fuzzy:
            if not self.fuzzy_target_date and self.fuzzy_label:
                t_date, t_period = parse_fuzzy_date_anchor(self.fuzzy_label)
                self.fuzzy_target_date = t_date
                self.fuzzy_period = t_period
            self.refresh_fuzzy_by_date()

        now = time.time()
        if not self.is_fuzzy and not self.is_pending:
            if target_timestamp and target_timestamp > now:
                self.target_timestamp = target_timestamp
                self.remaining_seconds = int(math.ceil(target_timestamp - now))
            else:
                self.remaining_seconds = max(0, int(total_seconds))
                self.target_timestamp = now + self.remaining_seconds
        else:
            self.target_timestamp = now + total_seconds

        self.warned_5m = warned_5m
        self.warned_due = warned_due

        self.win = tk.Toplevel(self.manager.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", self.manager.is_topmost)
        self.win.attributes("-alpha", self.manager.alpha)

        init_x = init_pos[0] if init_pos else 100
        init_y = init_pos[1] if init_pos else 100
        self.win.geometry(f"{self.size}x{self.size}+{init_x}+{init_y}")

        self.single_drag_start_x = 0
        self.single_drag_start_y = 0

        self._build_ui(task_text)
        self._update_color()
        self.win.update_idletasks()

    def set_fuzzy_schedule(self, label_text):
        self.is_pending = False
        self.is_fuzzy = True
        self.fuzzy_label = label_text.strip()
        t_date, t_period = parse_fuzzy_date_anchor(self.fuzzy_label)
        self.fuzzy_target_date = t_date
        self.fuzzy_period = t_period
        self.refresh_fuzzy_by_date()
        self.warned_5m = True
        self.warned_due = True

    def shift_fuzzy_days(self, delta_days):
        self.is_pending = False
        self.is_fuzzy = True
        if not self.fuzzy_target_date:
            t_date, t_period = parse_fuzzy_date_anchor(self.fuzzy_label)
            self.fuzzy_target_date = t_date
            if t_period:
                self.fuzzy_period = t_period

        if self.fuzzy_target_date:
            try:
                dt = datetime.strptime(self.fuzzy_target_date, "%Y-%m-%d").date()
                new_dt = dt + timedelta(days=int(delta_days))
                self.fuzzy_target_date = new_dt.strftime("%Y-%m-%d")
            except Exception:
                pass

        self.refresh_fuzzy_by_date()
        self.warned_5m = True
        self.warned_due = True

    def refresh_fuzzy_by_date(self):
        if not self.is_fuzzy:
            return
        new_label = compute_dynamic_fuzzy_label(
            self.fuzzy_target_date,
            self.fuzzy_period,
            self.fuzzy_label,
            lang=self.manager.active_lang,
        )
        self.fuzzy_label = new_label
        self.remaining_seconds = get_fuzzy_rank_seconds(
            self.fuzzy_label, self.fuzzy_target_date, self.fuzzy_period
        )

    def _build_ui(self, task_text):
        self.main_frame = tk.Frame(
            self.win, bg="#FFF9C4", bd=1, relief=tk.SOLID
        )
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.top_bar = tk.Frame(self.main_frame, bg="#FBC02D", height=22)
        self.top_bar.pack(fill=tk.X, side=tk.TOP)
        self.top_bar.pack_propagate(False)

        self.rank_label = tk.Label(
            self.top_bar,
            text="#1",
            bg="#FBC02D",
            fg="#333333",
            font=("Microsoft YaHei", 8, "bold"),
        )
        self.rank_label.pack(side=tk.LEFT, padx=6)

        self.close_btn = tk.Button(
            self.top_bar,
            text="×",
            command=self.close_note,
            bg="#FBC02D",
            fg="#333333",
            bd=0,
            font=("Arial", 11, "bold"),
            activebackground="#E53935",
            activeforeground="white",
            cursor="hand2",
        )
        self.close_btn.pack(side=tk.RIGHT, ipadx=4)

        for widget in (self.top_bar, self.rank_label):
            widget.bind("<ButtonPress-1>", self._on_drag_start)
            widget.bind("<B1-Motion>", self._on_drag_motion)

        self.task_entry = tk.Entry(
            self.main_frame,
            bg="#FFF9C4",
            fg="#212121",
            font=("Microsoft YaHei", 11, "bold"),
            bd=0,
            justify=tk.CENTER,
        )
        self.task_entry.insert(0, task_text)
        self.task_entry.pack(fill=tk.X, side=tk.TOP, pady=(12, 0), padx=8)
        self.task_entry.bind(
            "<KeyRelease>", lambda e: self.manager.save_state()
        )
        add_context_menu(self.task_entry, lang=self.manager.active_lang)

        self.tip_label = tk.Label(
            self.main_frame,
            text=self.manager.t("tip_double_click"),
            bg="#FFF9C4",
            fg="#757575",
            font=("Microsoft YaHei", 7),
        )
        self.tip_label.pack(side=tk.BOTTOM, pady=6)

        init_time_str = self._format_time()
        self.time_label = tk.Label(
            self.main_frame,
            text=init_time_str,
            bg="#FFF9C4",
            fg="#111111",
            font=self._get_time_font(init_time_str),
            cursor="hand2",
        )
        self.time_label.pack(expand=True)
        self.time_label.bind("<Double-Button-1>", self.prompt_edit_time)

    def _get_time_font(self, text_str):
        length = len(str(text_str))
        if length >= 11:
            return ("Microsoft YaHei", 13, "bold")
        if length >= 8:
            return ("Microsoft YaHei", 15, "bold")
        return ("Microsoft YaHei", 18, "bold")

    def _refresh_time_label(self):
        txt = self._format_time()
        self.time_label.configure(text=txt, font=self._get_time_font(txt))

    def _format_time(self):
        if self.is_pending:
            return self.manager.t("pending_label")
        if self.is_fuzzy:
            clean_label = self.fuzzy_label.strip()
            if (
                not clean_label
                or "unspecified" in clean_label.lower()
                or "none" in clean_label.lower()
            ):
                return self.manager.t("fuzzy_default")
            return clean_label

        secs = max(0, int(self.remaining_seconds))
        days = secs // 86400
        hours = (secs % 86400) // 3600
        minutes = (secs % 3600) // 60
        seconds = secs % 60

        u_d = self.manager.t("unit_d")
        u_h = self.manager.t("unit_h")
        u_m = self.manager.t("unit_m")
        u_s = self.manager.t("unit_s")

        if days >= 1:
            return (
                f"{days}{u_d} {hours:02d}{u_h}" if hours > 0 else f"{days} {u_d}"
            )
        if hours >= 1:
            return f"{hours:02d}{u_h} {minutes:02d}{u_m}"
        return f"{minutes:02d}{u_m} {seconds:02d}{u_s}"

    def prompt_edit_time(self, event=None):
        if self.manager.is_locked:
            return
        self.manager.open_custom_edit_dialog(self)

    def _update_color(self):
        if self.is_pending:
            bg_color, bar_color = "#FFEBEE", "#E53935"
            tip_text = self.manager.t("tip_pending")
            time_fg = "#C62828"
            top_fg = "white"
        elif self.is_fuzzy:
            bg_color, bar_color = "#E1F5FE", "#64B5F6"
            tip_text = self.manager.t("tip_fuzzy")
            time_fg = "#0277BD"
            top_fg = "#212121"
        elif self.remaining_seconds == 0:
            bg_color, bar_color = "#FFCDD2", "#E57373"
            tip_text = self.manager.t("tip_expired")
            time_fg = "#B71C1C"
            top_fg = "#212121"
        elif self.remaining_seconds <= 300:
            bg_color, bar_color = "#FFE0B2", "#FFB74D"
            tip_text = self.manager.t("tip_due_soon")
            time_fg = "#E65100"
            top_fg = "#212121"
        else:
            bg_color, bar_color = "#FFF9C4", "#FBC02D"
            tip_text = self.manager.t("tip_double_click")
            time_fg = "#111111"
            top_fg = "#333333"

        self.tip_label.configure(text=tip_text)
        txt_now = self._format_time()
        self.time_label.configure(text=txt_now, font=self._get_time_font(txt_now))
        for w in (
            self.main_frame,
            self.task_entry,
            self.time_label,
            self.tip_label,
        ):
            w.configure(bg=bg_color)
        self.time_label.configure(fg=time_fg)

        for w in (self.top_bar, self.rank_label, self.close_btn):
            w.configure(bg=bar_color)
        self.rank_label.configure(fg=top_fg)
        self.close_btn.configure(fg=top_fg)

    def tick(self):
        if self.is_pending:
            return

        if self.is_fuzzy:
            old_label = self.fuzzy_label
            self.refresh_fuzzy_by_date()
            if self.fuzzy_label != old_label:
                self.time_label.configure(text=self._format_time())
            return

        now = time.time()
        self.remaining_seconds = max(0, int(math.ceil(self.target_timestamp - now)))
        self.time_label.configure(text=self._format_time())
        self._update_color()

        if 0 < self.remaining_seconds <= 300:
            if not self.warned_5m:
                self.warned_5m = True
                self.manager.trigger_reminder(self, reminder_type="5min")
                self.manager.save_state()

        elif self.remaining_seconds == 0:
            if not self.warned_due:
                self.warned_due = True
                self.manager.trigger_reminder(self, reminder_type="due")
                self.manager.save_state()

    def _on_drag_start(self, event):
        if self.manager.is_locked:
            return
        if self.manager.drag_mode == "box":
            self.manager.start_box_drag(event.x_root, event.y_root)
        else:
            self.single_drag_start_x = event.x
            self.single_drag_start_y = event.y

    def _on_drag_motion(self, event):
        if self.manager.is_locked:
            return
        if self.manager.drag_mode == "box":
            self.manager.update_box_drag(event.x_root, event.y_root)
        else:
            x = self.win.winfo_x() + (event.x - self.single_drag_start_x)
            y = self.win.winfo_y() + (event.y - self.single_drag_start_y)
            self.win.geometry(f"+{x}+{y}")
            self.manager.save_state()

    def move_to(self, x, y, rank_index):
        self.rank_num = rank_index
        self.win.geometry(f"{self.size}x{self.size}+{x}+{y}")
        self.update_rank_label()

    def update_rank_label(self):
        lock_icon = "🔒 " if self.manager.is_locked else ""
        if self.is_pending:
            type_icon = "📌 "
        elif self.is_fuzzy:
            type_icon = "🗓️ "
        else:
            type_icon = ""
        self.rank_label.configure(text=f"{lock_icon}{type_icon}#{self.rank_num}")

    def set_topmost(self, is_topmost):
        self.win.attributes("-topmost", is_topmost)

    def set_alpha(self, alpha):
        self.win.attributes("-alpha", alpha)
        if self.manager.is_locked:
            set_window_mouse_transparent(self.win, enable=True, alpha=alpha)

    def set_clickthrough(self, lock):
        if lock:
            self.task_entry.configure(state="readonly", cursor="arrow")
            self.time_label.configure(cursor="arrow")
        else:
            self.task_entry.configure(state="normal", cursor="xterm")
            self.time_label.configure(cursor="hand2")

        set_window_mouse_transparent(
            self.win, enable=lock, alpha=self.manager.alpha
        )
        self.update_rank_label()

    def close_note(self):
        if self.manager.is_locked:
            return
        self.manager.remove_note(self)
        try:
            self.win.destroy()
        except Exception:
            pass


class NoteManager:

    def __init__(self, root):
        self.root = root
        ensure_data_dir()
        self.monitors = get_screen_monitors()
        self.current_screen_idx = 0

        self.notes = []
        self.next_id = 1
        self.last_order = []
        self.layout_mode = "horizontal"
        self.is_topmost = True
        self.drag_mode = "box"
        self.is_locked = False
        self.alpha = 1.0

        # 系统偏好设置（多语言适配 + 关闭按钮行为）
        self.pref_language = "auto"
        self.close_action = "tray"  # "tray" (默认最小化至托盘) 或 "exit" (直接退出)
        self.active_lang = "zh"
        self._is_withdrawing = False

        self.api_key = ""
        self.api_endpoint = DEFAULT_API_ENDPOINT
        self.api_model = DEFAULT_API_MODEL

        self.sound_mode = "default"
        self.custom_audio_path = ""
        self.custom_start_ms = 0
        self.custom_end_ms = 10000
        self._sound_seq_id = 0
        self.current_sound_toast = None

        self.active_toasts = []
        self.all_notes_hidden = False

        cur_m = self.monitors[0]
        self.anchor_x = cur_m["left"] + 50
        self.anchor_y = cur_m["top"] + 160

        self.drag_origin_mouse_x = 0
        self.drag_origin_mouse_y = 0
        self.drag_origin_anchor_x = self.anchor_x
        self.drag_origin_anchor_y = self.anchor_y

        # 1. 仅加载基础配置
        self.load_settings_only()
        self.update_active_lang()

        self.root.title(self.t("app_title"))
        apply_window_icon(self.root)
        self.root.attributes("-topmost", self.is_topmost)
        self.root.resizable(True, False)

        # 2. 构建控制栏并自动计算主窗口适配宽度
        self.control_frame = None
        self._build_control_bar(init_pos=True)
        self._bind_shortcuts()

        # 3. 绑定关闭按钮与最小化按钮行为
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_clicked)
        self.root.bind("<Unmap>", self._on_root_unmap)

        # 4. 启动系统托盘与本地单实例监听
        self.tray_icon = None
        self._init_system_tray()
        self._start_socket_listener()

        # 5. 单次载入便签卡片
        if not os.path.exists(DATA_FILE):
            self._create_initial_demos()
        else:
            self.load_saved_notes_only()

        self._schedule_tick()

    def _fit_main_console(self, init_pos=False):
        """核心修复：根据当前语言内部容器 control_frame 的真实渲染宽度动态撑开主窗口，杜绝切换英文后按钮截断"""
        self.root.update_idletasks()
        cf_w = (
            self.control_frame.winfo_reqwidth()
            if self.control_frame
            else self.root.winfo_reqwidth()
        )
        cf_h = (
            self.control_frame.winfo_reqheight()
            if self.control_frame
            else self.root.winfo_reqheight()
        )
        req_w = max(920, cf_w + 24)
        req_h = max(125, cf_h + 10)
        if not init_pos:
            try:
                cur_x = self.root.winfo_x()
                cur_y = self.root.winfo_y()
                if cur_x > -10000 and cur_y > -10000:
                    self.root.geometry(
                        f"{req_w}x{req_h}+{max(0, cur_x)}+{max(0, cur_y)}"
                    )
                    return
            except Exception:
                pass
        self.root.geometry(f"{req_w}x{req_h}+60+25")

    def update_active_lang(self):
        if self.pref_language == "auto":
            self.active_lang = detect_system_lang()
        else:
            self.active_lang = (
                self.pref_language if self.pref_language in ["zh", "en"] else "zh"
            )

    def t(self, key):
        return I18N.get(self.active_lang, I18N["zh"]).get(key, key)

    def _safe_withdraw(self):
        try:
            self.root.withdraw()
        finally:
            self._is_withdrawing = False

    def _on_root_unmap(self, event):
        if event.widget is self.root and not self._is_withdrawing:
            if self.root.state() == "iconic":
                self._is_withdrawing = True
                self.root.after(40, self._safe_withdraw)

    def on_close_clicked(self):
        if self.close_action == "tray":
            self._safe_withdraw()
        else:
            self.on_app_exit()

    def show_console_properly(self):
        self._is_withdrawing = False
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.attributes("-topmost", self.is_topmost)
        self.root.focus_force()

    def _start_socket_listener(self):
        if server_socket is None:
            return

        def _listen():
            while True:
                try:
                    conn, _ = server_socket.accept()
                    data = conn.recv(16)
                    if data == b"SHOW":
                        self.root.after(0, self.show_console_properly)
                    conn.close()
                except Exception:
                    break

        threading.Thread(target=_listen, daemon=True).start()

    def _init_system_tray(self):
        if not PYSTRAY_AVAILABLE:
            return

        def _on_toggle_console(icon, item):
            self.root.after(0, self.toggle_console_visibility)

        def _on_toggle_all_notes(icon, item):
            self.root.after(0, self.toggle_all_notes_visibility)

        def _on_add_note(icon, item):
            self.root.after(0, self.add_note_from_ui)

        def _on_toggle_lock(icon, item):
            self.root.after(0, self.toggle_lock_through)

        def _on_toggle_layout(icon, item):
            self.root.after(
                0,
                self.set_vertical_layout
                if self.layout_mode == "horizontal"
                else self.set_horizontal_layout,
            )

        def _on_open_sound(icon, item):
            self.root.after(0, self.open_sound_settings_dialog)

        def _on_open_api(icon, item):
            self.root.after(0, self.open_api_settings_dialog)

        def _on_open_pref(icon, item):
            self.root.after(0, self.open_preferences_dialog)

        def _on_exit(icon, item):
            if self.tray_icon:
                self.tray_icon.stop()
            self.root.after(0, self.on_app_exit)

        tray_menu = pystray.Menu(
            pystray.MenuItem(
                self.t("tray_toggle_console"), _on_toggle_console, default=True
            ),
            pystray.MenuItem(self.t("tray_new_note"), _on_add_note),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.t("tray_toggle_notes"), _on_toggle_all_notes),
            pystray.MenuItem(self.t("tray_toggle_lock"), _on_toggle_lock),
            pystray.MenuItem(self.t("tray_toggle_layout"), _on_toggle_layout),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.t("tray_sound"), _on_open_sound),
            pystray.MenuItem(self.t("tray_api"), _on_open_api),
            pystray.MenuItem(self.t("tray_pref"), _on_open_pref),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.t("tray_exit"), _on_exit),
        )

        tray_image = create_tray_image()
        self.tray_icon = pystray.Icon(
            "StickyNotesApp",
            tray_image,
            "StickyNotes-AI",
            tray_menu,
        )
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def toggle_console_visibility(self):
        if self.root.state() == "withdrawn" or self.root.state() == "iconic":
            self.show_console_properly()
        else:
            self._safe_withdraw()

    def toggle_all_notes_visibility(self):
        self.all_notes_hidden = not self.all_notes_hidden
        for n in self.notes:
            if self.all_notes_hidden:
                n.win.withdraw()
            else:
                n.win.deiconify()

    def _build_control_bar(self, init_pos=False):
        if hasattr(self, "control_frame") and self.control_frame:
            self.control_frame.destroy()
        self.control_frame = tk.Frame(self.root)
        self.control_frame.pack(fill=tk.BOTH, expand=True)

        row1 = tk.Frame(self.control_frame, padx=10, pady=4)
        row1.pack(fill=tk.X)

        tk.Label(row1, text=self.t("task")).pack(side=tk.LEFT)
        self.entry_task = tk.Entry(row1, width=12)
        self.entry_task.insert(0, "New Task" if self.active_lang == "en" else "新事项")
        self.entry_task.pack(side=tk.LEFT, padx=3)
        self.entry_task.bind("<Return>", lambda e: self.add_note_from_ui())
        add_context_menu(self.entry_task, lang=self.active_lang)

        tk.Label(row1, text=self.t("time")).pack(side=tk.LEFT)
        self.entry_time = tk.Entry(row1, width=7)
        self.entry_time.insert(0, "30m")
        self.entry_time.pack(side=tk.LEFT, padx=3)
        self.entry_time.bind("<Return>", lambda e: self.add_note_from_ui())
        add_context_menu(self.entry_time, lang=self.active_lang)

        btn_add = tk.Button(
            row1,
            text=self.t("btn_new"),
            command=self.add_note_from_ui,
            bg="#4CAF50",
            fg="white",
            bd=0,
            padx=8,
            pady=2,
        )
        btn_add.pack(side=tk.LEFT, padx=5)

        tk.Label(
            row1,
            text=self.t("max_per_row"),
            font=("Microsoft YaHei", 9, "bold"),
            fg="#1565C0",
        ).pack(side=tk.LEFT, padx=(8, 2))
        self.entry_max_per_row = tk.Entry(
            row1, width=3, justify=tk.CENTER, font=("Microsoft YaHei", 9, "bold")
        )
        self.entry_max_per_row.insert(0, getattr(self, "saved_max_cache", "5"))
        self.entry_max_per_row.pack(side=tk.LEFT, padx=1)
        tk.Label(row1, text=self.t("unit_notes")).pack(side=tk.LEFT, padx=(1, 10))
        self.entry_max_per_row.bind(
            "<KeyRelease>",
            lambda e: (self.sort_and_arrange(force=True), self.save_state()),
        )
        add_context_menu(self.entry_max_per_row, lang=self.active_lang)

        tk.Label(row1, text=self.t("screen")).pack(side=tk.LEFT, padx=(4, 2))
        screen_options = [
            f"Screen {i+1} ({m['width']}x{m['height']})"
            + (" [Primary]" if m["is_primary"] else "")
            if self.active_lang == "en"
            else f"屏幕 {i+1} ({m['width']}x{m['height']})"
            + (" [主]" if m["is_primary"] else "")
            for i, m in enumerate(self.monitors)
        ]
        chosen_idx = min(self.current_screen_idx, len(screen_options) - 1)
        self.screen_var = tk.StringVar(value=screen_options[chosen_idx])
        # 宽度设为 30，确保英文 [Primary] 完整显示不被截断
        self.screen_combo = ttk.Combobox(
            row1,
            textvariable=self.screen_var,
            values=screen_options,
            state="readonly",
            width=30,
        )
        self.screen_combo.pack(side=tk.LEFT, padx=2)
        self.screen_combo.bind(
            "<<ComboboxSelected>>", self._on_screen_selected
        )

        row2 = tk.Frame(self.control_frame, padx=10, pady=3)
        row2.pack(fill=tk.X)

        self.btn_h = tk.Button(
            row2,
            text=self.t("btn_h"),
            command=self.set_horizontal_layout,
            bg="#E0E0E0",
            bd=0,
            padx=6,
            pady=2,
        )
        self.btn_h.pack(side=tk.LEFT, padx=2)

        self.btn_v = tk.Button(
            row2,
            text=self.t("btn_v"),
            command=self.set_vertical_layout,
            bg="#E0E0E0",
            bd=0,
            padx=6,
            pady=2,
        )
        self.btn_v.pack(side=tk.LEFT, padx=2)

        self.btn_top = tk.Button(
            row2,
            text=self.t("top_on") if self.is_topmost else self.t("top_off"),
            command=self.toggle_topmost,
            bg="#90CAF9" if self.is_topmost else "#E0E0E0",
            bd=0,
            padx=6,
            pady=2,
        )
        self.btn_top.pack(side=tk.LEFT, padx=2)

        self.btn_mode = tk.Button(
            row2,
            text=self.t("mode_box") if self.drag_mode == "box" else self.t("mode_free"),
            command=self.toggle_drag_mode,
            bg="#FFE082" if self.drag_mode == "box" else "#E0E0E0",
            bd=0,
            padx=6,
            pady=2,
        )
        self.btn_mode.pack(side=tk.LEFT, padx=2)

        self.btn_lock = tk.Button(
            row2,
            text=self.t("lock_on") if self.is_locked else self.t("lock_off"),
            command=self.toggle_lock_through,
            bg="#FF7043" if self.is_locked else "#B0BEC5",
            fg="white" if self.is_locked else "black",
            bd=0,
            padx=8,
            pady=2,
        )
        self.btn_lock.pack(side=tk.LEFT, padx=4)

        tk.Label(row2, text=self.t("opacity")).pack(side=tk.LEFT, padx=(6, 0))
        self.slider_alpha = tk.Scale(
            row2,
            from_=20,
            to=100,
            orient=tk.HORIZONTAL,
            showvalue=0,
            length=65,
            command=self._on_slider_alpha,
        )
        self.slider_alpha.set(int(self.alpha * 100))
        self.slider_alpha.pack(side=tk.LEFT, padx=2)

        self.label_alpha = tk.Label(
            row2, text=f"{int(self.alpha * 100)}%", width=5, font=("Microsoft YaHei", 8)
        )
        self.label_alpha.pack(side=tk.LEFT)

        self.btn_sound = tk.Button(
            row2,
            text=self.t("btn_sound"),
            command=self.open_sound_settings_dialog,
            bg="#FFCCBC",
            fg="#BF360C",
            bd=0,
            padx=8,
            pady=2,
            font=("Microsoft YaHei", 9, "bold"),
        )
        self.btn_sound.pack(side=tk.LEFT, padx=4)

        self.btn_pref = tk.Button(
            row2,
            text=self.t("btn_pref"),
            command=self.open_preferences_dialog,
            bg="#CFD8DC",
            fg="#263238",
            bd=0,
            padx=8,
            pady=2,
            font=("Microsoft YaHei", 9, "bold"),
        )
        self.btn_pref.pack(side=tk.LEFT, padx=4)

        row3 = tk.Frame(self.control_frame, padx=10, pady=4, bg="#EDE7F6")
        row3.pack(fill=tk.X)

        tk.Label(
            row3,
            text=self.t("ai_memo"),
            bg="#EDE7F6",
            font=("Microsoft YaHei", 9, "bold"),
            fg="#4A148C",
        ).pack(side=tk.LEFT, padx=(2, 4))

        self.label_ai_status = tk.Label(
            row3,
            text=self.t("status_ready"),
            bg="#EDE7F6",
            fg="#6A1B9A",
            font=("Microsoft YaHei", 8),
        )
        self.label_ai_status.pack(side=tk.RIGHT, padx=4)

        self.btn_settings = tk.Button(
            row3,
            text=self.t("btn_api"),
            command=self.open_api_settings_dialog,
            bg="#D1C4E9",
            bd=0,
            padx=8,
            pady=2,
            font=("Microsoft YaHei", 8),
        )
        self.btn_settings.pack(side=tk.RIGHT, padx=3)

        self.btn_ai = tk.Button(
            row3,
            text=self.t("btn_parse"),
            command=self.trigger_ai_parse,
            bg="#7E57C2",
            fg="white",
            bd=0,
            padx=10,
            pady=2,
            font=("Microsoft YaHei", 8, "bold"),
        )
        self.btn_ai.pack(side=tk.RIGHT, padx=4)

        self.entry_ai = tk.Entry(row3, font=("Microsoft YaHei", 9))
        self.entry_ai.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.entry_ai.bind("<Return>", lambda e: self.trigger_ai_parse())
        add_context_menu(self.entry_ai, lang=self.active_lang)

        # 每次构建或切换语言后自动重算主窗口尺寸，确保所有按钮完整露出
        self._fit_main_console(init_pos=init_pos)

    def _bind_shortcuts(self):
        def is_typing(event):
            return isinstance(
                event.widget, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox)
            )

        def shortcut_n(event):
            if is_typing(event):
                return
            self.add_note_from_ui()

        def shortcut_j(event):
            if is_typing(event):
                return
            self.trigger_ai_parse()

        def shortcut_h(event):
            if is_typing(event):
                return
            self.set_horizontal_layout()

        def shortcut_v(event):
            if is_typing(event):
                return
            self.set_vertical_layout()

        def shortcut_t(event):
            if is_typing(event):
                return
            self.toggle_topmost()

        def shortcut_m(event):
            if is_typing(event):
                return
            self.toggle_drag_mode()

        def shortcut_l(event):
            if is_typing(event):
                return
            self.toggle_lock_through()

        def shortcut_o(event):
            if is_typing(event):
                return
            self.cycle_alpha_shortcut()

        for key in ("<n>", "<N>", "<Control-n>", "<Control-N>"):
            self.root.bind_all(key, shortcut_n)
        for key in ("<j>", "<J>", "<Control-j>", "<Control-J>"):
            self.root.bind_all(key, shortcut_j)
        for key in ("<h>", "<H>", "<Control-h>", "<Control-H>"):
            self.root.bind_all(key, shortcut_h)
        for key in ("<v>", "<V>", "<Control-v>", "<Control-V>"):
            self.root.bind_all(key, shortcut_v)
        for key in ("<t>", "<T>", "<Control-t>", "<Control-T>"):
            self.root.bind_all(key, shortcut_t)
        for key in ("<m>", "<M>", "<Control-m>", "<Control-M>"):
            self.root.bind_all(key, shortcut_m)
        for key in ("<l>", "<L>", "<Control-l>", "<Control-L>"):
            self.root.bind_all(key, shortcut_l)
        for key in ("<o>", "<O>", "<Control-o>", "<Control-O>"):
            self.root.bind_all(key, shortcut_o)

    def open_preferences_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title(self.t("pref_title"))
        dialog.attributes("-topmost", True)
        dialog.resizable(False, False)

        is_root_visible = (self.root.state() == "normal")
        if is_root_visible:
            dialog.transient(self.root)
            dialog.grab_set()

        main_box = tk.Frame(dialog, padx=18, pady=14)
        main_box.pack(fill=tk.BOTH, expand=True)

        frame_lang = tk.LabelFrame(
            main_box, text=self.t("pref_lang_frame"), padx=12, pady=8
        )
        frame_lang.pack(fill=tk.X, pady=(0, 10))

        lang_var = tk.StringVar(value=self.pref_language)
        tk.Radiobutton(
            frame_lang,
            text=self.t("pref_lang_auto"),
            variable=lang_var,
            value="auto",
        ).pack(anchor="w", pady=2)
        tk.Radiobutton(
            frame_lang,
            text=self.t("pref_lang_zh"),
            variable=lang_var,
            value="zh",
        ).pack(anchor="w", pady=2)
        tk.Radiobutton(
            frame_lang,
            text=self.t("pref_lang_en"),
            variable=lang_var,
            value="en",
        ).pack(anchor="w", pady=2)

        frame_close = tk.LabelFrame(
            main_box, text=self.t("pref_close_frame"), padx=12, pady=8
        )
        frame_close.pack(fill=tk.X, pady=(0, 12))

        close_var = tk.StringVar(value=self.close_action)
        tk.Radiobutton(
            frame_close,
            text=self.t("pref_close_tray"),
            variable=close_var,
            value="tray",
            font=("Microsoft YaHei", 9, "bold"),
            fg="#1565C0",
        ).pack(anchor="w", pady=2)
        tk.Radiobutton(
            frame_close,
            text=self.t("pref_close_exit"),
            variable=close_var,
            value="exit",
        ).pack(anchor="w", pady=2)

        btn_box = tk.Frame(main_box)
        btn_box.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 0))

        def save_pref():
            try:
                self.saved_max_cache = (
                    self.entry_max_per_row.get().strip() or "5"
                )
            except Exception:
                pass
            self.pref_language = lang_var.get()
            self.close_action = close_var.get()
            self.update_active_lang()
            self.root.title(self.t("app_title"))
            self._build_control_bar(init_pos=False)
            for n in self.notes:
                n._update_color()
                n.time_label.configure(text=n._format_time())

            if self.tray_icon:
                try:
                    self.tray_icon.stop()
                except Exception:
                    pass
                self._init_system_tray()

            self.save_state()
            dialog.destroy()
            messagebox.showinfo(
                "Preferences" if self.active_lang == "en" else "偏好设置",
                self.t("pref_saved_tip"),
                parent=self.root if is_root_visible else None,
            )

        btn_save = tk.Button(
            btn_box,
            text=self.t("pref_save"),
            command=save_pref,
            bg="#4CAF50",
            fg="white",
            bd=0,
            padx=14,
            pady=4,
            font=("Microsoft YaHei", 9, "bold"),
        )
        btn_save.pack(side=tk.RIGHT, padx=4)

        btn_cancel = tk.Button(
            btn_box,
            text=self.t("pref_cancel"),
            command=dialog.destroy,
            bg="#E0E0E0",
            bd=0,
            padx=12,
            pady=4,
        )
        btn_cancel.pack(side=tk.RIGHT, padx=4)

        auto_fit_window(
            dialog,
            min_w=460,
            min_h=300,
            pad_w=24,
            pad_h=16,
            center_on=self.root if is_root_visible else None,
            default_mon=self.monitors[self.current_screen_idx],
        )
        dialog.deiconify()
        dialog.lift()
        dialog.focus_force()

    def stop_alert_sound(self):
        self._sound_seq_id += 1
        mci_send("stop alert_bgm")
        mci_send("close alert_bgm")
        if WINSOUND_AVAILABLE:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass

    def play_alert_sound(
        self,
        level="warning",
        mode_override=None,
        temp_file=None,
        temp_start_ms=None,
        temp_end_ms=None,
    ):
        mode = mode_override or self.sound_mode
        self._sound_seq_id += 1
        my_seq = self._sound_seq_id

        mci_send("stop alert_bgm")
        mci_send("close alert_bgm")

        if mode == "custom_mp3":
            target_file = temp_file if temp_file is not None else self.custom_audio_path
            target_file = resolve_app_path(target_file) if target_file else ""
            st_ms = (
                temp_start_ms
                if temp_start_ms is not None
                else self.custom_start_ms
            )
            ed_ms = (
                temp_end_ms if temp_end_ms is not None else self.custom_end_ms
            )

            if target_file and os.path.exists(target_file):
                if mci_open_audio(target_file, "alert_bgm"):
                    start_pos = max(0, int(st_ms))
                    end_pos = max(start_pos + 300, int(ed_ms))
                    mci_send(f"play alert_bgm from {start_pos} to {end_pos}")
                    return

        def _beep_worker():
            if not WINSOUND_AVAILABLE:
                return
            try:
                if mode == "beep_double":
                    if self._sound_seq_id != my_seq:
                        return
                    winsound.Beep(880, 180)
                    time.sleep(0.08)
                    if self._sound_seq_id != my_seq:
                        return
                    winsound.Beep(1046, 220)
                elif mode == "beep_urgent":
                    for _ in range(3):
                        if self._sound_seq_id != my_seq:
                            return
                        winsound.Beep(1200, 140)
                        time.sleep(0.06)
                elif mode == "chime_up":
                    for freq in (523, 659, 784, 1046):
                        if self._sound_seq_id != my_seq:
                            return
                        winsound.Beep(freq, 130)
                else:
                    if self._sound_seq_id != my_seq:
                        return
                    if level == "due":
                        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                    else:
                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

        threading.Thread(target=_beep_worker, daemon=True).start()

    def open_sound_settings_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title(
            "Ringtone Settings"
            if self.active_lang == "en"
            else "提醒铃声与自定义 MP3 截取设置"
        )
        dialog.attributes("-topmost", True)
        dialog.resizable(True, True)

        is_root_visible = (self.root.state() == "normal")
        if is_root_visible:
            dialog.transient(self.root)
            dialog.grab_set()

        temp_state = {
            "file_path": self.custom_audio_path,
            "total_sec": 10.0,
            "loaded": False,
        }

        def stop_all_preview():
            mci_send("stop preview_bgm")
            mci_send("close preview_bgm")
            self.stop_alert_sound()

        def on_dialog_close():
            stop_all_preview()
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

        main_container = tk.Frame(dialog, padx=16, pady=12)
        main_container.pack(fill=tk.BOTH, expand=True)

        t_step1 = (
            " Step 1: Select Ringtone Sound Mode "
            if self.active_lang == "en"
            else " 第一步：选择提醒音效模式 "
        )
        preset_frame = tk.LabelFrame(
            main_container, text=t_step1, padx=12, pady=8
        )
        preset_frame.pack(fill=tk.X, pady=(0, 10))

        mode_var = tk.StringVar(value=self.sound_mode)

        row_m1 = tk.Frame(preset_frame)
        row_m1.pack(fill=tk.X, pady=2)
        presets_m = [
            ("System Beep" if self.active_lang == "en" else "系统默认提示音", "default"),
            ("Dual Pulse" if self.active_lang == "en" else "清脆双频脉冲", "beep_double"),
            ("Urgent Tri-Beep" if self.active_lang == "en" else "急促三连警报", "beep_urgent"),
            ("Chime Up" if self.active_lang == "en" else "柔和上行和弦", "chime_up"),
        ]
        for text, val in presets_m:
            tk.Radiobutton(
                row_m1, text=text, variable=mode_var, value=val
            ).pack(side=tk.LEFT, padx=(0, 12))

        row_m2 = tk.Frame(preset_frame)
        row_m2.pack(fill=tk.X, pady=(6, 2))
        tk.Radiobutton(
            row_m2,
            text="Custom MP3/WAV Audio (Trim ≤10s segment below)"
            if self.active_lang == "en"
            else "自定义 MP3/WAV 铃声 (支持下方自由截取片段 ≤10秒)",
            variable=mode_var,
            value="custom_mp3",
            font=("Microsoft YaHei", 9, "bold"),
            fg="#4A148C",
        ).pack(side=tk.LEFT)

        t_step2 = (
            " Step 2: Upload Audio & Live Preview (Max 10s clip) "
            if self.active_lang == "en"
            else " 第二步：上传音频与实时截取试听 (规定不超过 10 秒，先试听满意再保存) "
        )
        mp3_frame = tk.LabelFrame(
            main_container,
            text=t_step2,
            padx=12,
            pady=10,
        )
        mp3_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        file_row = tk.Frame(mp3_frame)
        file_row.pack(fill=tk.X, pady=(0, 8))

        def choose_mp3():
            path = filedialog.askopenfilename(
                parent=dialog,
                title="Select Audio File" if self.active_lang == "en" else "选择 MP3 或 WAV 铃声文件",
                filetypes=[("Audio Files", "*.mp3 *.wav"), ("All Files", "*.*")],
            )
            if path:
                mode_var.set("custom_mp3")
                load_audio_file(path, is_init=False)

        btn_upload = tk.Button(
            file_row,
            text=" Upload Audio (MP3/WAV) "
            if self.active_lang == "en"
            else " 上传音频 (MP3/WAV) ",
            command=choose_mp3,
            bg="#7E57C2",
            fg="white",
            bd=0,
            padx=12,
            pady=3,
            font=("Microsoft YaHei", 9, "bold"),
        )
        btn_upload.pack(side=tk.RIGHT, padx=(8, 0))

        lbl_file = tk.Label(
            file_row,
            text="Current: No file chosen"
            if self.active_lang == "en"
            else "当前音频：未选择文件",
            fg="#333333",
            font=("Microsoft YaHei", 9),
            anchor="w",
        )
        lbl_file.pack(side=tk.LEFT, fill=tk.X, expand=True)

        lbl_range_info = tk.Label(
            mp3_frame,
            text="0.0s ~ 0.0s (Clip: 0.0s / Total: 0.0s)"
            if self.active_lang == "en"
            else "当前截取区间：0.0s ~ 0.0s （截取时长 0.0 秒，上限 10.0 秒）",
            fg="#D84315",
            font=("Microsoft YaHei", 9, "bold"),
            anchor="w",
        )

        def get_current_slice_ms():
            st_s = float(slider_start.get())
            du_s = min(10.0, float(slider_dur.get()))
            ed_s = min(temp_state["total_sec"], st_s + du_s)
            return int(round(st_s * 1000)), int(round(ed_s * 1000))

        def preview_current_selection(*args):
            cur_mode = mode_var.get()
            if cur_mode != "custom_mp3":
                self.play_alert_sound(mode_override=cur_mode)
                return

            if not temp_state["loaded"] or not temp_state["file_path"]:
                messagebox.showwarning(
                    "Notice" if self.active_lang == "en" else "提示",
                    "Please choose an audio file first!"
                    if self.active_lang == "en"
                    else "请先点击右侧【上传音频 (MP3/WAV)】选择一个音频文件！",
                    parent=dialog,
                )
                return

            st_ms, ed_ms = get_current_slice_ms()
            if mci_open_audio(temp_state["file_path"], "preview_bgm"):
                mci_send(f"play preview_bgm from {st_ms} to {ed_ms}")

        def update_range_label(*args):
            st = float(slider_start.get())
            du = min(10.0, float(slider_dur.get()))
            tot = temp_state["total_sec"]
            if st + du > tot:
                du = max(0.5, tot - st)
                slider_dur.set(round(du, 1))
            ed = min(tot, st + du)
            if self.active_lang == "en":
                lbl_range_info.configure(
                    text=f"Clip Range: {st:.1f}s ~ {ed:.1f}s (Duration: {ed - st:.1f}s / Total: {tot:.1f}s)"
                )
            else:
                lbl_range_info.configure(
                    text=f"当前截取区间：{st:.1f} 秒 ~ {ed:.1f} 秒 （片段时长 {ed - st:.1f} 秒 / 音频总长 {tot:.1f} 秒）"
                )

        slider_row1 = tk.Frame(mp3_frame)
        slider_row1.pack(fill=tk.X, pady=3)
        tk.Label(
            slider_row1,
            text="Start Position (s):"
            if self.active_lang == "en"
            else "截取起始位置 (秒):",
            width=18,
            anchor="w",
        ).pack(side=tk.LEFT)
        slider_start = tk.Scale(
            slider_row1,
            from_=0.0,
            to=10.0,
            resolution=0.1,
            orient=tk.HORIZONTAL,
            command=update_range_label,
        )
        slider_start.pack(side=tk.LEFT, fill=tk.X, expand=True)

        slider_row2 = tk.Frame(mp3_frame)
        slider_row2.pack(fill=tk.X, pady=3)
        tk.Label(
            slider_row2,
            text="Duration (≤10s):"
            if self.active_lang == "en"
            else "截取片段时长 (≤10s):",
            width=18,
            anchor="w",
        ).pack(side=tk.LEFT)
        slider_dur = tk.Scale(
            slider_row2,
            from_=0.5,
            to=10.0,
            resolution=0.1,
            orient=tk.HORIZONTAL,
            command=update_range_label,
        )
        slider_dur.set(10.0)
        slider_dur.pack(side=tk.LEFT, fill=tk.X, expand=True)

        lbl_range_info.pack(fill=tk.X, pady=(6, 6))

        preview_bar = tk.Frame(mp3_frame)
        preview_bar.pack(fill=tk.X, pady=(4, 2))

        tk.Button(
            preview_bar,
            text=" ▶ Play Selected Clip "
            if self.active_lang == "en"
            else " ▶ 立即试听所选片段 ",
            command=preview_current_selection,
            bg="#FF9800",
            fg="white",
            bd=0,
            padx=12,
            pady=3,
            font=("Microsoft YaHei", 9, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            preview_bar,
            text=" ⏹ Stop " if self.active_lang == "en" else " ⏹ 停止试听 ",
            command=stop_all_preview,
            bg="#E0E0E0",
            bd=0,
            padx=10,
            pady=3,
            font=("Microsoft YaHei", 9),
        ).pack(side=tk.LEFT, padx=(0, 12))

        auto_preview_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            preview_bar,
            text="Auto-play on slider release"
            if self.active_lang == "en"
            else "拖动滑块松手后自动试听该段",
            variable=auto_preview_var,
            font=("Microsoft YaHei", 8),
        ).pack(side=tk.LEFT)

        def on_slider_release(event):
            if auto_preview_var.get() and temp_state["loaded"]:
                mode_var.set("custom_mp3")
                preview_current_selection()

        slider_start.bind("<ButtonRelease-1>", on_slider_release)
        slider_dur.bind("<ButtonRelease-1>", on_slider_release)

        def load_audio_file(filepath, is_init=False):
            if not filepath or not os.path.exists(filepath):
                return
            stop_all_preview()
            if not mci_open_audio(filepath, "preview_bgm"):
                if not is_init:
                    messagebox.showerror(
                        "Error" if self.active_lang == "en" else "音频格式错误",
                        "Cannot decode audio file. Please choose standard MP3 or WAV."
                        if self.active_lang == "en"
                        else "无法解码该音频文件，请选择标准 MP3 或 WAV 文件。",
                        parent=dialog,
                    )
                return

            err, length_str = mci_send("status preview_bgm length")
            try:
                total_ms = int(length_str)
            except Exception:
                total_ms = 10000

            total_sec = max(0.5, round(total_ms / 1000.0, 1))
            temp_state["file_path"] = filepath
            temp_state["total_sec"] = total_sec
            temp_state["loaded"] = True

            fname = os.path.basename(filepath)
            if len(fname) > 26:
                fname = fname[:14] + "..." + fname[-9:]
            lbl_file.configure(
                text=f"{fname} ({total_sec:.1f}s)"
                if self.active_lang == "en"
                else f"当前音频：{fname} (总长 {total_sec:.1f}s)"
            )

            max_start = max(0.0, round(total_sec - 0.5, 1))
            slider_start.configure(to=max_start)
            max_dur = min(10.0, total_sec)
            slider_dur.configure(to=max_dur)

            if is_init and self.custom_end_ms > self.custom_start_ms:
                init_st = min(
                    max_start, round(self.custom_start_ms / 1000.0, 1)
                )
                init_du = min(
                    max_dur,
                    round(
                        (self.custom_end_ms - self.custom_start_ms) / 1000.0, 1
                    ),
                )
                slider_start.set(init_st)
                slider_dur.set(init_du)
            else:
                slider_start.set(0.0)
                slider_dur.set(max_dur)
                if not is_init:
                    update_range_label()
                    preview_current_selection()
                    return

            update_range_label()

        bottom_frame = tk.Frame(main_container, pady=6)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

        tk.Label(
            bottom_frame,
            text="* Preview first, click Save when satisfied"
            if self.active_lang == "en"
            else "* 试听满意后点击右侧【确认保存设置】，不满意点击【取消】即可放弃修改",
            fg="#757575",
            font=("Microsoft YaHei", 8),
        ).pack(side=tk.LEFT)

        def save_sound_settings():
            stop_all_preview()
            chosen_mode = mode_var.get()
            if chosen_mode == "custom_mp3":
                src_path = temp_state["file_path"]
                if not src_path or not os.path.exists(src_path):
                    messagebox.showwarning(
                        "Notice" if self.active_lang == "en" else "提示",
                        "Please choose a local MP3/WAV file first!"
                        if self.active_lang == "en"
                        else "请先上传并选择一个本地 MP3/WAV 铃声文件！",
                        parent=dialog,
                    )
                    return

                ensure_data_dir()
                ext = os.path.splitext(src_path)[1].lower() or ".mp3"
                dest_path = os.path.join(DATA_DIR, f"custom_ringtone{ext}")
                try:
                    if os.path.abspath(src_path) != os.path.abspath(dest_path):
                        shutil.copy2(src_path, dest_path)
                    self.custom_audio_path = dest_path
                except Exception:
                    self.custom_audio_path = src_path

                st_ms, ed_ms = get_current_slice_ms()
                self.custom_start_ms = st_ms
                self.custom_end_ms = ed_ms

            self.sound_mode = chosen_mode
            self.save_state()
            dialog.destroy()
            messagebox.showinfo(
                "Saved" if self.active_lang == "en" else "铃声已保存",
                "Ringtone settings saved!"
                if self.active_lang == "en"
                else "提醒音效与截取区间已保存在本地配置中！",
                parent=self.root if is_root_visible else None,
            )

        btn_save = tk.Button(
            bottom_frame,
            text=" Save " if self.active_lang == "en" else " 确认保存设置 ",
            command=save_sound_settings,
            bg="#4CAF50",
            fg="white",
            bd=0,
            padx=14,
            pady=4,
            font=("Microsoft YaHei", 9, "bold"),
        )
        btn_save.pack(side=tk.RIGHT, padx=4)

        btn_cancel = tk.Button(
            bottom_frame,
            text=" Cancel " if self.active_lang == "en" else " 取消 ",
            command=on_dialog_close,
            bg="#E0E0E0",
            bd=0,
            padx=12,
            pady=4,
        )
        btn_cancel.pack(side=tk.RIGHT, padx=4)

        init_audio = resolve_app_path(self.custom_audio_path) if self.custom_audio_path else ""
        if init_audio and os.path.exists(init_audio):
            load_audio_file(init_audio, is_init=True)

        auto_fit_window(
            dialog,
            min_w=620,
            min_h=440,
            pad_w=28,
            pad_h=20,
            center_on=self.root if is_root_visible else None,
            default_mon=self.monitors[self.current_screen_idx],
        )
        dialog.deiconify()
        dialog.lift()
        dialog.focus_force()

    def trigger_reminder(self, note, reminder_type="5min"):
        task_title = note.task_entry.get().strip() or "Task"
        if reminder_type == "5min":
            self.show_toast(
                self.t("toast_warn_title"),
                self.t("toast_warn_msg").format(task=task_title),
                level="warning",
            )
        elif reminder_type == "due":
            self.show_toast(
                self.t("toast_due_title"),
                self.t("toast_due_msg").format(task=task_title),
                level="due",
            )

    def show_toast(self, title, message, level="warning"):
        toast = ToastNotification(self, title, message, level=level)
        self.active_toasts.append(toast)
        self.reposition_toasts()

    def remove_toast(self, toast):
        if toast in self.active_toasts:
            self.active_toasts.remove(toast)
        self.reposition_toasts()

    def reposition_toasts(self):
        for idx, t in enumerate(self.active_toasts):
            t.reposition(idx)

    def open_api_settings_dialog(self):
        """修复中文模式下说明文字为英文的问题：全面实现中英双语提示词动态切换"""
        is_en = self.active_lang == "en"
        dialog = tk.Toplevel(self.root)
        dialog.title("AI Model API Config" if is_en else "大模型 API 设置中心")
        dialog.attributes("-topmost", True)
        dialog.resizable(True, True)

        is_root_visible = (self.root.state() == "normal")
        if is_root_visible:
            dialog.transient(self.root)
            dialog.grab_set()

        main_box = tk.Frame(dialog, padx=16, pady=12)
        main_box.pack(fill=tk.BOTH, expand=True)

        bottom_frame = tk.Frame(main_box, pady=10)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

        lbl_provider_tip = tk.Label(
            main_box,
            text="",
            fg="#1565C0",
            font=("Microsoft YaHei", 8),
            justify=tk.LEFT,
            wraplength=580,
            anchor="w",
        )

        def save_and_close():
            self.api_key = entry_key.get().strip()
            self.api_endpoint = (
                entry_endpoint.get().strip() or DEFAULT_API_ENDPOINT
            )
            self.api_model = entry_model.get().strip() or DEFAULT_API_MODEL
            self.save_state()
            dialog.destroy()
            messagebox.showinfo(
                "Saved" if is_en else "配置已保存",
                f"Endpoint: {self.api_endpoint}\nModel: {self.api_model}\nConfig saved and ready!"
                if is_en
                else f"当前服务接口：{self.api_endpoint}\n当前模型：{self.api_model}\n配置已写入本地，已准备就绪！",
                parent=self.root if is_root_visible else None,
            )

        btn_save = tk.Button(
            bottom_frame,
            text=" Save Config " if is_en else " 保存配置 ",
            command=save_and_close,
            bg="#4CAF50",
            fg="white",
            bd=0,
            padx=14,
            pady=4,
        )
        btn_save.pack(side=tk.RIGHT, padx=4)

        btn_cancel = tk.Button(
            bottom_frame,
            text=" Cancel " if is_en else " 取消 ",
            command=dialog.destroy,
            bd=0,
            bg="#E0E0E0",
            padx=12,
            pady=4,
        )
        btn_cancel.pack(side=tk.RIGHT, padx=4)

        t_quick = (
            " Popular AI Providers (Click to auto-fill) "
            if is_en
            else " 常用大模型服务商一键填充 (点击切换) "
        )
        preset_frame = tk.LabelFrame(main_box, text=t_quick, padx=10, pady=8)
        preset_frame.pack(fill=tk.X, pady=(0, 6))

        def apply_preset(endpoint, model, tip_text):
            entry_endpoint.delete(0, tk.END)
            entry_endpoint.insert(0, endpoint)
            entry_model.delete(0, tk.END)
            entry_model.insert(0, model)
            lbl_provider_tip.configure(text=tip_text)

        row_p1 = tk.Frame(preset_frame)
        row_p1.pack(fill=tk.X, pady=2)
        row_p2 = tk.Frame(preset_frame)
        row_p2.pack(fill=tk.X, pady=2)

        providers = [
            (
                row_p1,
                "Zhipu AI (Free)" if is_en else "智谱 (免费推荐)",
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                "glm-4-flash",
                "#E8F5E9",
                "💡 [Zhipu AI]: GLM-4-Flash is free forever. Get key at: open.bigmodel.cn"
                if is_en
                else "💡【智谱 AI】：GLM-4-Flash 永久免费，国内直连延迟极低。Key 获取：open.bigmodel.cn",
            ),
            (
                row_p1,
                "DeepSeek",
                "https://api.deepseek.com/chat/completions",
                "deepseek-chat",
                "#E3F2FD",
                "💡 [DeepSeek]: Strong reasoning. Get key at: platform.deepseek.com"
                if is_en
                else "💡【DeepSeek】：推理能力极强，国内直连。Key 获取：platform.deepseek.com",
            ),
            (
                row_p1,
                "Kimi" if is_en else "Kimi (月之暗面)",
                "https://api.moonshot.cn/v1/chat/completions",
                "moonshot-v1-8k",
                "#FFF3E0",
                "💡 [Kimi]: Excellent Chinese/English parsing. Key: platform.moonshot.cn"
                if is_en
                else "💡【Kimi】：长文本与口语拆解出色，国内直连。Key 获取：platform.moonshot.cn",
            ),
            (
                row_p1,
                "Qwen (Alibaba)" if is_en else "通义千问",
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                "qwen-turbo",
                "#EDE7F6",
                "💡 [Qwen]: Alibaba DashScope compatible mode. Key: bailian.console.aliyun.com"
                if is_en
                else "💡【阿里通义千问】：百炼平台兼容模式，可选 qwen-turbo / qwen-plus。Key 获取：bailian.console.aliyun.com",
            ),
            (
                row_p2,
                "Doubao" if is_en else "字节豆包",
                "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
                "ep-your-endpoint-id" if is_en else "ep-请替换为火山接入点ID",
                "#FCE4EC",
                "⚠️ [Doubao]: Model name must be your Volcengine Endpoint ID (ep-xxxx)."
                if is_en
                else "⚠️【字节豆包】：模型名称必须填写火山引擎控制台创建的接入点 ID (如 ep-2025...)，官网：console.volcengine.com/ark",
            ),
            (
                row_p2,
                "OpenAI (GPT)",
                "https://api.openai.com/v1/chat/completions",
                "gpt-4o-mini",
                "#E0F2F1",
                "💡 [OpenAI]: Works directly overseas/TUN, or via system proxy automatically."
                if is_en
                else "💡【OpenAI】：支持海外/TUN直连、系统代理或填入第三方中转接口地址。",
            ),
            (
                row_p2,
                "Google Gemini",
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                "gemini-2.5-flash",
                "#E8EAF6",
                "💡 [Gemini]: Works directly overseas/TUN, or via system proxy automatically. Key: aistudio.google.com"
                if is_en
                else "💡【Google Gemini】：官方兼容接口，支持直连或系统代理自动回退。Key 免费获取：aistudio.google.com",
            ),
            (
                row_p2,
                "Custom / Local" if is_en else "自定义 / 本地",
                "http://localhost:11434/v1/chat/completions",
                "qwen2.5:7b",
                "#ECEFF1",
                "💡 [Custom/Ollama]: Supports Ollama, OneAPI, or any OpenAI-compatible server."
                if is_en
                else "💡【自定义 / 本地大模型】：支持 Ollama 本地离线模型、OneAPI、NewAPI 或任意 OpenAI 规范中转站。",
            ),
        ]

        for parent_row, label, ep, mod, bg_c, tip in providers:
            tk.Button(
                parent_row,
                text=label,
                command=lambda e=ep, m=mod, t=tip: apply_preset(e, m, t),
                bg=bg_c,
                bd=0,
                padx=6,
                pady=2,
                font=("Microsoft YaHei", 8),
            ).pack(side=tk.LEFT, padx=3)

        lbl_provider_tip.pack(fill=tk.X, pady=(2, 6))

        form_frame = tk.Frame(main_box, pady=4)
        form_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            form_frame,
            text="API Key:" if is_en else "API Key (密钥):",
            font=("Microsoft YaHei", 9, "bold"),
        ).pack(anchor="w", pady=(4, 2))
        entry_key = tk.Entry(form_frame, font=("Consolas", 10), width=60)
        entry_key.insert(0, self.api_key)
        entry_key.pack(fill=tk.X, pady=(0, 6))
        add_context_menu(entry_key, lang=self.active_lang)

        tk.Label(
            form_frame,
            text="API Endpoint:" if is_en else "接口地址 (Endpoint):",
            font=("Microsoft YaHei", 9),
        ).pack(anchor="w", pady=(2, 2))
        entry_endpoint = tk.Entry(form_frame, font=("Consolas", 9), width=60)
        entry_endpoint.insert(0, self.api_endpoint)
        entry_endpoint.pack(fill=tk.X, pady=(0, 6))
        add_context_menu(entry_endpoint, lang=self.active_lang)

        tk.Label(
            form_frame,
            text="Model Name:" if is_en else "模型名称 (Model):",
            font=("Microsoft YaHei", 9),
        ).pack(anchor="w", pady=(2, 2))
        entry_model = tk.Entry(form_frame, font=("Consolas", 9), width=60)
        entry_model.insert(0, self.api_model)
        entry_model.pack(fill=tk.X, pady=(0, 4))
        add_context_menu(entry_model, lang=self.active_lang)

        default_tip = (
            "💡 Click presets above to switch between Zhipu, DeepSeek, Kimi, Qwen, Doubao, GPT, Gemini, or Ollama."
            if is_en
            else "💡 点击上方预设按钮可在智谱、DeepSeek、Kimi、通义千问、豆包、GPT、Gemini 或本地模型间一键切换。"
        )
        apply_preset(self.api_endpoint, self.api_model, default_tip)

        auto_fit_window(
            dialog,
            min_w=620,
            min_h=450,
            pad_w=28,
            pad_h=20,
            center_on=self.root if is_root_visible else None,
            default_mon=self.monitors[self.current_screen_idx],
        )
        dialog.deiconify()
        dialog.lift()
        dialog.focus_force()

    def open_custom_edit_dialog(self, note):
        dialog = tk.Toplevel(self.root)
        dialog.title(
            "Edit Note Time" if self.active_lang == "en" else "修改便签时间"
        )
        dialog.attributes("-topmost", True)
        dialog.resizable(True, False)
        dialog.transient(note.win)
        dialog.grab_set()

        curr_text = note._format_time()
        container = tk.Frame(dialog, padx=18, pady=12)
        container.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            container,
            text=f"Current: [{curr_text}]"
            if self.active_lang == "en"
            else f"当前设定：【{curr_text}】",
            font=("Microsoft YaHei", 10, "bold"),
            fg="#1565C0",
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            container,
            text="Enter countdown (e.g. 5m10s, 10m, 2h), schedule (e.g. tomorrow), or click Pending:"
            if self.active_lang == "en"
            else "可输入倒计时(如 5m10s, 10m, 2h)、模糊日程(如 明天下午) 或点击设为待定：",
            font=("Microsoft YaHei", 9),
            fg="#616161",
            anchor="w",
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 8))

        entry_box = tk.Frame(container)
        entry_box.pack(fill=tk.X, pady=(0, 12))

        def set_to_pending():
            note.is_pending = True
            note.is_fuzzy = False
            note.fuzzy_label = ""
            note.fuzzy_target_date = ""
            note.fuzzy_period = ""
            note.warned_5m = True
            note.warned_due = True
            note._update_color()
            note.time_label.configure(text=note._format_time())
            self.sort_and_arrange(force=True)
            self.save_state()
            dialog.destroy()

        btn_quick_pending = tk.Button(
            entry_box,
            text=" Set Pending " if self.active_lang == "en" else " 设为待定 ",
            command=set_to_pending,
            bg="#FFCDD2",
            fg="#C62828",
            bd=0,
            padx=10,
            pady=2,
            font=("Microsoft YaHei", 9, "bold"),
        )
        btn_quick_pending.pack(side=tk.RIGHT, padx=(8, 0))

        entry = tk.Entry(entry_box, font=("Microsoft YaHei", 10), width=36)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entry.focus_set()
        add_context_menu(entry, lang=self.active_lang)

        btn_box = tk.Frame(container)
        btn_box.pack(side=tk.BOTTOM, fill=tk.X, pady=(4, 0))

        def do_update():
            new_val = entry.get().strip()
            if new_val:
                if new_val.lower() in ["待定", "pending"]:
                    set_to_pending()
                    return

                norm_val = convert_cn_numbers(new_val)
                if any(
                    k in new_val.lower()
                    for k in [
                        "明天", "明日", "后天", "大后天", "今天", "今日", "周", "星期",
                        "tomorrow", "today", "yesterday", "next", "afternoon", "morning",
                    ]
                ) and not re.search(
                    r"^\d+(?:\.\d+)?\s*(?:d|days?|h|hours?|m|mins?|s|secs?|[天时分秒])",
                    norm_val.lower(),
                ):
                    note.set_fuzzy_schedule(new_val)
                else:
                    note.is_pending = False
                    note.is_fuzzy = False
                    note.fuzzy_target_date = ""
                    note.fuzzy_period = ""
                    note.remaining_seconds = parse_time_input(new_val)
                    note.target_timestamp = (
                        time.time() + note.remaining_seconds
                    )
                    if note.remaining_seconds > 300:
                        note.warned_5m = False
                        note.warned_due = False
                    else:
                        note.warned_5m = True
                        note.warned_due = False

                note._update_color()
                note.time_label.configure(text=note._format_time())
                self.sort_and_arrange(force=True)
                self.save_state()
            dialog.destroy()

        btn_ok = tk.Button(
            btn_box,
            text=" Apply " if self.active_lang == "en" else " 确认修改 ",
            command=do_update,
            bg="#4CAF50",
            fg="white",
            bd=0,
            padx=14,
            pady=3,
        )
        btn_ok.pack(side=tk.RIGHT, padx=4)

        btn_no = tk.Button(
            btn_box,
            text=" Cancel " if self.active_lang == "en" else " 取消 ",
            command=dialog.destroy,
            bd=0,
            bg="#E0E0E0",
            padx=12,
            pady=3,
        )
        btn_no.pack(side=tk.RIGHT, padx=4)
        entry.bind("<Return>", lambda e: do_update())

        auto_fit_window(
            dialog,
            min_w=480,
            min_h=190,
            pad_w=24,
            pad_h=16,
            center_on=note.win,
            default_mon=self.monitors[self.current_screen_idx],
        )
        dialog.deiconify()
        dialog.lift()
        dialog.focus_force()

    def trigger_ai_parse(self):
        if (
            not self.api_key
            and "localhost" not in self.api_endpoint
            and "127.0.0.1" not in self.api_endpoint
        ):
            self.open_api_settings_dialog()
            if not self.api_key:
                return

        user_text = self.entry_ai.get().strip()
        if not user_text:
            return

        self.btn_ai.configure(state=tk.DISABLED)
        self.label_ai_status.configure(text=self.t("status_parsing"))

        threading.Thread(
            target=self._ai_worker_thread, args=(user_text,), daemon=True
        ).start()

    def _ai_worker_thread(self, user_text):
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M")

        existing_notes_summary = [
            {
                "task": n.task_entry.get().strip(),
                "time_display": n._format_time(),
                "is_fuzzy": n.is_fuzzy,
                "is_pending": n.is_pending,
            }
            for n in self.notes
        ]
        notes_context_str = json.dumps(
            existing_notes_summary, ensure_ascii=False
        )

        prompt = f"""Current local time: {now_str}.
Current existing desktop sticky notes:
{notes_context_str}

Please parse the user's task input into an array of actionable JSON objects.
Output rules:
1. "task": Concise task title (≤8 words / characters).
2. "action": "update" (if user asks to adjust/postpone/advance an existing task or uses relative time shift) or "create".
3. "target": Matching existing task title if action is "update", otherwise "".
4. "time_mode":
   - "timer": Countdown or duration (e.g. "10m", "2h", "-30m", "+1d"). Convert all words to Arabic numbers.
   - "clock": Specific clock time (e.g. "15:00", "20:00").
   - "fuzzy": Future date/period without exact minutes (e.g. "tomorrow", "tomorrow afternoon", "in 2 days").
   - "pending": Tasks without any specified time or daily chores (e.g. "clean desk", "buy batteries").
5. "time_val":
   - If timer: duration string (e.g. "10m", "2h", "-30m", "+1d")
   - If clock: "HH:MM" in 24h format
   - If fuzzy: date tag string (e.g. "tomorrow", "in 2 days")
   - If pending: "Pending" or "待定"
6. "day_ref": If clock, set "today", "tomorrow", or "unspecified".

User Input:
{user_text}

Output format: Return ONLY a valid JSON array without any markdown formatting or explanations."""

        payload = {
            "model": self.api_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a desktop sticky notes scheduler that outputs ONLY a strict JSON array.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.api_endpoint,
                data=req_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "User-Agent": "StickyNoteApp/3.3",
                },
                method="POST",
            )

            domestic_hosts = [
                "bigmodel.cn", "deepseek.com", "moonshot.cn", "aliyuncs.com",
                "volces.com", "localhost", "127.0.0.1",
            ]
            is_domestic = any(h in self.api_endpoint for h in domestic_hosts)
            ssl_context = ssl._create_unverified_context()

            direct_opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}),
                urllib.request.HTTPSHandler(context=ssl_context),
            )
            system_opener = urllib.request.build_opener(
                urllib.request.ProxyHandler(),
                urllib.request.HTTPSHandler(context=ssl_context),
            )

            openers = (
                [direct_opener, system_opener]
                if is_domestic
                else [system_opener, direct_opener]
            )

            resp_bytes = None
            last_err = None
            for opener in openers:
                try:
                    with opener.open(req, timeout=25) as resp:
                        resp_bytes = resp.read()
                    break
                except urllib.error.HTTPError:
                    raise
                except Exception as e:
                    last_err = e

            if resp_bytes is None:
                raise last_err

            result_json = json.loads(resp_bytes.decode("utf-8"))
            content = result_json["choices"][0]["message"]["content"].strip()
            clean_json = re.sub(
                r"^```json\s*|\s*```$", "", content, flags=re.MULTILINE
            ).strip()
            items = json.loads(clean_json)

            self.root.after(0, self._on_ai_success, items, user_text)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            self.root.after(
                0, self._on_ai_failed, f"HTTP {e.code} Error:\n{err_body}"
            )
        except Exception as e:
            self.root.after(0, self._on_ai_failed, str(e))

    def _on_ai_success(self, items, raw_user_text=""):
        self.btn_ai.configure(state=tk.NORMAL)
        self.label_ai_status.configure(text=self.t("status_done"))

        if not isinstance(items, list):
            messagebox.showwarning(
                "Notice" if self.active_lang == "en" else "提示",
                "AI returned invalid format."
                if self.active_lang == "en"
                else "AI 返回了非列表格式，请重试。",
            )
            return

        now = datetime.now()
        updated_count = 0
        created_count = 0
        warnings = []

        INVALID_KEYWORDS = [
            "unspecified", "none", "null", "undefined", "未知", "无", "", "待定", "pending",
        ]
        DURATION_PATTERN = r"(\d+(?:\.\d+)?)\s*(?:d|days?|个?天|日|h|hours?|hrs?|个?小时|m|mins?|minutes?|个?分钟|分|s|secs?|seconds?|秒)"

        for it in items:
            action = it.get("action", "create")
            task = it.get("task", "Task").strip()
            time_mode = it.get("time_mode", "pending")
            time_val = str(it.get("time_val", "pending")).strip()
            day_ref = it.get("day_ref", "unspecified")

            if (
                time_val.lower() in INVALID_KEYWORDS
                or time_mode == "pending"
            ):
                time_mode = "pending"
                time_val = self.t("pending_label")

            matched_clause = extract_clause_for_task(task, raw_user_text)
            norm_clause = (
                convert_cn_numbers(matched_clause) if matched_clause else ""
            )

            is_relative_delta = False
            delta_sign = 1
            if any(k in norm_clause.lower() for k in ["提前", "提早", "缩短", "advance", "earlier"]):
                is_relative_delta = True
                delta_sign = -1
            elif any(
                k in norm_clause.lower() for k in ["推迟", "延后", "推后", "延长", "postpone", "delay", "later"]
            ):
                is_relative_delta = True
                delta_sign = 1
            elif time_val.startswith("-"):
                is_relative_delta = True
                delta_sign = -1
            elif time_val.startswith("+"):
                is_relative_delta = True
                delta_sign = 1

            is_clock_expr = bool(
                re.search(
                    r"(\d{1,2}|[一二两三四五六七八九十]+)\s*(?:点|o'clock|:\d{2})(?!\d)",
                    matched_clause,
                    re.IGNORECASE,
                )
            )
            clause_has_duration = (
                bool(re.search(DURATION_PATTERN, norm_clause, re.IGNORECASE))
                and not is_clock_expr
            )

            calibrated_secs = None
            delta_days = 0
            if clause_has_duration:
                calibrated_secs = parse_time_input(norm_clause)
                day_m = re.findall(
                    r"(\d+(?:\.\d+)?)\s*(?:d|days?|个?天|日)", norm_clause, re.IGNORECASE
                )
                if day_m:
                    delta_days = int(
                        round(delta_sign * sum(float(x) for x in day_m))
                    )
            else:
                norm_tval = convert_cn_numbers(time_val)
                day_m = re.findall(
                    r"(\d+(?:\.\d+)?)\s*(?:d|days?|个?天|日)", norm_tval, re.IGNORECASE
                )
                if day_m and is_relative_delta:
                    delta_days = int(
                        round(delta_sign * sum(float(x) for x in day_m))
                    )

            is_Fuzzy_Date_Expr = bool(
                re.search(
                    r"(?:in\s+\d+\s*days?|\d+\s*天后|tomorrow|after\s+tomorrow|明天|后天|大后天)",
                    norm_clause,
                    re.IGNORECASE,
                )
            )
            if clause_has_duration and not is_relative_delta and not is_Fuzzy_Date_Expr:
                time_mode = "timer"

            if is_relative_delta or any(
                k in norm_clause for k in ["改到", "改为", "改成", "change to", "reschedule to"]
            ):
                action = "update"

            target_name = it.get("target", "").strip() or task
            matched_note = None
            for n in self.notes:
                curr_task = n.task_entry.get().strip()
                if curr_task and (
                    target_name.lower() in curr_task.lower()
                    or curr_task.lower() in target_name.lower()
                    or task.lower() in curr_task.lower()
                    or curr_task.lower() in task.lower()
                ):
                    matched_note = n
                    break

            if matched_note and action == "create":
                action = "update"

            # ----------------- 更新已有便签 -----------------
            if action == "update":
                if matched_note:
                    if (
                        matched_note.is_fuzzy
                        and is_relative_delta
                        and delta_days != 0
                    ):
                        matched_note.shift_fuzzy_days(delta_days)

                    elif time_mode == "pending":
                        matched_note.is_pending = True
                        matched_note.is_fuzzy = False
                        matched_note.fuzzy_label = ""
                        matched_note.fuzzy_target_date = ""
                        matched_note.fuzzy_period = ""
                        matched_note.warned_5m = True
                        matched_note.warned_due = True

                    elif time_mode == "fuzzy":
                        matched_note.set_fuzzy_schedule(time_val)

                    elif time_mode == "timer":
                        matched_note.is_pending = False
                        matched_note.is_fuzzy = False
                        matched_note.fuzzy_target_date = ""
                        matched_note.fuzzy_period = ""

                        if is_relative_delta:
                            raw_delta = (
                                calibrated_secs
                                if calibrated_secs is not None
                                else abs(parse_delta_seconds(time_val))
                            )
                            delta_sec = delta_sign * raw_delta
                            matched_note.remaining_seconds = max(
                                0, matched_note.remaining_seconds + delta_sec
                            )
                        else:
                            new_sec = (
                                calibrated_secs
                                if calibrated_secs is not None
                                else parse_time_input(time_val)
                            )
                            matched_note.remaining_seconds = max(0, new_sec)

                        matched_note.target_timestamp = (
                            time.time() + matched_note.remaining_seconds
                        )
                        if matched_note.remaining_seconds > 300:
                            matched_note.warned_5m = False
                            matched_note.warned_due = False
                        else:
                            matched_note.warned_5m = True
                            matched_note.warned_due = False

                    elif time_mode == "clock":
                        matched_note.is_pending = False
                        matched_note.is_fuzzy = False
                        matched_note.fuzzy_target_date = ""
                        matched_note.fuzzy_period = ""
                        try:
                            hh, mm = map(int, time_val.split(":"))
                            target_dt = now.replace(
                                hour=hh, minute=mm, second=0
                            )
                            if target_dt < now:
                                target_dt += timedelta(days=1)
                            matched_note.remaining_seconds = int(
                                math.ceil((target_dt - now).total_seconds())
                            )
                            matched_note.target_timestamp = (
                                time.time() + matched_note.remaining_seconds
                            )
                            if matched_note.remaining_seconds > 300:
                                matched_note.warned_5m = False
                                matched_note.warned_due = False
                            else:
                                matched_note.warned_5m = True
                                matched_note.warned_due = False
                        except Exception:
                            pass

                    matched_note._update_color()
                    matched_note.time_label.configure(
                        text=matched_note._format_time()
                    )
                    updated_count += 1
                    continue
                else:
                    if is_relative_delta:
                        self.create_note(
                            task,
                            0,
                            is_pending=True,
                            warned_5m=True,
                            warned_due=True,
                            do_sort=False,
                        )
                        created_count += 1
                        msg = (
                            f"⚠️ Note [{task}] not found! Created as Pending."
                            if self.active_lang == "en"
                            else f"⚠️ 未找到已有便签【{task}】！已为您将其创建为【待定】便签。"
                        )
                        warnings.append(msg)
                        continue
                    else:
                        action = "create"

            # ----------------- 新建便签 -----------------
            if action == "create":
                is_pending = False
                is_fuzzy = False
                fuzzy_label = ""
                fuzzy_target_date = ""
                fuzzy_period = ""
                secs = 0
                warned_5m = False
                warned_due = False

                if time_mode == "pending":
                    is_pending = True
                    secs = 0
                    warned_5m = True
                    warned_due = True

                elif time_mode == "fuzzy":
                    is_fuzzy = True
                    fuzzy_label = time_val
                    fuzzy_target_date, fuzzy_period = parse_fuzzy_date_anchor(
                        fuzzy_label
                    )
                    fuzzy_label = compute_dynamic_fuzzy_label(
                        fuzzy_target_date,
                        fuzzy_period,
                        fuzzy_label,
                        lang=self.active_lang,
                    )
                    secs = get_fuzzy_rank_seconds(
                        fuzzy_label, fuzzy_target_date, fuzzy_period
                    )
                    warned_5m = True
                    warned_due = True

                elif time_mode == "timer":
                    is_fuzzy = False
                    secs = (
                        calibrated_secs
                        if calibrated_secs is not None
                        else parse_time_input(time_val)
                    )
                    warned_5m = secs <= 300
                    warned_due = secs == 0

                elif time_mode == "clock":
                    is_fuzzy = False
                    try:
                        hh, mm = map(int, time_val.split(":"))
                        target_dt = now.replace(hour=hh, minute=mm, second=0)

                        if day_ref == "tomorrow":
                            target_dt += timedelta(days=1)
                        elif day_ref == "today":
                            if target_dt < now:
                                target_dt += timedelta(days=1)
                        elif day_ref == "unspecified":
                            if target_dt < now:
                                target_dt += timedelta(days=1)

                        secs = max(
                            60, int(math.ceil((target_dt - now).total_seconds()))
                        )
                        warned_5m = secs <= 300
                        warned_due = False
                    except Exception:
                        secs = 900

                self.create_note(
                    task,
                    secs,
                    is_fuzzy=is_fuzzy,
                    fuzzy_label=fuzzy_label,
                    fuzzy_target_date=fuzzy_target_date,
                    fuzzy_period=fuzzy_period,
                    is_pending=is_pending,
                    warned_5m=warned_5m,
                    warned_due=warned_due,
                    do_sort=False,
                )
                created_count += 1

        self.sort_and_arrange(force=True)
        self.save_state()
        self.entry_ai.delete(0, tk.END)

        if warnings:
            messagebox.showwarning(
                "Notice" if self.active_lang == "en" else "提醒",
                "\n\n".join(warnings),
                parent=self.root if (self.root.state() == "normal") else None,
            )

    def _on_ai_failed(self, err_msg):
        self.btn_ai.configure(state=tk.NORMAL)
        self.label_ai_status.configure(text=self.t("status_failed"))
        messagebox.showerror(
            "API Error" if self.active_lang == "en" else "API 请求异常",
            f"Failed to call API:\n{err_msg}",
        )

    def _create_initial_demos(self):
        demo_title = (
            "Demo Note" if self.active_lang == "en" else "示例-可随时删除"
        )
        self.create_note(
            demo_title,
            parse_time_input("30m"),
            warned_5m=False,
            warned_due=False,
        )

    def _on_screen_selected(self, event=None):
        self.current_screen_idx = self.screen_combo.current()
        cur_m = self.monitors[self.current_screen_idx]
        self.anchor_x = cur_m["left"] + 50
        self.anchor_y = cur_m["top"] + 160
        self.sort_and_arrange(force=True)
        self.save_state()

    def add_note_from_ui(self):
        task_text = self.entry_task.get().strip() or (
            "Task" if self.active_lang == "en" else "未命名任务"
        )
        time_text = self.entry_time.get().strip()
        norm_time = convert_cn_numbers(time_text)
        if time_text.lower() in ["待定", "未定", "pending", ""]:
            self.create_note(
                task_text, 0, is_pending=True, warned_5m=True, warned_due=True
            )
        elif any(
            k in time_text.lower()
            for k in [
                "明天", "明日", "后天", "大后天", "今天", "今日", "周", "星期",
                "tomorrow", "today", "yesterday", "next",
            ]
        ) and not re.search(
            r"^\d+(?:\.\d+)?\s*(?:d|days?|h|hours?|m|mins?|s|secs?|[天时分秒])",
            norm_time.lower(),
        ):
            self.create_note(
                task_text,
                86400,
                is_fuzzy=True,
                fuzzy_label=time_text,
                warned_5m=True,
                warned_due=True,
            )
        else:
            seconds = parse_time_input(time_text)
            self.create_note(
                task_text,
                seconds,
                warned_5m=seconds <= 300,
                warned_due=seconds == 0,
            )
        self.save_state()

    def create_note(
        self,
        task_text,
        seconds,
        target_timestamp=None,
        init_pos=None,
        is_fuzzy=False,
        fuzzy_label="",
        fuzzy_target_date="",
        fuzzy_period="",
        is_pending=False,
        warned_5m=False,
        warned_due=False,
        do_sort=True,
    ):
        note = StickyNoteWindow(
            self,
            task_text,
            seconds,
            self.next_id,
            target_timestamp=target_timestamp,
            init_pos=init_pos,
            is_fuzzy=is_fuzzy,
            fuzzy_label=fuzzy_label,
            fuzzy_target_date=fuzzy_target_date,
            fuzzy_period=fuzzy_period,
            is_pending=is_pending,
            warned_5m=warned_5m,
            warned_due=warned_due,
        )
        self.next_id += 1
        self.notes.append(note)

        note.win.update_idletasks()
        if self.is_locked:
            note.set_clickthrough(True)

        if do_sort:
            self.sort_and_arrange(force=True)
        return note

    def remove_note(self, note):
        if note in self.notes:
            self.notes.remove(note)
            self.sort_and_arrange(force=True)
            self.save_state()

    def toggle_drag_mode(self):
        if self.drag_mode == "box":
            self.drag_mode = "free"
            self.btn_mode.configure(text=self.t("mode_free"), bg="#E0E0E0")
        else:
            self.drag_mode = "box"
            self.btn_mode.configure(text=self.t("mode_box"), bg="#FFE082")
            self.sort_and_arrange(force=True)
        self.save_state()

    def toggle_lock_through(self):
        self.is_locked = not self.is_locked
        for note in self.notes:
            note.set_clickthrough(self.is_locked)

        if self.is_locked:
            self.btn_lock.configure(
                text=self.t("lock_on"), bg="#FF7043", fg="white"
            )
        else:
            self.btn_lock.configure(
                text=self.t("lock_off"), bg="#B0BEC5", fg="black"
            )
        self.save_state()

    def start_box_drag(self, root_x, root_y):
        self.drag_origin_mouse_x = root_x
        self.drag_origin_mouse_y = root_y
        self.drag_origin_anchor_x = self.anchor_x
        self.drag_origin_anchor_y = self.anchor_y

    def update_box_drag(self, root_x, root_y):
        dx = root_x - self.drag_origin_mouse_x
        dy = root_y - self.drag_origin_mouse_y

        cur_m = self.monitors[self.current_screen_idx]
        self.anchor_x = max(
            cur_m["left"] + 5, self.drag_origin_anchor_x + dx
        )
        self.anchor_y = max(
            cur_m["top"] + 5, self.drag_origin_anchor_y + dy
        )

        self.sort_and_arrange(force=True)
        self.save_state()

    def set_horizontal_layout(self):
        self.layout_mode = "horizontal"
        self.sort_and_arrange(force=True)
        self.save_state()

    def set_vertical_layout(self):
        self.layout_mode = "vertical"
        self.sort_and_arrange(force=True)
        self.save_state()

    def toggle_topmost(self):
        self.is_topmost = not self.is_topmost
        self.root.attributes("-topmost", self.is_topmost)
        for note in self.notes:
            note.set_topmost(self.is_topmost)
        state_text = self.t("top_on") if self.is_topmost else self.t("top_off")
        color = "#90CAF9" if self.is_topmost else "#E0E0E0"
        self.btn_top.configure(text=state_text, bg=color)
        self.save_state()

    def _on_slider_alpha(self, val):
        self.alpha = int(val) / 100.0
        self.label_alpha.configure(text=f"{int(val)}%")
        for note in self.notes:
            note.set_alpha(self.alpha)
        self.save_state()

    def cycle_alpha_shortcut(self):
        presets = [100, 80, 60, 40]
        cur = int(self.alpha * 100)
        next_val = 100
        for p in presets:
            if cur > p:
                next_val = p
                break
        self.slider_alpha.set(next_val)

    def sort_and_arrange(self, force=False):
        if not self.notes:
            return

        def get_rank_key(n):
            if n.is_pending:
                tier = 2
                sub_sec = 0
            elif n.is_fuzzy:
                tier = 1
                sub_sec = n.remaining_seconds
            else:
                tier = 0
                sub_sec = n.remaining_seconds
            return (tier, sub_sec, n.note_id)

        self.notes.sort(key=get_rank_key)
        current_order = [n.note_id for n in self.notes]

        if self.drag_mode == "free" and not force:
            for idx, note in enumerate(self.notes):
                note.move_to(
                    note.win.winfo_x(), note.win.winfo_y(), idx + 1
                )
            return

        if not force and current_order == self.last_order:
            return

        self.last_order = current_order

        cur_m = self.monitors[self.current_screen_idx]
        mon_right = cur_m["right"]
        mon_bottom = cur_m["bottom"]

        try:
            val = self.entry_max_per_row.get().strip()
            max_per_row = int(val) if val and int(val) > 0 else 0
        except (AttributeError, ValueError):
            max_per_row = 5

        gap = 14
        size = 175
        step = size + gap

        cur_col = 0
        cur_row = 0

        for idx, note in enumerate(self.notes):
            if self.layout_mode == "horizontal":
                target_x = self.anchor_x + cur_col * step
                is_max_reached = (max_per_row > 0) and (
                    cur_col >= max_per_row
                )
                is_screen_overflow = (target_x + size > mon_right - 10) and (
                    cur_col > 0
                )

                if is_max_reached or is_screen_overflow:
                    cur_col = 0
                    cur_row += 1
                    target_x = self.anchor_x

                target_y = self.anchor_y + cur_row * step
                note.move_to(target_x, target_y, idx + 1)
                cur_col += 1

            else:  # vertical
                target_y = self.anchor_y + cur_row * step
                is_max_reached = (max_per_row > 0) and (
                    cur_row >= max_per_row
                )
                is_screen_overflow = (
                    target_y + size > mon_bottom - 20
                ) and (cur_row > 0)

                if is_max_reached or is_screen_overflow:
                    cur_row = 0
                    cur_col += 1
                    target_y = self.anchor_y

                target_x = self.anchor_x + cur_col * step
                note.move_to(target_x, target_y, idx + 1)
                cur_row += 1

    def _schedule_tick(self):
        for note in self.notes:
            note.tick()
        self.sort_and_arrange(force=False)
        self.root.after(1000, self._schedule_tick)

    def save_state(self):
        try:
            notes_data = []
            for n in self.notes:
                notes_data.append(
                    {
                        "task_text": n.task_entry.get(),
                        "remaining_seconds": n.remaining_seconds,
                        "target_timestamp": n.target_timestamp,
                        "is_fuzzy": n.is_fuzzy,
                        "fuzzy_label": n.fuzzy_label,
                        "fuzzy_target_date": n.fuzzy_target_date,
                        "fuzzy_period": n.fuzzy_period,
                        "is_pending": n.is_pending,
                        "warned_5m": n.warned_5m,
                        "warned_due": n.warned_due,
                        "pos": (n.win.winfo_x(), n.win.winfo_y()),
                    }
                )

            max_val = getattr(self, "saved_max_cache", "5")
            if hasattr(self, "entry_max_per_row"):
                try:
                    max_val = self.entry_max_per_row.get().strip() or max_val
                except Exception:
                    pass

            state = {
                "layout_mode": self.layout_mode,
                "drag_mode": self.drag_mode,
                "is_topmost": self.is_topmost,
                "is_locked": self.is_locked,
                "alpha": self.alpha,
                "current_screen_idx": self.current_screen_idx,
                "max_per_row": max_val,
                "anchor_x": self.anchor_x,
                "anchor_y": self.anchor_y,
                "pref_language": self.pref_language,
                "close_action": self.close_action,
                "api_key": self.api_key,
                "api_endpoint": self.api_endpoint,
                "api_model": self.api_model,
                "sound_mode": self.sound_mode,
                "custom_audio_path": to_relative_app_path(self.custom_audio_path),
                "custom_start_ms": self.custom_start_ms,
                "custom_end_ms": self.custom_end_ms,
                "notes": notes_data,
            }

            ensure_data_dir()
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_settings_only(self):
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

            self.layout_mode = state.get("layout_mode", "horizontal")
            self.drag_mode = state.get("drag_mode", "box")
            self.is_topmost = state.get("is_topmost", True)
            self.is_locked = state.get("is_locked", False)
            self.alpha = state.get("alpha", 1.0)
            self.anchor_x = state.get("anchor_x", 60)
            self.anchor_y = state.get("anchor_y", 160)

            self.pref_language = state.get("pref_language", "auto")
            self.close_action = state.get("close_action", "tray")

            self.api_key = state.get("api_key", "")
            self.api_endpoint = state.get("api_endpoint", DEFAULT_API_ENDPOINT) or DEFAULT_API_ENDPOINT
            self.api_model = state.get("api_model", DEFAULT_API_MODEL) or DEFAULT_API_MODEL

            self.sound_mode = state.get("sound_mode", "default")
            raw_audio = state.get("custom_audio_path", "")
            self.custom_audio_path = resolve_app_path(raw_audio) if raw_audio else ""
            self.custom_start_ms = state.get("custom_start_ms", 0)
            self.custom_end_ms = state.get("custom_end_ms", 10000)

            saved_screen_idx = state.get("current_screen_idx", 0)
            if isinstance(saved_screen_idx, int) and 0 <= saved_screen_idx < len(self.monitors):
                self.current_screen_idx = saved_screen_idx

            self.saved_max_cache = str(state.get("max_per_row", "5"))
        except Exception:
            pass

    def load_saved_notes_only(self):
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

            saved_notes = state.get("notes", [])
            now = time.time()
            for n_data in saved_notes:
                rem_secs = n_data.get("remaining_seconds", 900)
                tgt_ts = n_data.get("target_timestamp")
                is_fz = n_data.get("is_fuzzy", False)
                is_pd = n_data.get("is_pending", False)

                if not is_fz and not is_pd and tgt_ts:
                    calc_rem = max(0, int(math.ceil(tgt_ts - now)))
                else:
                    calc_rem = rem_secs

                def_warn_5m = True if (is_fz or is_pd) else (calc_rem <= 300)
                def_warn_due = True if (is_fz or is_pd) else (calc_rem == 0)

                self.create_note(
                    n_data.get("task_text", "Task"),
                    calc_rem,
                    target_timestamp=tgt_ts,
                    init_pos=n_data.get("pos"),
                    is_fuzzy=is_fz,
                    fuzzy_label=n_data.get("fuzzy_label", ""),
                    fuzzy_target_date=n_data.get("fuzzy_target_date", ""),
                    fuzzy_period=n_data.get("fuzzy_period", ""),
                    is_pending=is_pd,
                    warned_5m=n_data.get("warned_5m", def_warn_5m),
                    warned_due=n_data.get("warned_due", def_warn_due),
                    do_sort=False,
                )

            self.sort_and_arrange(force=True)
        except Exception:
            pass

    def on_app_exit(self):
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.stop_alert_sound()
        mci_send("close all")
        self.save_state()
        if server_socket:
            try:
                server_socket.close()
            except Exception:
                pass
        self.root.destroy()


if __name__ == "__main__":
    main_root = tk.Tk()
    app = NoteManager(main_root)
    main_root.mainloop()