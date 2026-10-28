from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QGroupBox, QMessageBox, QTextEdit, QFrame
)
from database import DatabaseManager
from uart_controller import UARTController

class SettingsWidget(QWidget):
    settings_saved = pyqtSignal()
    simulate_tap = pyqtSignal(str) # (card_uid)

    def __init__(self, db: DatabaseManager, uart_ctrl: UARTController, parent=None):
        super().__init__(parent)
        self.db = db
        self.uart_ctrl = uart_ctrl
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # Left Column: Configuration Settings Form
        config_box = QGroupBox("Cấu Hình Hệ Thống & Bảng Giá")
        config_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold; font-size: 14px; color: #00E5FF;
                border: 1px solid #334155; border-radius: 8px; margin-top: 10px; padding-top: 15px;
                background-color: #0F172A;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 5px; }
        """)
        config_layout = QVBoxLayout(config_box)
        config_layout.setSpacing(10)

        # Serial UART Config
        lbl_port = QLabel("Cổng UART / COM (ESP32):")
        lbl_port.setStyleSheet("color: white; font-weight: bold;")
        self.combo_port = QComboBox()
        self.combo_port.setEditable(True)
        self.combo_port.setStyleSheet("background-color: #1E293B; color: white; padding: 6px; border-radius: 4px;")
        self.refresh_ports()

        lbl_baud = QLabel("Baud Rate:")
        lbl_baud.setStyleSheet("color: white; font-weight: bold;")
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["115200", "9600", "57600", "38400"])
        self.combo_baud.setStyleSheet("background-color: #1E293B; color: white; padding: 6px; border-radius: 4px;")

        # Camera Source Config
        lbl_cam = QLabel("Nguồn Camera (Webcam Index / RTSP URL / Path):")
        lbl_cam.setStyleSheet("color: white; font-weight: bold;")
        self.edit_cam = QLineEdit("0")
        self.edit_cam.setStyleSheet("background-color: #1E293B; color: white; padding: 6px; border-radius: 4px;")

        # Tariff Fees Config
        lbl_moto_base = QLabel("Phí Xe Máy (Block đầu):")
        lbl_moto_base.setStyleSheet("color: white; font-weight: bold;")
        self.edit_moto_base = QLineEdit("5000")
        self.edit_moto_base.setStyleSheet("background-color: #1E293B; color: #FACC15; padding: 6px; border-radius: 4px; font-weight: bold;")

        lbl_moto_hourly = QLabel("Phí Xe Máy (Mỗi giờ tiếp theo):")
        lbl_moto_hourly.setStyleSheet("color: white; font-weight: bold;")
        self.edit_moto_hourly = QLineEdit("2000")
        self.edit_moto_hourly.setStyleSheet("background-color: #1E293B; color: #FACC15; padding: 6px; border-radius: 4px;")

        lbl_car_base = QLabel("Phí Ô Tô (Block đầu):")
        lbl_car_base.setStyleSheet("color: white; font-weight: bold;")
        self.edit_car_base = QLineEdit("20000")
        self.edit_car_base.setStyleSheet("background-color: #1E293B; color: #FACC15; padding: 6px; border-radius: 4px; font-weight: bold;")

        lbl_car_hourly = QLabel("Phí Ô Tô (Mỗi giờ tiếp theo):")
        lbl_car_hourly.setStyleSheet("color: white; font-weight: bold;")
        self.edit_car_hourly = QLineEdit("10000")
        self.edit_car_hourly.setStyleSheet("background-color: #1E293B; color: #FACC15; padding: 6px; border-radius: 4px;")

        btn_save = QPushButton("LƯU CẤU HÌNH HỆ THỐNG")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #0284C7; color: white; font-size: 14px; font-weight: bold;
                padding: 10px; border-radius: 6px; margin-top: 10px;
            }
            QPushButton:hover { background-color: #0369A1; }
        """)
        btn_save.clicked.connect(self.save_settings)

        config_layout.addWidget(lbl_port)
        config_layout.addWidget(self.combo_port)
        config_layout.addWidget(lbl_baud)
        config_layout.addWidget(self.combo_baud)
        config_layout.addWidget(lbl_cam)
        config_layout.addWidget(self.edit_cam)
        config_layout.addWidget(lbl_moto_base)
        config_layout.addWidget(self.edit_moto_base)
        config_layout.addWidget(lbl_moto_hourly)
        config_layout.addWidget(self.edit_moto_hourly)
        config_layout.addWidget(lbl_car_base)
        config_layout.addWidget(self.edit_car_base)
        config_layout.addWidget(lbl_car_hourly)
        config_layout.addWidget(self.edit_car_hourly)
        config_layout.addWidget(btn_save)

        main_layout.addWidget(config_box, stretch=3)

        # Right Column: Virtual ESP32 Hardware Simulator
        sim_box = QGroupBox("Bộ Giả Lập ESP32 Hardware & UART Monitor")
        sim_box.setStyleSheet(config_box.styleSheet())
        sim_layout = QVBoxLayout(sim_box)
        sim_layout.setSpacing(10)

        lbl_sim_desc = QLabel("Mô phỏng không cần ESP32/camera: quẹt cùng thẻ mẫu một lần để xe vào, quẹt lại để xe ra và tạo QR thanh toán:")
        lbl_sim_desc.setWordWrap(True)
        lbl_sim_desc.setStyleSheet("color: #94A3B8; font-size: 12px;")
        sim_layout.addWidget(lbl_sim_desc)

        # Quick Test Cards Buttons
        test_buttons_layout = QHBoxLayout()

        btn_card1 = QPushButton("Quẹt Thẻ Xe Máy #1 (83F2A10B)")
        btn_card1.setStyleSheet("background-color: #334155; color: white; font-weight: bold; padding: 8px; border-radius: 6px;")
        btn_card1.clicked.connect(lambda: self.trigger_sim_tap("83F2A10B"))

        btn_card2 = QPushButton("Quẹt Thẻ Ô Tô #2 (94B3C21C)")
        btn_card2.setStyleSheet("background-color: #334155; color: white; font-weight: bold; padding: 8px; border-radius: 6px;")
        btn_card2.clicked.connect(lambda: self.trigger_sim_tap("94B3C21C"))

        test_buttons_layout.addWidget(btn_card1)
        test_buttons_layout.addWidget(btn_card2)

        btn_overnight = QPushButton("Thử xe qua đêm (50.000đ)")
        btn_overnight.setStyleSheet("background-color: #7C3AED; color: white; font-weight: bold; padding: 8px; border-radius: 6px;")
        btn_overnight.clicked.connect(lambda: self.trigger_sim_tap("NIGHT50000"))
        test_buttons_layout.addWidget(btn_overnight)
        sim_layout.addLayout(test_buttons_layout)

        # Custom UID simulation
        custom_layout = QHBoxLayout()
        self.edit_custom_uid = QLineEdit()
        self.edit_custom_uid.setPlaceholderText("Nhập UID tuỳ ý (VD: 12345678)...")
        self.edit_custom_uid.setStyleSheet("background-color: #1E293B; color: #FACC15; padding: 8px; border-radius: 4px; font-weight: bold;")

        btn_custom_tap = QPushButton("Giả Lập Quẹt")
        btn_custom_tap.setStyleSheet("background-color: #16A34A; color: white; font-weight: bold; padding: 8px 14px; border-radius: 4px;")
        btn_custom_tap.clicked.connect(lambda: self.trigger_sim_tap(self.edit_custom_uid.text()))

        custom_layout.addWidget(self.edit_custom_uid)
        custom_layout.addWidget(btn_custom_tap)
        sim_layout.addLayout(custom_layout)

        # UART Raw Terminal Log
        lbl_log = QLabel("Nhật Ký Truyền Nhận UART Raw:")
        lbl_log.setStyleSheet("color: white; font-weight: bold; margin-top: 10px;")
        self.log_terminal = QTextEdit()
        self.log_terminal.setReadOnly(True)
        self.log_terminal.setStyleSheet("""
            QTextEdit {
                background-color: #020617; color: #22C55E; font-family: monospace; font-size: 12px;
                border: 1px solid #1E293B; border-radius: 6px;
            }
        """)
        sim_layout.addWidget(lbl_log)
        sim_layout.addWidget(self.log_terminal)

        main_layout.addWidget(sim_box, stretch=3)

        # Connect UART controller raw log signal
        self.uart_ctrl.raw_data_received.connect(self.append_log)

    def refresh_ports(self):
        ports = UARTController.get_available_ports()
        self.combo_port.clear()
        self.combo_port.addItem("SIMULATOR (Virtual UART)")
        for p in ports:
            self.combo_port.addItem(p)

    def load_settings(self):
        saved_port = self.db.get_setting("serial_port", "COM3")
        if saved_port in ("", "AUTO"):
            saved_port = "COM3"
            self.db.set_setting("serial_port", saved_port)
        baud = self.db.get_setting("baud_rate", "115200")
        cam = self.db.get_setting("camera_index", "0")

        self.combo_port.setCurrentText(saved_port)
        self.combo_baud.setCurrentText(baud)
        self.edit_cam.setText(cam)

        self.edit_moto_base.setText(self.db.get_setting("motorbike_base_fee", "5000"))
        self.edit_moto_hourly.setText(self.db.get_setting("motorbike_hourly_fee", "2000"))
        self.edit_car_base.setText(self.db.get_setting("car_base_fee", "20000"))
        self.edit_car_hourly.setText(self.db.get_setting("car_hourly_fee", "10000"))

    def save_settings(self):
        port = self.combo_port.currentText().strip()
        baud = self.combo_baud.currentText().strip()
        cam = self.edit_cam.text().strip()

        self.db.set_setting("serial_port", port)
        self.db.set_setting("baud_rate", baud)
        self.db.set_setting("camera_index", cam)

        self.db.set_setting("motorbike_base_fee", self.edit_moto_base.text().strip())
        self.db.set_setting("motorbike_hourly_fee", self.edit_moto_hourly.text().strip())
        self.db.set_setting("car_base_fee", self.edit_car_base.text().strip())
        self.db.set_setting("car_hourly_fee", self.edit_car_hourly.text().strip())

        self.uart_ctrl.set_config(port, int(baud))
        self.settings_saved.emit()
        QMessageBox.information(self, "Thành công", "Đã lưu cấu hình hệ thống thành công.")

    def trigger_sim_tap(self, uid_str: str):
        uid = uid_str.strip().upper()
        if not uid:
            uid = "83F2A10B"
        self.simulate_tap.emit(uid)

    def append_log(self, text: str):
        self.log_terminal.append(text)




