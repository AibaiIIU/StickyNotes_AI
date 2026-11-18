"""
StickyNotes_AI 开源发布版打包脚本 (v3.4)
在 dist/StickyNotes_AI_v3.4/ 下生成带图标的纯净版 StickyNotes_AI.exe，
自动清理旧的 v3.3 构建目录，并附带中英双语 Word 说明书、示例测试文本与 MIT LICENSE。
"""

import os
import shutil
import subprocess
import sys

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_ENTRY = os.path.join(ROOT_DIR, "src", "square_notes.py")
ICON_PATH = os.path.join(ROOT_DIR, "assets", "app.ico")
MANUAL_CN = os.path.join(ROOT_DIR, "docs", "USER_MANUAL_CN.docx")
MANUAL_EN = os.path.join(ROOT_DIR, "docs", "USER_MANUAL_EN.docx")
SAMPLE_TXT = os.path.join(ROOT_DIR, "examples", "sample_tasks.txt")
LICENSE_FILE = os.path.join(ROOT_DIR, "LICENSE")
DIST_ROOT = os.path.join(ROOT_DIR, "dist")
RELEASE_DIR = os.path.join(DIST_ROOT, "StickyNotes_AI_v3.4")


def safe_copy(src, dst):
    try:
        shutil.copy2(src, dst)
    except PermissionError:
        if os.path.exists(dst):
            print(f"  [Skipped locked file, already exists]: {os.path.basename(dst)}")
        else:
            raise


def main():
    for required in (SRC_ENTRY, ICON_PATH, MANUAL_CN, MANUAL_EN, SAMPLE_TXT, LICENSE_FILE):
        if not os.path.exists(required):
            raise FileNotFoundError(f"缺少发布所需文件: {required}")

    # 清理旧版本发布目录与压缩包
    for old_item in ("StickyNotes_AI_v3.3", "StickyNotes_AI_v3.3_Win64.zip"):
        old_path = os.path.join(DIST_ROOT, old_item)
        if os.path.isdir(old_path):
            shutil.rmtree(old_path, ignore_errors=True)
        elif os.path.exists(old_path):
            os.remove(old_path)

    if os.path.exists(RELEASE_DIR):
        old_exe = os.path.join(RELEASE_DIR, "StickyNotes_AI.exe")
        if os.path.exists(old_exe):
            os.remove(old_exe)
        old_notes = os.path.join(RELEASE_DIR, "notes_data")
        if os.path.isdir(old_notes):
            shutil.rmtree(old_notes)
        try:
            shutil.rmtree(RELEASE_DIR)
        except PermissionError:
            pass
    os.makedirs(RELEASE_DIR, exist_ok=True)

    sep = os.pathsep
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "StickyNotes_AI",
        "--icon",
        ICON_PATH,
        "--distpath",
        RELEASE_DIR,
        "--workpath",
        os.path.join(ROOT_DIR, "build", "work"),
        "--specpath",
        os.path.join(ROOT_DIR, "build"),
        "--hidden-import",
        "pystray._win32",
        "--hidden-import",
        "PIL._tkinter_finder",
        "--add-data",
        f"{ICON_PATH}{sep}assets",
        SRC_ENTRY,
    ]

    print("Building clean release StickyNotes_AI.exe (v3.4) ...")
    subprocess.run(cmd, check=True, cwd=ROOT_DIR)

    # 复制随包附带的说明书、示例文本与开源协议
    safe_copy(MANUAL_CN, os.path.join(RELEASE_DIR, "USER_MANUAL_CN.docx"))
    safe_copy(MANUAL_EN, os.path.join(RELEASE_DIR, "USER_MANUAL_EN.docx"))
    safe_copy(SAMPLE_TXT, os.path.join(RELEASE_DIR, "sample_tasks.txt"))
    safe_copy(LICENSE_FILE, os.path.join(RELEASE_DIR, "LICENSE"))

    exe_path = os.path.join(RELEASE_DIR, "StickyNotes_AI.exe")
    print(f"Release package ready at: {RELEASE_DIR}")
    print(f"  - StickyNotes_AI.exe ({os.path.getsize(exe_path)} bytes)")
    print("  - USER_MANUAL_CN.docx")
    print("  - USER_MANUAL_EN.docx")
    print("  - sample_tasks.txt")
    print("  - LICENSE")


if __name__ == "__main__":
    main()
