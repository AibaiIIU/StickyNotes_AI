# StickyNotes_AI 二次开发与架构指南 / Developer Guide

[简体中文说明](#中文开发指南) | [English Developer Guide](#english-developer-guide)

---

<a name="中文开发指南"></a>
## 中文开发指南

### 1. 工程结构说明

```text
StickyNotes_AI_Release/
├── assets/
│   └── app.ico                 # 窗口、任务栏与系统托盘图标（多分辨率 32/64/256 ICO）
├── src/
│   └── square_notes.py         # 主程序源码（单文件架构，零外部配置文件依赖）
├── docs/
│   ├── images/                 # 文档插图
│   ├── DEV_GUIDE.md            # 本二次开发手册
│   ├── USER_MANUAL_CN.docx     # 中文完整使用说明书
│   └── USER_MANUAL_EN.docx     # 英文完整使用说明书
├── examples/
│   └── sample_tasks.txt        # AI 速记测试用例
├── build.py                    # PyInstaller 打包脚本（输出完整发布目录）
└── requirements.txt            # 运行与开发依赖
```

### 2. 核心代码架构 (`src/square_notes.py`)

源码采用模块化面向对象结构，主要职责划分如下：

| 类 / 函数模块 | 核心职责 |
| :--- | :--- |
| **路径与资源适配** (`BASE_DIR`, `RESOURCE_DIR`, `resolve_app_path`, `to_relative_app_path`) | 区分程序运行物理目录（存放 `notes_data/`）与 PyInstaller `_MEIPASS` 临时解包目录（存放内置 `assets/app.ico`）；保存路径时自动转换为相对路径。 |
| **单实例守护** (`SINGLE_INSTANCE_PORT = 58763`) | 启动时绑定本地 TCP 回环端口；若端口已被占用则发送 `SHOW` 唤醒已有主控制台并安全退出。 |
| **图标与托盘加载** (`get_app_icon_path`, `apply_window_icon`, `create_tray_image`) | 优先加载 `assets/app.ico` 作为窗口与 `pystray` 托盘图标，缺失时自动回退至 PIL 矢量绘制图标。 |
| **时间与自然语言解析** (`convert_cn_numbers`, `parse_time_input`, `parse_fuzzy_date_anchor`, `compute_dynamic_fuzzy_label`) | 处理中文数字（如“一个半小时”、“一刻钟”）、复合时长单位、模糊日程锚点及跨天动态日期标签演化。 |
| **Win32 桌面底层能力** (`get_screen_monitors`, `set_window_mouse_transparent`, `mci_open_audio`) | 通过 `EnumDisplayMonitors` 与 `SetProcessDpiAwareness(2)` 适配多屏 DPI；通过 `SetWindowLongW(WS_EX_TRANSPARENT)` 实现鼠标点击穿透；通过 `winmm.dll` MCI 与 `GetShortPathNameW` 实现 MP3/WAV 精准片段播放。 |
| **`ToastNotification`** | 主屏幕右下角垂直堆叠式预警弹窗（橙色 5 分钟临期 / 红色到期），支持 10 秒自动销毁及单击静音。 |
| **`StickyNoteWindow`** | `175×175` 方形便签窗口实体，负责五色状态渲染、原位文字编辑、双击时间弹窗、拖拽事件转发与穿透锁定状态同步。 |
| **`NoteManager`** | 中枢控制器，负责控制台构建、I18N 中英热切换、`tick()` 定时刷新、`sort_and_arrange()` 三阶排序与自动换行、AI 异步请求线程与正则二次校准，以及 JSON 持久化。 |

### 3. 常见扩展接口与定制方法

1. **新增 AI 服务商预设**：
   在 `NoteManager.open_api_settings_dialog()` 的 `providers` 列表中追加元组：
   `(所属行 row_p1/row_p2, 按钮显示名称, OpenAI兼容接口URL, 默认模型名, 按钮背景色, 提示说明文案)`。
   若新增国内直连域名，可同步加入 `_ai_worker_thread()` 中的 `domestic_hosts` 列表以启用优先直连策略。
2. **自定义卡片尺寸与配色**：
   - 修改 `StickyNoteWindow.__init__` 中的 `self.size = 175` 以及 `NoteManager.sort_and_arrange()` 中的 `gap = 14`、`size = 175`；
   - 修改 `StickyNoteWindow._update_color()` 中的五套状态配色十六进制值。
3. **扩展界面语言 (I18N)**：
   在文件顶部 `I18N` 字典中新增语种键（如 `"ja"`），并在 `open_preferences_dialog()` 添加对应单选按钮即可实现热切换。
4. **替换自定义图标 (`assets/app.ico`)**：
   直接将新的多尺寸 `.ico` 文件（建议包含 `32×32`、`64×64`、`256×256`）覆盖保存为 `assets/app.ico`，源码运行与打包后的软件窗口、任务栏、系统托盘及 EXE 文件图标将同步更新。

### 4. 构建发布包 (`build.py`)

```bash
pip install -r requirements.txt
python build.py
```

脚本执行完毕后，将在 `dist/StickyNotes_AI_v3.3/` 下自动生成可直接压缩分发的完整目录：
- `StickyNotes_AI.exe`（单文件无黑框、内嵌 `assets/app.ico`）
- `USER_MANUAL_CN.docx`
- `USER_MANUAL_EN.docx`
- `sample_tasks.txt`

---

<a name="english-developer-guide"></a>
## English Developer Guide

### 1. Project Layout

```text
StickyNotes_AI_Release/
├── assets/
│   └── app.ico                 # Multi-size ICO (32/64/256) for EXE, windows & tray
├── src/
│   └── square_notes.py         # Core application source code
├── docs/
│   ├── images/                 # Documentation screenshots
│   ├── DEV_GUIDE.md            # This developer guide
│   ├── USER_MANUAL_CN.docx     # Chinese User Manual
│   └── USER_MANUAL_EN.docx     # English User Manual
├── examples/
│   └── sample_tasks.txt        # Natural-language prompt examples
├── build.py                    # PyInstaller release bundle script
└── requirements.txt            # Runtime & build dependencies
```

### 2. Core Architecture (`src/square_notes.py`)

- **Path & Resource Resolution (`BASE_DIR`, `RESOURCE_DIR`, `resolve_app_path`, `to_relative_app_path`)**: Separates the writable runtime folder (`notes_data/`) from PyInstaller's `_MEIPASS` extraction folder (`assets/app.ico`), converting project-local paths to portable relative paths upon saving.
- **Single-Instance Guard (`SINGLE_INSTANCE_PORT = 58763`)**: Binds localhost TCP port `58763`; duplicate launches send `"SHOW"` to restore the running console and exit immediately.
- **Icon & Tray Loader (`get_app_icon_path`, `apply_window_icon`, `create_tray_image`)**: Loads `assets/app.ico` for Tkinter `iconbitmap(default=...)` and `pystray` tray icons, with an automatic PIL-drawn fallback if the `.ico` is absent.
- **Natural-Language & Fuzzy Date Engine**: `convert_cn_numbers`, `parse_time_input`, `parse_fuzzy_date_anchor`, and `compute_dynamic_fuzzy_label` handle durations, mixed Chinese/English units, and dynamic midnight date rollovers.
- **Win32 Integration**:
  - Multi-monitor enumeration (`EnumDisplayMonitors`) + `SetProcessDpiAwareness(2)`;
  - Mouse click-through via `SetWindowLongW(GWL_EXSTYLE)` with `WS_EX_TRANSPARENT | WS_EX_LAYERED`;
  - Windows MCI audio playback (`winmm.dll`) with `GetShortPathNameW` 8.3 short paths for reliable Unicode filename support.
- **UI & Controller Classes**:
  - `ToastNotification`: Stacked bottom-right 5-minute warning and due alerts;
  - `StickyNoteWindow`: `175×175` square card view, inline title editing, double-click time editor, and click-through toggling;
  - `NoteManager`: Central coordinator managing the console bar, `I18N` hot-switching, 1-second `tick()`, 3-tier `sort_and_arrange()`, background AI API worker with regex calibration, and JSON persistence.

### 3. Extension Points

1. **Adding AI Provider Presets**: Append a tuple to `providers` inside `NoteManager.open_api_settings_dialog()`, and optionally add domestic hostnames to `domestic_hosts` inside `_ai_worker_thread()`.
2. **Customizing Card Size & Theme Colors**: Adjust `self.size = 175` in `StickyNoteWindow.__init__`, `size = 175` / `gap = 14` in `NoteManager.sort_and_arrange()`, and color hex codes in `StickyNoteWindow._update_color()`.
3. **Adding UI Languages**: Add a new locale dictionary entry in `I18N` and a corresponding radio button in `open_preferences_dialog()`.
4. **Replacing the App Icon**: Replace `assets/app.ico` with your own multi-resolution `.ico` file (`32×32`, `64×64`, `256×256` recommended). Both source runs and PyInstaller builds automatically pick it up for the EXE, taskbar, window titlebar, and system tray.

### 4. Building the Release Package (`build.py`)

```bash
pip install -r requirements.txt
python build.py
```

Outputs a ready-to-zip distribution folder at `dist/StickyNotes_AI_v3.3/` containing `StickyNotes_AI.exe`, `USER_MANUAL_CN.docx`, `USER_MANUAL_EN.docx`, and `sample_tasks.txt`.
