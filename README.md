# Hệ Thống Quản Lý Bãi Giữ Xe Thông Minh (Portable ALPR + ESP32 UART)

Ứng dụng quản lý bãi giữ xe chạy trực tiếp từ **Ổ Cứng Di Động (USB / External Drive)** trên nhiều máy tính khác nhau (Windows / Linux / macOS) mà không bị phụ thuộc vào đường dẫn cố định.

## 🎬 Video Demo

[![Video demo hệ thống quản lý bãi giữ xe](https://img.youtube.com/vi/M9WuzOeWIzk/maxresdefault.jpg)](https://www.youtube.com/watch?v=M9WuzOeWIzk)

▶️ **Xem demo:** <https://www.youtube.com/watch?v=M9WuzOeWIzk>

---

## 🚀 Hướng Dẫn Chạy Trên Các Máy Tính Khác Nhau

### 1. Trên Máy Tính Windows:
- Cắm ổ cứng di động vào máy tính Windows.
- Mở thư mục dự án và nhấp đúp chạy tệp:
  `run_windows.bat`
- *(Tệp bat sẽ tự động tạo môi trường `.venv` và cài đặt các thư viện cần thiết nếu máy chưa có sẵn)*.

### 2. Trên Máy Tính Linux (Ubuntu, Debian, Fedora, Arch...):
- Cắm ổ cứng di động và mở Terminal tại thư mục ứng dụng.
- Chạy câu lệnh:
  ```bash
  ./run_linux.sh
  ```
- Hoặc chạy qua môi trường python local:
  ```bash
  python3 main.py
  ```

### 3. Trên Máy Tính macOS:
- Mở Terminal tại thư mục ứng dụng và chạy:
  ```bash
  ./run_mac.sh
  ```

---

## 🌟 Tính Năng Nổi Bật

1. **Portable 100% (Hoạt động đa nền tảng)**:
   - Tất cả dữ liệu (Cơ sở dữ liệu SQLite `data/parking.db`, ảnh chụp `data/captures`, mô hình AI `weights/best.pt`) đều được định vị bằng đường dẫn tương đối động (`paths.py`).
2. **Nhận diện Biển Số Tự Động (ALPR)**:
   - Phát hiện vùng biển số bằng **YOLOv8n** với trọng số huấn luyện sẵn `weights/best.pt` (2 lớp: ô tô / xe máy), suy luận trên CPU.
   - Nhận dạng ký tự bằng **EasyOCR** (PyTorch, chạy CPU); **PaddleOCR** là bộ dự phòng tự động khi EasyOCR không khả dụng hoặc đọc thất bại.
   - Hậu xử lý theo mẫu biển Việt Nam: chuẩn hóa chữ hoa, bỏ dấu phân cách, tách biển hai dòng và sửa các cặp ký tự dễ nhầm (O/0, I/1, B/8, Z/2) theo vị trí ký tự.
3. **Giao Tiếp ESP32 UART & Bộ Giả Lập Virtual Hardware**:
   - Nhận tín hiệu quẹt thẻ RFID (`CARD:<UID>`), phát lệnh mở cản barrier (`CMD:GATE_OPEN`).
   - Tích hợp bộ giả lập quẹt thẻ ngay trên app để thử nghiệm không cần phần cứng.
4. **Tính Phí Tự Động & Đóng Gói Nhập/Xuất Dữ Liệu**:
   - Tự động tính phí theo thời lượng gửi xe và loại xe (Xe máy / Ô tô).
   - Xuất file báo cáo **CSV/Excel**.

---

## 📁 Cấu Trúc Dự Án Portable

```
.
├── paths.py                # Xử lý đường dẫn tương đối động cho ổ cứng di động
├── run_windows.bat         # File chạy 1-click cho máy Windows
├── run_linux.sh            # File chạy 1-click cho máy Linux
├── run_mac.sh              # File chạy 1-click cho máy macOS
├── alpr/                   # Engine AI: YOLOv8n (detect) + EasyOCR/PaddleOCR (OCR)
├── weights/best.pt         # Trọng số mô hình biển số xe Việt Nam
├── database.py             # SQLite Database (lưu ngay trên ổ cứng di động)
├── uart_controller.py      # Giao tiếp UART Serial & Virtual Simulator
├── camera_controller.py    # Multi-threaded OpenCV Camera Stream
├── parking_manager.py      # Logic xe vào/ra & tính tiền
├── gui/                    # Giao diện PyQt6
├── main.py                 # File chạy chính
├── esp32_firmware/         # Firmware Arduino cho ESP32-S3
│   └── esp32_firmware.ino
├── FinalProjectReport.pdf  # Báo cáo đồ án
├── FinalProjectPPT.pdf     # Slide thuyết trình
└── requirements.txt        # Thư viện cần thiết
```

---

## 📄 Tài Liệu

| Tài liệu | Tệp |
| --- | --- |
| Báo cáo đồ án | [FinalProjectReport.pdf](FinalProjectReport.pdf) |
| Slide thuyết trình | [FinalProjectPPT.pdf](FinalProjectPPT.pdf) |

Xem thêm video demo: <https://www.youtube.com/watch?v=M9WuzOeWIzk>
