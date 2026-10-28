import os
import csv
import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QComboBox, QLabel, QHeaderView, QDialog,
    QMessageBox, QFileDialog, QGroupBox, QFrame
)
from database import DatabaseManager

class LogDetailDialog(QDialog):
    """Dialog showing detailed side-by-side images of vehicle entry vs exit."""
    def __init__(self, record: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Chi Tiết Lượt Gửi Xe #{record['id']} - Biển số: {record['plate_in']}")
        self.setMinimumSize(850, 520)
        self.setStyleSheet("background-color: #0F172A; color: white;")
        self.init_ui(record)

    def init_ui(self, rec: dict):
        layout = QVBoxLayout(self)

        # Info Header
        info_str = (
            f"UID Thẻ: {rec['card_uid']} | Loại xe: {rec['vehicle_type']} | "
            f"Giờ vào: {rec['entry_time']} | Giờ ra: {rec.get('exit_time') or 'Chưa ra'} | "
            f"Phí: {rec.get('fee', 0):,} VNĐ"
        )
        lbl_info = QLabel(info_str)
        lbl_info.setStyleSheet("color: #38BDF8; font-size: 14px; font-weight: bold; padding: 10px; background-color: #1E293B; border-radius: 6px;")
        layout.addWidget(lbl_info)

        # Images Layout: Left = Entry Image, Right = Exit Image
        img_layout = QHBoxLayout()

        box_in = QGroupBox(f"Ảnh Xe Vào ({rec['plate_in']})")
        box_in.setStyleSheet("color: #34D399; font-weight: bold;")
        layout_in = QVBoxLayout(box_in)
        lbl_img_in = QLabel()
        lbl_img_in.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_img_in.setText("Không có ảnh vào")

        path_in = rec.get("image_in_path")
        if path_in and os.path.exists(path_in):
            pix_in = QPixmap(path_in).scaled(380, 320, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_img_in.setPixmap(pix_in)
        layout_in.addWidget(lbl_img_in)
        img_layout.addWidget(box_in)

        box_out = QGroupBox(f"Ảnh Xe Ra ({rec.get('plate_out') or 'Chưa ra'})")
        box_out.setStyleSheet("color: #60A5FA; font-weight: bold;")
        layout_out = QVBoxLayout(box_out)
        lbl_img_out = QLabel()
        lbl_img_out.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_img_out.setText("Chưa có ảnh ra")

        path_out = rec.get("image_out_path")
        if path_out and os.path.exists(path_out):
            pix_out = QPixmap(path_out).scaled(380, 320, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_img_out.setPixmap(pix_out)
        layout_out.addWidget(lbl_img_out)
        img_layout.addWidget(box_out)

        layout.addLayout(img_layout)

        # Close button
        btn_close = QPushButton("Đóng")
        btn_close.setStyleSheet("background-color: #334155; color: white; padding: 8px; font-weight: bold; border-radius: 6px;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class LogsWidget(QWidget):
    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.records_data = []
        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Top Filter & Search Bar
        filter_box = QFrame()
        filter_box.setStyleSheet("background-color: #0F172A; border: 1px solid #1E293B; border-radius: 8px; padding: 6px;")
        filter_layout = QHBoxLayout(filter_box)

        lbl_search = QLabel("Tìm kiếm:")
        lbl_search.setStyleSheet("color: white; font-weight: bold;")
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Nhập biển số hoặc UID thẻ...")
        self.edit_search.setStyleSheet("background-color: #1E293B; color: white; padding: 6px; border-radius: 4px;")
        self.edit_search.textChanged.connect(self.load_data)

        lbl_filter = QLabel("Trạng thái:")
        lbl_filter.setStyleSheet("color: white; font-weight: bold;")
        self.combo_filter = QComboBox()
        self.combo_filter.addItems(["TẤT CẢ (ALL)", "ĐANG GỬI (IN_PARK)", "ĐÃ THÀNH TOÁN (COMPLETED)"])
        self.combo_filter.setStyleSheet("background-color: #1E293B; color: white; padding: 6px; border-radius: 4px;")
        self.combo_filter.currentIndexChanged.connect(self.load_data)

        btn_refresh = QPushButton("Làm Mới")
        btn_refresh.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        btn_refresh.clicked.connect(self.load_data)

        btn_export = QPushButton("Xuất CSV...")
        btn_export.setStyleSheet("background-color: #16A34A; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        btn_export.clicked.connect(self.export_csv)

        filter_layout.addWidget(lbl_search)
        filter_layout.addWidget(self.edit_search, stretch=2)
        filter_layout.addWidget(lbl_filter)
        filter_layout.addWidget(self.combo_filter)
        filter_layout.addWidget(btn_refresh)
        filter_layout.addWidget(btn_export)

        layout.addWidget(filter_box)

        # Table View
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "ID", "UID Thẻ", "Biển Vào", "Biển Ra", "Loại Xe", "Giờ Vào", "Giờ Ra", "Phí (VNĐ)", "Trạng Thái", "Ghi Chú"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0F172A;
                color: #E2E8F0;
                gridline-color: #334155;
                font-size: 13px;
                border: 1px solid #1E293B;
            }
            QHeaderView::section {
                background-color: #1E293B;
                color: #38BDF8;
                font-weight: bold;
                padding: 8px;
                border: 1px solid #334155;
            }
            QTableWidget::item:selected {
                background-color: #0369A1;
            }
        """)
        self.table.doubleClicked.connect(self.show_detail_dialog)
        layout.addWidget(self.table)

    def load_data(self):
        search_term = self.edit_search.text().strip()
        filter_idx = self.combo_filter.currentIndex()

        status_map = {0: "ALL", 1: "IN_PARK", 2: "COMPLETED"}
        status_filter = status_map.get(filter_idx, "ALL")

        self.records_data = self.db.get_parking_records(search_term, status_filter)
        self.table.setRowCount(len(self.records_data))

        for row_idx, rec in enumerate(self.records_data):
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(rec["id"])))
            self.table.setItem(row_idx, 1, QTableWidgetItem(rec["card_uid"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(rec["plate_in"]))
            self.table.setItem(row_idx, 3, QTableWidgetItem(rec.get("plate_out") or "--"))
            self.table.setItem(row_idx, 4, QTableWidgetItem(rec.get("vehicle_type", "Motorbike")))
            self.table.setItem(row_idx, 5, QTableWidgetItem(rec["entry_time"]))
            self.table.setItem(row_idx, 6, QTableWidgetItem(rec.get("exit_time") or "--"))

            fee_str = f"{rec.get('fee', 0):,} VNĐ" if rec.get("fee") else "0 VNĐ"
            self.table.setItem(row_idx, 7, QTableWidgetItem(fee_str))

            status_str = "ĐANG GỬI" if rec["status"] == "IN_PARK" else "ĐÃ RA BÃI"
            item_status = QTableWidgetItem(status_str)
            if rec["status"] == "IN_PARK":
                item_status.setForeground(Qt.GlobalColor.green)
            else:
                item_status.setForeground(Qt.GlobalColor.cyan)
            self.table.setItem(row_idx, 8, item_status)

            self.table.setItem(row_idx, 9, QTableWidgetItem(rec.get("notes") or ""))

    def show_detail_dialog(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.records_data):
            rec = self.records_data[row]
            dialog = LogDetailDialog(rec, self)
            dialog.exec()

    def export_csv(self):
        if not self.records_data:
            QMessageBox.information(self, "Thông báo", "Không có dữ liệu để xuất CSV.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Xuất Nhật Ký Gửi Xe CSV", "nhat_ky_gui_xe.csv", "CSV Files (*.csv)")
        if file_path:
            try:
                with open(file_path, mode="w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(["ID", "UID Thẻ", "Biển Số Vào", "Biển Số Ra", "Loại Xe", "Giờ Vào", "Giờ Ra", "Phí (VNĐ)", "Trạng Thái", "Ghi Chú"])
                    for rec in self.records_data:
                        writer.writerow([
                            rec["id"], rec["card_uid"], rec["plate_in"], rec.get("plate_out") or "",
                            rec.get("vehicle_type", ""), rec["entry_time"], rec.get("exit_time") or "",
                            rec.get("fee", 0), rec["status"], rec.get("notes") or ""
                        ])
                QMessageBox.information(self, "Thành công", f"Đã xuất file CSV thành công:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể xuất file: {e}")
