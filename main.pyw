import sys
import ctypes
import threading
import subprocess
import time
import json
import os
import shutil
import re # ver 1.2
from ctypes import wintypes
from PyQt5 import QtWidgets, uic, QtGui
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import QTimer # ver 1.2

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
            emitter.triggered.emit(f"[ SYSTEM ] 단축키 등록 실패: {info['alias']}")
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
        self.start_version_check_timer() # ver 1.2

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

    # def list_files_in_directory(self):
    #     folder_path = "D:\Source\Python\gom-shortcut-key" # QFileDialog.getExistingDirectory(self, "폴더 선택")
    #     if folder_path:
    #         try:
    #             # .zip 파일 목록 가져오기
    #             zip_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".zip")]
    #             if not zip_files:
    #                 QMessageBox.information(self, "알림", "📦 .zip 파일이 없습니다.")
    #                 return
    #             # 가장 최근 파일 선택
    #             zip_files_with_mtime = [
    #                 (f, os.path.getmtime(os.path.join(folder_path, f))) for f in zip_files
    #             ]
    #             latest_file = max(zip_files_with_mtime, key=lambda x: x[1])[0]
    #             src_path = os.path.join(folder_path, latest_file)

    #             # 다운로드 폴더 경로
    #             downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
    #             dst_path = os.path.join(downloads_path, latest_file)

    #             # 복사
    #             shutil.copy2(src_path, dst_path)

    #             # 로그 출력
    #             self.textEdit.append(f"✅ 최신 zip 파일 '{latest_file}'을(를) 다운로드 폴더로 복사했습니다.")
    #             # self.textEdit.append(f"📁 '{folder_path}'의 파일 목록:\n{file_list}\n")
    #         except Exception as e:
    #             self.textEdit.append(f"❌ 에러 발생: {e}")

    # ver 1.2
    def list_files_in_directory(self):
        folder_path = r"D:\Source\Python\test-extension"
        installed_path = r"D:\Source\Python\test-installed"
        target_folder_name = "gom-extension"
        final_dest_path = os.path.join(installed_path, target_folder_name)

        if not os.path.exists(folder_path):
            QMessageBox.warning(self, "경고", "📁 대상 폴더가 존재하지 않습니다.")
            return

        try:
            # gom-extension-x.x.x 형식 필터링
            pattern = re.compile(r"^gom-extension-(\d+\.\d+\.\d+)$")
            versioned_folders = []

            for name in os.listdir(folder_path):
                full_path = os.path.join(folder_path, name)
                if os.path.isdir(full_path):
                    match = pattern.match(name)
                    if match:
                        version_str = match.group(1)
                        version_tuple = tuple(map(int, version_str.split('.')))
                        versioned_folders.append((version_tuple, full_path))

            if not versioned_folders:
                QMessageBox.information(self, "알림", "📂 'gom-extension-x.x.x' 폴더가 없습니다.")
                return

            # 최신 버전 폴더 선택
            latest_version, latest_folder = max(versioned_folders, key=lambda x: x[0])

            # 대상 경로가 존재하면 삭제
            if os.path.exists(final_dest_path):
                shutil.rmtree(final_dest_path)

            # 복사 (폴더 이름을 gom-extension 으로 변경)
            shutil.copytree(latest_folder, final_dest_path)

            self.textEdit.append(
                f"✅ 최신 폴더 '{os.path.basename(latest_folder)}'를 '{final_dest_path}'로 복사했습니다."
            )

        except Exception as e:
            self.textEdit.append(f"❌ 에러 발생: {e}")

    # ver 1.2
    def is_latest(self, folder_path, installed_path):
        try:
            # (1) folder_path에서 가장 높은 버전의 gom-extension-x.x.x 폴더 찾기
            pattern = re.compile(r'^gom-extension-(\d+)\.(\d+)\.(\d+)$')
            latest_version_tuple = None
            latest_version_str = ""

            for name in os.listdir(folder_path):
                full_path = os.path.join(folder_path, name)
                match = pattern.match(name)
                if match and os.path.isdir(full_path):
                    version_tuple = tuple(map(int, match.groups()))
                    if not latest_version_tuple or version_tuple > latest_version_tuple:
                        latest_version_tuple = version_tuple
                        latest_version_str = ".".join(map(str, version_tuple))

            if not latest_version_tuple:
                print("❌ 최신 버전 폴더를 찾을 수 없습니다.")
                return (False, "", "")

            # (2) 설치된 폴더에서 manifest.json 읽기
            manifest_path = os.path.join(installed_path, "gom-extension", "manifest.json")
            if not os.path.exists(manifest_path):
                print("⚠️ 설치된 manifest.json 파일이 없습니다.")
                return (False, "", latest_version_str)

            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)

            installed_version_str = manifest_data.get("version", "")
            if not installed_version_str:
                print("⚠️ manifest.json에 'version' 항목이 없습니다.")
                return (False, "", latest_version_str)

            installed_version_tuple = tuple(map(int, installed_version_str.split(".")))

            # (3) 비교 후 반환
            is_up_to_date = installed_version_tuple >= latest_version_tuple
            return (is_up_to_date, installed_version_str, latest_version_str)

        except Exception as e:
            print(f"❌ 에러 발생: {e}")
    
    # ver 1.2
    def start_version_check_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_version_periodically)
        self.timer.start(5000)  # 5초 (5000ms) 간격

    # ver 1.2
    def check_version_periodically(self):
        folder_path = r"D:\Source\Python\test-extension"
        installed_path = r"D:\Source\Python\test-installed"

        is_latest_flag, installed_ver, latest_ver = self.is_latest(folder_path, installed_path)
        if not is_latest_flag:
            msg = f"🔔 새로운 버전이 있습니다!\n설치됨: {installed_ver}\n최신: {latest_ver}"
            self.display_message(msg)
        else:
            msg = f"최신 버전입니다: {latest_ver}"
            self.display_message(msg)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    threading.Thread(target=listen_hotkeys, daemon=True).start()
    sys.exit(app.exec_())
