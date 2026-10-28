import os
import datetime
import cv2
import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QFrame, QMessageBox, QStatusBar
)

from database import DatabaseManager
from uart_controller import UARTController
from camera_controller import CameraController
from parking_manager import ParkingManager
from payment_qr import PaymentInfoServer

from .lane_widget import LaneWidget
from .logs_widget import LogsWidget
from .cards_widget import CardsWidget
from .settings_widget import SettingsWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HỆ THỐNG QUẢN LÝ BÃI GIỮ XE THÔNG MINH (ALPR + ESP32 UART)")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 700)

        # Apply dark aesthetic theme
        self.setStyleSheet("""
            QMainWindow { background-color: #020617; }
            QWidget { font-family: 'Segoe UI', Arial, sans-serif; }
            QTabWidget::pane {
                border: 1px solid #1E293B;
                background-color: #0F172A;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            QTabBar::tab {
                background-color: #0F172A;
                color: #94A3B8;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #1E293B;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background-color: #0284C7;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #1E293B;
                color: #E2E8F0;
            }
        """)

        # 1. Database & Core Controllers
        self.db = DatabaseManager()

        port = self.db.get_setting("serial_port", "COM3")
        if port in ("", "AUTO"):
            port = "COM3"
            self.db.set_setting("serial_port", port)
        baud = int(self.db.get_setting("baud_rate", "115200"))
        cam_src = self.db.get_setting("camera_index", "0")

        self.uart_ctrl = UARTController(port=port, baudrate=baud)
        self.camera_ctrl = CameraController(camera_source=cam_src)
        self.parking_mgr = ParkingManager(self.db)
        self.payment_server = PaymentInfoServer()
        self._simulation_entries = {}

        # 2. Main Layout UI
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header Bar with Live Stats & App Title
        header_bar = self._create_header_bar()
        main_layout.addWidget(header_bar)

        # Tab Widget
        self.tabs = QTabWidget()

        self.lane_widget = LaneWidget()
        self.logs_widget = LogsWidget(self.db)
        self.cards_widget = CardsWidget(self.db)
        self.settings_widget = SettingsWidget(self.db, self.uart_ctrl)

        self.tabs.addTab(self.lane_widget, " LÀN XE VÀO / RA ")
        self.tabs.addTab(self.logs_widget, " NHẬT KÝ GỬI XE ")
        self.tabs.addTab(self.cards_widget, " QUẢN LÝ THẺ RFID ")
        self.tabs.addTab(self.settings_widget, " CẤU HÌNH & GIẢ LẬP ESP32 ")

        main_layout.addWidget(self.tabs)

        # Connect Signals
        self._connect_signals()

        # Start background threads
        self.uart_ctrl.start()
        self.camera_ctrl.start()

        # Refresh stats timer
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.update_statistics)
        self.stats_timer.start(5000)
        self.update_statistics()

    def _create_header_bar(self) -> QFrame:
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #0F172A;
                border: 1px solid #1E293B;
                border-radius: 8px;
                padding: 6px 12px;
            }
        """)
        layout = QHBoxLayout(header)

        # App Title
        lbl_app_title = QLabel(" HỆ THỐNG QUẢN LÝ BÃI XE THÔNG MINH")
        lbl_app_title.setStyleSheet("color: #38BDF8; font-size: 18px; font-weight: bold;")
        layout.addWidget(lbl_app_title)

        layout.addStretch()

        # Stat Badges
        self.badge_in_park = QLabel("Đang trong bãi: 0 xe")
        self.badge_in_park.setStyleSheet("""
            background-color: #065F46; color: #34D399; font-weight: bold; padding: 6px 12px; border-radius: 6px; font-size: 13px;
        """)

        self.badge_revenue = QLabel("Doanh thu: 0 VNĐ")
        self.badge_revenue.setStyleSheet("""
            background-color: #1E3A8A; color: #60A5FA; font-weight: bold; padding: 6px 12px; border-radius: 6px; font-size: 13px;
        """)

        self.badge_uart = QLabel("ESP32: Đang kết nối...")
        self.badge_uart.setStyleSheet("""
            background-color: #334155; color: #94A3B8; font-weight: bold; padding: 6px 12px; border-radius: 6px; font-size: 13px;
        """)

        layout.addWidget(self.badge_in_park)
        layout.addWidget(self.badge_revenue)
        layout.addWidget(self.badge_uart)

        return header

    def _connect_signals(self):
        # Camera stream -> GUI update
        self.camera_ctrl.frame_received.connect(self.lane_widget.update_camera_frame)

        # UART RFID scan -> Parking Manager
        self.uart_ctrl.card_scanned_mode.connect(self.on_rfid_card_scanned)
        self.uart_ctrl.connection_status.connect(self.on_uart_status_changed)

        # Manual triggers from GUI
        self.lane_widget.trigger_barrier.connect(self.on_barrier_triggered)
        self.lane_widget.manual_tap.connect(self.on_manual_card_tap)
        self.settings_widget.simulate_tap.connect(self.on_simulation_card_tap)
        self.settings_widget.settings_saved.connect(self.on_settings_reloaded)

    def on_rfid_card_scanned(self, card_uid: str, mode: str = "AUTO"):
        """Called when an RFID card UID is received via UART or Simulator."""
        print(f"[Main Window] Processing RFID Card Scan UID: {card_uid} (Mode: {mode})")

        # Capture current camera snapshot
        frame = self.camera_ctrl.capture_frame()

        # Get mode from lane widget or ESP32 signal
        if mode in ["ENTRY", "EXIT"]:
            force_mode = mode
        else:
            mode_str = self.lane_widget.combo_mode.currentText()
            if "ENTRY" in mode_str:
                force_mode = "ENTRY"
            elif "EXIT" in mode_str:
                force_mode = "EXIT"
            else:
                force_mode = "AUTO"

        # Process parking entry/exit logic
        result = self.parking_mgr.process_card_tap(card_uid, frame, force_mode)

        # Update GUI lane widget display
        self.lane_widget.display_tap_result(result)

        # Send command to ESP32: Open specific barrier & update LCD screen
        if result.get("status_ok", True):
            op_type = result.get("type", "ENTRY")
            plate = result.get("plate", "KHONG_RO")

            if op_type == "ENTRY":
                self.uart_ctrl.send_command("CMD:GATE_IN_OPEN")
                self.uart_ctrl.send_command(f"LCD:TEXT:VAO: {plate}|XIN MOI VAO")
            else:
                try:
                    payment_url, payment_bill = self.payment_server.create_bill(result)
                    qr_image = self.payment_server.make_qr(payment_url)
                    self.lane_widget.display_payment_qr(qr_image, payment_url, payment_bill["amount"])
                except OSError as exc:
                    print(f"[Payment QR] Could not start payment page: {exc}")
                fee = result.get("fee", 0)
                self.uart_ctrl.send_command("CMD:GATE_OUT_OPEN")
                self.uart_ctrl.send_command(f"LCD:TEXT:RA: {plate}|PHI: {fee:,} VND")
        else:
            self.uart_ctrl.send_command("CMD:BEEP_ERROR")
            err_msg = result.get("message", "THE LOI")
            self.uart_ctrl.send_command(f"LCD:TEXT:CANH BAO|{err_msg}")

        # Refresh stats & table view
        self.update_statistics()
        self.logs_widget.load_data()


    def on_simulation_card_tap(self, card_uid: str):
        """Hardware-free demo: tap a sample UID once for entry, again for exit."""
        now = datetime.datetime.now()
        vehicle = "Car" if card_uid == "94B3C21C" else "Motorbike"
        plate = "51A-TEST" if vehicle == "Motorbike" else "51H-TEST"
        entry = self._simulation_entries.get(card_uid)

        if entry is None:
            entry_time = now - (datetime.timedelta(days=1) if card_uid == "NIGHT50000" else datetime.timedelta(minutes=10))
            self._simulation_entries[card_uid] = {"entry": entry_time, "vehicle": vehicle, "plate": plate}
            result = {
                "type": "ENTRY", "card_uid": card_uid, "plate": plate,
                "entry_time": entry_time.strftime("%H:%M:%S %d/%m/%Y"),
                "vehicle_type": vehicle, "status_ok": True, "crop_path": ""
            }
            print(f"[Simulation] {vehicle} entry demo for {card_uid}; tap again for exit/payment QR")
        else:
            entry_time = entry["entry"]
            overnight = entry_time.date() != now.date()
            fee = 50000 if overnight else (10000 if entry["vehicle"] == "Car" else 5000)
            result = {
                "type": "EXIT", "card_uid": card_uid, "plate_in": entry["plate"],
                "plate_out": entry["plate"], "entry_time": entry_time.strftime("%H:%M:%S %d/%m/%Y"),
                "exit_time": now.strftime("%H:%M:%S %d/%m/%Y"),
                "duration": "Qua đêm" if overnight else "0h 10m", "fee": fee,
                "vehicle_type": entry["vehicle"], "status_ok": True,
                "crop_path": "", "crop_out_path": "", "crop_in_path": ""
            }
            del self._simulation_entries[card_uid]
            payment_url, bill = self.payment_server.create_bill(result)
            qr_image = self.payment_server.make_qr(payment_url)
            self.lane_widget.display_payment_qr(qr_image, payment_url, bill["amount"])
            print(f"[Simulation] Exit demo: {fee:,} VND; QR page {payment_url}")

        self.lane_widget.display_tap_result(result)

    def on_manual_card_tap(self, card_uid: str, mode: str, image_override=None):
        print(f"[Manual Tap] UID={card_uid}, Mode={mode}, HasImageOverride={image_override is not None}")
        if image_override is not None:
            frame = image_override
        else:
            frame = self.camera_ctrl.capture_frame()

        result = self.parking_mgr.process_card_tap(card_uid, frame, mode)
        self.lane_widget.display_tap_result(result)
        if result.get("status_ok", True):
            self.uart_ctrl.send_command("CMD:GATE_OPEN")
        self.update_statistics()
        self.logs_widget.load_data()

    def on_barrier_triggered(self):
        sent = self.uart_ctrl.send_command("CMD:GATE_OPEN")
        if sent:
            QMessageBox.information(self, "Barrier Control", "Đã gửi lệnh MỞ CỔNG (CMD:GATE_OPEN) tới ESP32 UART.")
        else:
            QMessageBox.warning(self, "Barrier Control", "Không thể gửi lệnh qua UART. Kiểm tra kết nối cổng Serial.")

    def on_uart_status_changed(self, is_connected: bool, msg: str):
        if is_connected:
            self.badge_uart.setText(f"ESP32 UART: ONLINE ({self.uart_ctrl.port})")
            self.badge_uart.setStyleSheet("background-color: #065F46; color: #34D399; font-weight: bold; padding: 6px 12px; border-radius: 6px;")
        else:
            self.badge_uart.setText(f"ESP32 UART: OFFLINE")
            self.badge_uart.setStyleSheet("background-color: #991B1B; color: #F87171; font-weight: bold; padding: 6px 12px; border-radius: 6px;")

    def on_settings_reloaded(self):
        cam_src = self.db.get_setting("camera_index", "0")
        self.camera_ctrl.set_source(cam_src)
        self.update_statistics()

    def update_statistics(self):
        stats = self.db.get_statistics()
        in_park = stats["in_park_count"]
        revenue = stats["total_revenue"]

        self.badge_in_park.setText(f"Đang trong bãi: {in_park} xe")
        self.badge_revenue.setText(f"Doanh thu: {revenue:,} VNĐ")

    def closeEvent(self, event):
        """Cleanup threads when window closes."""
        print("[App Shutdown] Stopping camera and UART worker threads...")
        self.camera_ctrl.stop()
        self.uart_ctrl.stop()
        self.payment_server.close()
        event.accept()




