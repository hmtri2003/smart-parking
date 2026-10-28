from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QComboBox, QLabel, QHeaderView, QMessageBox, QGroupBox
)
from database import DatabaseManager

class CardsWidget(QWidget):
    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.init_ui()
        self.load_cards()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # Left Column: Table of cards
        table_box = QGroupBox("Danh Sách Thẻ RFID Đã Đăng Ký")
        table_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold; font-size: 14px; color: #00E5FF;
                border: 1px solid #334155; border-radius: 8px; margin-top: 10px; padding-top: 15px;
                background-color: #0F172A;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 5px; }
        """)
        table_layout = QVBoxLayout(table_box)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["UID Thẻ", "Tên Chủ Thẻ", "Loại Xe Default", "Trạng Thái", "Ngày Đăng Ký"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0F172A; color: #E2E8F0; gridline-color: #334155; font-size: 13px; border: 1px solid #1E293B;
            }
            QHeaderView::section {
                background-color: #1E293B; color: #38BDF8; font-weight: bold; padding: 8px; border: 1px solid #334155;
            }
        """)
        self.table.itemClicked.connect(self.on_table_item_clicked)
        table_layout.addWidget(self.table)

        layout.addWidget(table_box, stretch=3)

        # Right Column: Add/Edit Card Form
        form_box = QGroupBox("Cập Nhật Thông Tin Thẻ RFID")
        form_box.setStyleSheet(table_box.styleSheet())
        form_layout = QVBoxLayout(form_box)
        form_layout.setSpacing(12)

        lbl_uid = QLabel("UID Thẻ RFID:")
        lbl_uid.setStyleSheet("color: white; font-weight: bold;")
        self.edit_uid = QLineEdit()
        self.edit_uid.setPlaceholderText("VD: A1B2C3D4...")
        self.edit_uid.setStyleSheet("background-color: #1E293B; color: #FACC15; padding: 8px; border-radius: 4px; font-weight: bold;")

        lbl_name = QLabel("Tên Khách Hàng / Chủ Thẻ:")
        lbl_name.setStyleSheet("color: white; font-weight: bold;")
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("VD: Nguyễn Văn A...")
        self.edit_name.setStyleSheet("background-color: #1E293B; color: white; padding: 8px; border-radius: 4px;")

        lbl_type = QLabel("Loại Phương Tiện:")
        lbl_type.setStyleSheet("color: white; font-weight: bold;")
        self.combo_type = QComboBox()
        self.combo_type.addItems(["Motorbike", "Car"])
        self.combo_type.setStyleSheet("background-color: #1E293B; color: white; padding: 8px; border-radius: 4px;")

        lbl_status = QLabel("Trạng Thái Thẻ:")
        lbl_status.setStyleSheet("color: white; font-weight: bold;")
        self.combo_status = QComboBox()
        self.combo_status.addItems(["Active", "Blocked"])
        self.combo_status.setStyleSheet("background-color: #1E293B; color: white; padding: 8px; border-radius: 4px;")

        self.btn_save = QPushButton("LƯU THÔNG TIN THẺ")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #0284C7; color: white; font-size: 14px; font-weight: bold;
                padding: 10px; border-radius: 6px; margin-top: 15px;
            }
            QPushButton:hover { background-color: #0369A1; }
        """)
        self.btn_save.clicked.connect(self.save_card)

        form_layout.addWidget(lbl_uid)
        form_layout.addWidget(self.edit_uid)
        form_layout.addWidget(lbl_name)
        form_layout.addWidget(self.edit_name)
        form_layout.addWidget(lbl_type)
        form_layout.addWidget(self.combo_type)
        form_layout.addWidget(lbl_status)
        form_layout.addWidget(self.combo_status)
        form_layout.addWidget(self.btn_save)
        form_layout.addStretch()

        layout.addWidget(form_box, stretch=2)

    def load_cards(self):
        cards = self.db.get_all_cards()
        self.table.setRowCount(len(cards))
        for row_idx, card in enumerate(cards):
            self.table.setItem(row_idx, 0, QTableWidgetItem(card["card_uid"]))
            self.table.setItem(row_idx, 1, QTableWidgetItem(card.get("owner_name", "")))
            self.table.setItem(row_idx, 2, QTableWidgetItem(card.get("vehicle_type", "Motorbike")))
            self.table.setItem(row_idx, 3, QTableWidgetItem(card.get("status", "Active")))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(card.get("created_at", ""))))

    def on_table_item_clicked(self, item):
        row = item.row()
        uid = self.table.item(row, 0).text()
        name = self.table.item(row, 1).text()
        vtype = self.table.item(row, 2).text()
        status = self.table.item(row, 3).text()

        self.edit_uid.setText(uid)
        self.edit_name.setText(name)
        self.combo_type.setCurrentText(vtype)
        self.combo_status.setCurrentText(status)

    def save_card(self):
        uid = self.edit_uid.text().strip().upper()
        name = self.edit_name.text().strip()
        vtype = self.combo_type.currentText()
        status = self.combo_status.currentText()

        if not uid:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập UID thẻ.")
            return

        self.db.update_card(uid, name, vtype, status)
        QMessageBox.information(self, "Thành công", f"Đã lưu thông tin thẻ [{uid}] thành công.")
        self.load_cards()
