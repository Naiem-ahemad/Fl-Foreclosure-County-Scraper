import os
import sys
import time
import shutil
import requests
import keyboard
import threading
from PySide6.QtGui import QIcon
from Merger import Auction_merger
from datetime import datetime, timedelta
from PySide6.QtCore import Slot , QObject
from PySide6.QtGui import QGuiApplication
from Scraper import Scraper, Calendar_scraper
from PySide6.QtQml import QQmlApplicationEngine

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class EmittingStream(QObject):
    from PySide6.QtCore import Signal    
    charWritten = Signal(str)
    lineClearRequest = Signal(int)  # emits how many lines to clear

    def __init__(self):
        super().__init__()
        if not os.path.exists("logs"):
            os.makedirs("logs")
        today = datetime.now().strftime("%Y-%m-%d")
        self.log_file_path = os.path.join("logs", f"{today}.log")
        self.log_file = open(self.log_file_path, "a", encoding="utf-8")

    def write(self, text):
        if text:
            self.charWritten.emit(text)
            self.log_file.write(text)
            self.log_file.flush()

    def flush(self):
        self.log_file.flush()

    def close(self):
        self.log_file.close()

class Backend(QObject):
    def __init__(self):
        super().__init__()
        
        self._scraping_lock = threading.Lock()
        self.scraping = False
        self.thread = None
        self.typing_done_flag = threading.Event()
        self.vpn_verified = False  # ✅ Track VPN verification


    @Slot()
    def notify_typing_done(self):
        self.typing_done_flag.set()

    @Slot()
    def start_scraping(self):
        with self._scraping_lock:
            if self.scraping:
                print("✅ Already scraping or finished.\n")
                return
            self.scraping = True
            self.vpn_verified = False

        def do_scraping():
            try:
                # 🔁 VPN check loop
                while not self.vpn_verified and self.scraping:
                    try:
                        response = requests.get("http://ip-api.com/json", timeout=5)
                        data = response.json()
                        country = data.get("country", "Unknown")
                    except Exception:
                        stream.charWritten.emit("⚠️ VPN check failed. Cannot determine location.\n")
                        self.retry_with_countdown("VPN check", 30)
                        continue

                    if country != "United States":
                        stream.charWritten.emit(f"⚠️ VPN not in US. Location: {country}\n")
                        self.retry_with_countdown("VPN check", 30)
                        continue
                    else:
                        self.vpn_verified = True
                        stream.charWritten.emit(f"✅ US VPN check passed. Location: {country}\n")
                        stream.lineClearRequest.emit(5)
                if not self.scraping:
                    return  # 🔚 If scraping was cancelled mid-retry

                # 🗓 Get auction date
                yesterday = datetime.now() - timedelta(days=1)
                AUCTION_DATE = yesterday.strftime("%m/%d/%Y")
                FOLDER_NAME = AUCTION_DATE.replace("/", "-")

                print(f"🔄 Starting scraping for auction date: {AUCTION_DATE}\n")

                try:
                    Calendar_scraper.main()
                    Scraper.main()
                    Auction_merger.main()
                except Exception as e:
                    print(f"⚠️ Error during scraping: {e}\n")
                    print("Press Enter To EXIT")

                print(f"\n🔄 Cleaning up folder: {FOLDER_NAME}")
                try:
                    shutil.rmtree(FOLDER_NAME)
                    print(f"✅ Folder deleted successfully.\n")
                    print("Press Enter To EXIT")
                except FileNotFoundError:
                    print(f"[-] Folder not found: {FOLDER_NAME}\n")
                    print("Press Enter To EXIT")
                except Exception as e:
                    print(f"⚠️ Error deleting folder {FOLDER_NAME}: {e}\n")
                    print("↩ Press Enter To EXIT")
            except Exception as e:
                stream.charWritten.emit(f"Error: {e}\n")

            finally:
                with self._scraping_lock:
                    self.scraping = False

        self.thread = threading.Thread(target=do_scraping, daemon=True)
        self.thread.start()
    def retry_with_countdown(self, reason, seconds):
        if self.vpn_verified or not self.scraping:
            stream.charWritten.emit(f"✅ {reason} retry aborted.\n")
            return

        # Clear and wait for typing done, but do not block indefinitely
        self.typing_done_flag.clear()
        self.typing_done_flag.wait(timeout=5)  # Wait a bit for previous typing to finish

        if self.vpn_verified or not self.scraping:
            stream.charWritten.emit(f"✅ {reason} retry aborted.\n")
            return

        # Send static message once to trigger typing animation on QML
        stream.charWritten.emit(f"[!] Retrying in (static)\n")

        for remaining in range(seconds, 0, -1):
            if self.vpn_verified or not self.scraping:
                stream.charWritten.emit(f"[✓] {reason} retry aborted.\n")
                return
            stream.charWritten.emit(f"[!] Retrying countdown {remaining}\n")
            time.sleep(1)

        # After countdown, emit a newline and wait for typing done before retrying
        stream.charWritten.emit("\n")
        self.typing_done_flag.clear()
        self.typing_done_flag.wait(timeout=5)

    @Slot()
    def force_quit(self):
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)

if __name__ == "__main__":

    app = QGuiApplication(sys.argv)

    icon_path = resource_path("assets/icon.ico")
    app.setWindowIcon(QIcon(icon_path))

    stream = EmittingStream()
    sys.stdout = stream
    sys.stderr = stream

    engine = QQmlApplicationEngine()
    backend = Backend()

    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("stream", stream)

    qml_file = resource_path("Animation/Animation.qml")
    engine.load(qml_file)
    if not engine.rootObjects():
        stream.close()
        sys.exit(-1)

    def handle_enter():
        stream.close()
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        os._exit(0)  # 🚪 Force close all threads & GUI

    def listen_for_enter():
        keyboard.wait("enter")
        handle_enter()

    threading.Thread(target=listen_for_enter, daemon=True).start()

    sys.exit(app.exec())
