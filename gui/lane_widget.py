import os
import cv2
import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QImage, QPixmap, QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog,
    QComboBox, QLineEdit, QGroupBox, QFrame, QMessageBox, QFileDialog, QSplitter
)

class LaneWidget(QWidget):
    # Signal emitted when barrier open command should be sent
    trigger_barrier = pyqtSignal()
    # Signal (card_uid, mode, image_override)
    manual_tap = pyqtSignal(str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # Left Column: Live Camera & Controls
        left_box = QGroupBox("Camera Trực Tiếp & Làn Xe")
        left_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #00E5FF;
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #0F172A;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """)
        left_layout = QVBoxLayout(left_box)

        # Camera Display Frame
        self.camera_label = QLabel()
        self.camera_label.setMinimumSize(640, 440)
        self.camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_label.setText("ĐANG KẾT NỐI CAMERA STREAM...")
        self.camera_label.setStyleSheet("""
            QLabel {
                background-color: #020617;
                border: 2px solid #1E293B;
                border-radius: 10px;
                color: #94A3B8;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        left_layout.addWidget(self.camera_label, stretch=4)

        # Control Bar below Camera
        control_bar = QHBoxLayout()

        # Mode Selector (Auto / Entry / Exit)
        lbl_mode = QLabel("Chế độ Làn:")
        lbl_mode.setStyleSheet("color: #E2E8F0; font-weight: bold;")
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["TỰ ĐỘNG (AUTO)", "XE VÀO (ENTRY)", "XE RA (EXIT)"])
        self.combo_mode.setStyleSheet("""
            QComboBox {
                background-color: #1E293B;
                color: #FFFFFF;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
        """)

        # Manual Snapshot & Image File Test Buttons
        self.btn_capture = QPushButton("Chụp & Quẹt Thẻ Mẫu")
        self.btn_capture.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #0369A1; }
        """)
        self.btn_capture.clicked.connect(self._on_manual_capture_clicked)

        self.btn_load_image = QPushButton("Nạp Ảnh Đĩa...")
        self.btn_load_image.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        self.btn_load_image.clicked.connect(self._on_load_file_clicked)

        control_bar.addWidget(lbl_mode)
        control_bar.addWidget(self.combo_mode)
        control_bar.addWidget(self.btn_capture)
        control_bar.addWidget(self.btn_load_image)
        left_layout.addLayout(control_bar)

        main_layout.addWidget(left_box, stretch=3)

        # Right Column: OCR Result, Entry/Exit Info & Barrier Control
        right_box = QGroupBox("Kết Quả Nhận Diện Biển Số & Quẹt Thẻ")
        right_box.setStyleSheet(left_box.styleSheet())
        right_layout = QVBoxLayout(right_box)
        right_layout.setSpacing(12)

        # Status Banner
        self.lbl_banner = QLabel("SẴN SÀNG QUẸT THẺ")
        self.lbl_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_banner.setStyleSheet("""
            QLabel {
                background-color: #1E293B;
                color: #38BDF8;
                font-size: 16px;
                font-weight: bold;
                padding: 10px;
                border-radius: 6px;
                border: 1px solid #334155;
            }
        """)
        right_layout.addWidget(self.lbl_banner)

        # RFID Card UID Display
        card_layout = QHBoxLayout()
        lbl_card_title = QLabel("UID Thẻ Quẹt:")
        lbl_card_title.setStyleSheet("color: #94A3B8; font-size: 13px; font-weight: bold;")
        self.edit_card_uid = QLineEdit()
        self.edit_card_uid.setPlaceholderText("Nhập hoặc chờ quét thẻ...")
        self.edit_card_uid.setStyleSheet("""
            QLineEdit {
                background-color: #0F172A;
                color: #FACC15;
                font-size: 16px;
                font-weight: bold;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        card_layout.addWidget(lbl_card_title)
        card_layout.addWidget(self.edit_card_uid)
        right_layout.addLayout(card_layout)

        # Cropped License Plate Image Preview
        self.crop_label = QLabel()
        self.crop_label.setFixedSize(260, 110)
        self.crop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.crop_label.setText("Ảnh Cắt Biển Số")
        self.crop_label.setStyleSheet("""
            QLabel {
                background-color: #020617;
                border: 2px dashed #475569;
                border-radius: 8px;
                color: #64748B;
            }
        """)
        crop_container = QHBoxLayout()
        crop_container.addStretch()
        crop_container.addWidget(self.crop_label)
        crop_container.addStretch()
        right_layout.addLayout(crop_container)

        # OCR Plate Result Display & Edit
        plate_layout = QVBoxLayout()
        lbl_plate_title = QLabel("Biển Số Xe Nhận Diện (OCR):")
        lbl_plate_title.setStyleSheet("color: #94A3B8; font-size: 13px; font-weight: bold;")
        self.edit_plate = QLineEdit()
        self.edit_plate.setPlaceholderText("Biển số xe...")
        self.edit_plate.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit_plate.setStyleSheet("""
            QLineEdit {
                background-color: #020617;
                color: #4ADE80;
                font-size: 24px;
                font-weight: bold;
                border: 2px solid #22C55E;
                border-radius: 8px;
                padding: 8px;
                letter-spacing: 2px;
            }
        """)
        plate_layout.addWidget(lbl_plate_title)
        plate_layout.addWidget(self.edit_plate)
        right_layout.addLayout(plate_layout)

        # Parking Info Grid (Duration, Fee, Match Status)
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #1E293B;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        info_grid = QVBoxLayout(info_frame)

        self.lbl_time_in = QLabel("Thời gian vào: --:--:--")
        self.lbl_time_out = QLabel("Thời gian ra: --:--:--")
        self.lbl_duration = QLabel("Thời lượng gửi: --")
        self.lbl_fee = QLabel("Phí gửi xe: 0 VNĐ")

        for lbl in [self.lbl_time_in, self.lbl_time_out, self.lbl_duration]:
            lbl.setStyleSheet("color: #CBD5E1; font-size: 13px;")
            info_grid.addWidget(lbl)

        self.lbl_fee.setStyleSheet("color: #F59E0B; font-size: 20px; font-weight: bold; margin-top: 4px;")
        info_grid.addWidget(self.lbl_fee)

        right_layout.addWidget(info_frame)

        # Barrier Command Control Button
        self.btn_barrier = QPushButton("MỞ CỔNG BARRIER (UART)")
        self.btn_barrier.setMinimumHeight(45)
        self.btn_barrier.setStyleSheet("""
            QPushButton {
                background-color: #16A34A;
                color: white;
                font-size: 15px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #15803D; }
        """)
        self.btn_barrier.clicked.connect(lambda: self.trigger_barrier.emit())
        right_layout.addWidget(self.btn_barrier)

        main_layout.addWidget(right_box, stretch=2)

    def display_payment_qr(self, image: np.ndarray, url: str, amount: int):
        if hasattr(self, "payment_dialog") and self.payment_dialog is not None:
            self.payment_dialog.close()

        rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB) if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()

        self.payment_dialog = QDialog(self)
        self.payment_dialog.setWindowTitle("QR thanh toán")
        self.payment_dialog.setFixedSize(380, 430)
        layout = QVBoxLayout(self.payment_dialog)
        title = QLabel(f"Quét mã để xem số tiền: {amount:,} VNĐ")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #0F172A; padding: 8px;")
        qr = QLabel()
        qr.setFixedSize(300, 300)
        qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr.setStyleSheet("background: white; padding: 8px;")
        qr.setPixmap(QPixmap.fromImage(qimg).scaled(280, 280, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation))
        link = QLabel(f"Điện thoại cần cùng Wi-Fi.\\n{url}")
        link.setWordWrap(True)
        link.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(qr, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(link)
        self.payment_dialog.show()

    def clear_payment_qr(self):
        if hasattr(self, "payment_dialog") and self.payment_dialog is not None:
            self.payment_dialog.close()
            self.payment_dialog = None
    def update_camera_frame(self, cv_img: np.ndarray):
        """Receives BGR numpy array from CameraController or Image Loader and updates GUI QLabel."""
        if cv_img is None or cv_img.size == 0:
            return

        h, w, ch = cv_img.shape
        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        bytes_per_line = ch * w
        q_img = QImage(rgb_img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

        pixmap = QPixmap.fromImage(q_img).scaled(
            self.camera_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.camera_label.setPixmap(pixmap)

    def display_tap_result(self, result: dict):
        """Displays processing output when a card is tapped."""
        is_entry = (result.get("type") == "ENTRY")
        status_ok = result.get("status_ok", True)

        card_uid = result.get("card_uid", "")
        self.edit_card_uid.setText(card_uid)

        # Update Banner
        if is_entry:
            self.clear_payment_qr()
            self.lbl_banner.setText("XE VÀO BÃI")
            self.lbl_banner.setStyleSheet("""
                QLabel {
                    background-color: #065F46; color: #34D399; font-size: 16px; font-weight: bold; padding: 10px; border-radius: 6px;
                }
            """)
            plate = result.get("plate", "")
            self.edit_plate.setText(plate)
            self.lbl_time_in.setText(f"Thời gian vào: {result.get('entry_time', '')}")
            self.lbl_time_out.setText("Thời gian ra: --:--:--")
            self.lbl_duration.setText("Thời lượng gửi: Đang gửi")
            self.lbl_fee.setText("Phí gửi xe: -- VNĐ")
        else:
            plate_out = result.get("plate_out", "")
            self.edit_plate.setText(plate_out)
            self.lbl_time_in.setText(f"Thời gian vào: {result.get('entry_time', '')}")
            self.lbl_time_out.setText(f"Thời gian ra: {result.get('exit_time', '')}")
            self.lbl_duration.setText(f"Thời lượng gửi: {result.get('duration', '')}")
            fee = result.get("fee", 0)
            self.lbl_fee.setText(f"Phí gửi xe: {fee:,} VNĐ")

            if status_ok:
                self.lbl_banner.setText("XE RA - HỢP LỆ")
                self.lbl_banner.setStyleSheet("""
                    QLabel {
                        background-color: #1E3A8A; color: #60A5FA; font-size: 16px; font-weight: bold; padding: 10px; border-radius: 6px;
                    }
                """)
            else:
                self.lbl_banner.setText("CẢNH BÁO: KHÔNG KHỚP BIỂN SỐ")
                self.lbl_banner.setStyleSheet("""
                    QLabel {
                        background-color: #991B1B; color: #F87171; font-size: 16px; font-weight: bold; padding: 10px; border-radius: 6px;
                    }
                """)

        # Display Cropped Plate
        crop_path = result.get("crop_path") or result.get("crop_out_path") or result.get("crop_in_path")
        if crop_path and os.path.exists(crop_path):
            pix = QPixmap(crop_path).scaled(
                self.crop_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.crop_label.setPixmap(pix)

    def _on_manual_capture_clicked(self):
        uid = self.edit_card_uid.text().strip() or "A1B2C3D4"
        mode_str = self.combo_mode.currentText()
        if "ENTRY" in mode_str:
            mode = "ENTRY"
        elif "EXIT" in mode_str:
            mode = "EXIT"
        else:
            mode = "AUTO"
        self.manual_tap.emit(uid, mode, None)

    def _on_load_file_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh xe", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            img = cv2.imread(file_path)
            if img is not None:
                self.update_camera_frame(img)
                uid = self.edit_card_uid.text().strip() or "FILE_TEST"
                mode_str = self.combo_mode.currentText()
                if "ENTRY" in mode_str:
                    mode = "ENTRY"
                elif "EXIT" in mode_str:
                    mode = "EXIT"
                else:
                    mode = "AUTO"
                self.manual_tap.emit(uid, mode, img)





