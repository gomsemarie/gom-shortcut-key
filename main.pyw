import sys
import ctypes
import threading
import subprocess
import time
import json
import os
import shutil
from ctypes import wintypes
from PyQt5 import QtWidgets, uic, QtGui
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QFileDialog

CONFIG_FILE = "hotkey_config.json"

DEFAULT_HOTKEYS = {
    i + 1: {
        "mod": 0x0002,  # Ctrl
        "vk": 0x74 + i,  # F5~F12
        "text": f"Pressed Ctrl + F{5 + i}",
        "alias": f"Alias F{5 + i}"
    }
    for i in range(8)
}

HOTKEYS = DEFAULT_HOTKEYS.copy()
WM_HOTKEY = 0x0312

class HotkeyEmitter(QObject):
    triggered = pyqtSignal(str)

emitter = HotkeyEmitter()

notify_enabled = True

def load_config():
    global notify_enabled
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for k, v in data.get("hotkeys", {}).items():
                id = int(k)
                HOTKEYS[id]["text"] = v.get("text", HOTKEYS[id]["text"])
                HOTKEYS[id]["alias"] = v.get("alias", HOTKEYS[id]["alias"])
            notify_enabled = data.get("notify", True)

def save_config():
    data = {
        "hotkeys": {
            str(k): {
                "text": HOTKEYS[k]["text"],
                "alias": HOTKEYS[k]["alias"]
            } for k in HOTKEYS
        },
        "notify": notify_enabled
    }
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def set_clipboard_text(text):
    process = subprocess.Popen('clip', stdin=subprocess.PIPE, shell=True)
    process.communicate(input=text.encode('utf-16le'))

def listen_hotkeys():
    user32 = ctypes.windll.user32
    for id, info in HOTKEYS.items():
        if not user32.RegisterHotKey(None, id, info["mod"], info["vk"]):
        #     emitter.triggered.emit(f"[ SYSTEM ] 단축키 등록 성공: {info["alias"]}")
        # else:
            emitter.triggered.emit(f"[ SYSTEM ] 단축키 등록 실패: {info["alias"]}")
    try:
        msg = wintypes.MSG()
        while True:
            if user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == WM_HOTKEY:
                    hotkey_id = msg.wParam
                    if hotkey_id in HOTKEYS:
                        text = HOTKEYS[hotkey_id]["text"]
                        alias = HOTKEYS[hotkey_id]["alias"]
                        set_clipboard_text(text)
                        emitter.triggered.emit(f"[ {alias} ] {text}")
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        for id in HOTKEYS.keys():
            ctypes.windll.user32.UnregisterHotKey(None, id)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("shortcut.ui", self)
        self.textEdit.append("단축키를 누르면 문자열이 클립보드에 복사됩니다.")
        emitter.triggered.connect(self.display_message)
        self.saveButton.clicked.connect(self.save_settings)
        self.fileButton.clicked.connect(self.list_files_in_directory)

        self.input_fields = {}
        for i in range(8):
            fn = 5 + i
            idx = i + 1
            self.input_fields[idx] = {
                "text": self.findChild(QtWidgets.QLineEdit, f"lineEditF{fn}"),
                "alias": self.findChild(QtWidgets.QLineEdit, f"aliasF{fn}")
            }

        self.checkBoxNotify.toggled.connect(self.toggle_notify)

        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        self.tray_icon.setIcon(QtGui.QIcon("gom-icon.png"))
        self.tray_menu = QtWidgets.QMenu()

        show_action = self.tray_menu.addAction("보이기")
        hide_action = self.tray_menu.addAction("숨기기")
        quit_action = self.tray_menu.addAction("종료")

        show_action.triggered.connect(self.show)
        hide_action.triggered.connect(self.hide)
        quit_action.triggered.connect(QtWidgets.qApp.quit)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

        self.load_settings()

    def toggle_notify(self, state):
        global notify_enabled
        notify_enabled = state

    def on_tray_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.DoubleClick:
            self.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        if notify_enabled:
            self.tray_icon.showMessage(
                "단축키 앱",
                "백그라운드에서 계속 실행 중입니다.",
                QtWidgets.QSystemTrayIcon.Information,
                3000
            )

    def display_message(self, msg):
        self.textEdit.append(msg)
        if notify_enabled:
            self.tray_icon.showMessage("단축키 입력됨", msg, QtWidgets.QSystemTrayIcon.Information, 2000)

    def load_settings(self):
        load_config()
        for idx, fields in self.input_fields.items():
            fields["text"].setText(HOTKEYS[idx]["text"])
            fields["alias"].setText(HOTKEYS[idx]["alias"])
        self.checkBoxNotify.setChecked(notify_enabled)

    def save_settings(self):
        for idx, fields in self.input_fields.items():
            HOTKEYS[idx]["text"] = fields["text"].text()
            HOTKEYS[idx]["alias"] = fields["alias"].text()
        save_config()
        self.textEdit.append("설정이 저장되었습니다.")

    def list_files_in_directory(self):
        folder_path = "D:\Source\Python\gom-shortcut-key" # QFileDialog.getExistingDirectory(self, "폴더 선택")
        if folder_path:
            try:
                # .zip 파일 목록 가져오기
                zip_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".zip")]
                if not zip_files:
                    QMessageBox.information(self, "알림", "📦 .zip 파일이 없습니다.")
                    return
                # 가장 최근 파일 선택
                zip_files_with_mtime = [
                    (f, os.path.getmtime(os.path.join(folder_path, f))) for f in zip_files
                ]
                latest_file = max(zip_files_with_mtime, key=lambda x: x[1])[0]
                src_path = os.path.join(folder_path, latest_file)

                # 다운로드 폴더 경로
                downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
                dst_path = os.path.join(downloads_path, latest_file)

                # 복사
                shutil.copy2(src_path, dst_path)

                # 로그 출력
                self.textEdit.append(f"✅ 최신 zip 파일 '{latest_file}'을(를) 다운로드 폴더로 복사했습니다.")
                # self.textEdit.append(f"📁 '{folder_path}'의 파일 목록:\n{file_list}\n")
            except Exception as e:
                self.textEdit.append(f"❌ 에러 발생: {e}")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    threading.Thread(target=listen_hotkeys, daemon=True).start()
    sys.exit(app.exec_())
