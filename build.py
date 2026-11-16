"""
StickyNotes_AI 开源发布版打包脚本
在 dist/StickyNotes_AI_v3.3/ 下生成带图标的纯净版 StickyNotes_AI.exe，
并自动附带中英双语 Word 说明书与示例测试文本，方便直接压缩发布。
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
RELEASE_DIR = os.path.join(ROOT_DIR, "dist", "StickyNotes_AI_v3.3")


def main():
    for required in (SRC_ENTRY, ICON_PATH, MANUAL_CN, MANUAL_EN, SAMPLE_TXT):
        if not os.path.exists(required):
            raise FileNotFoundError(f"缺少发布所需文件: {required}")

    if os.path.exists(RELEASE_DIR):
        shutil.rmtree(RELEASE_DIR)
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

    print("Building clean release StickyNotes_AI.exe ...")
    subprocess.run(cmd, check=True, cwd=ROOT_DIR)

    # 复制随包附带的说明书与示例文本
    shutil.copy2(MANUAL_CN, os.path.join(RELEASE_DIR, "USER_MANUAL_CN.docx"))
    shutil.copy2(MANUAL_EN, os.path.join(RELEASE_DIR, "USER_MANUAL_EN.docx"))
    shutil.copy2(SAMPLE_TXT, os.path.join(RELEASE_DIR, "sample_tasks.txt"))

    exe_path = os.path.join(RELEASE_DIR, "StickyNotes_AI.exe")
    print(f"Release package ready at: {RELEASE_DIR}")
    print(f"  - StickyNotes_AI.exe ({os.path.getsize(exe_path)} bytes)")
    print("  - USER_MANUAL_CN.docx")
    print("  - USER_MANUAL_EN.docx")
    print("  - sample_tasks.txt")


if __name__ == "__main__":
    main()
