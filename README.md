# Hệ Thống Quản Lý Bãi Giữ Xe Thông Minh (Portable ALPR + ESP32 UART)

Ứng dụng quản lý bãi giữ xe chạy trực tiếp từ **Ổ Cứng Di Động (USB / External Drive)** trên nhiều máy tính khác nhau (Windows / Linux / macOS) mà không bị phụ thuộc vào đường dẫn cố định.

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
   - Sử dụng **YOLOv8** + **PaddleOCR** đọc chính xác biển số xe Việt Nam.
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
├── alpr/                   # Engine AI YOLOv8 + PaddleOCR
├── weights/best.pt         # Trọng số mô hình biển số xe Việt Nam
├── database.py             # SQLite Database (lưu ngay trên ổ cứng di động)
├── uart_controller.py      # Giao tiếp UART Serial & Virtual Simulator
├── camera_controller.py    # Multi-threaded OpenCV Camera Stream
├── parking_manager.py      # Logic xe vào/ra & tính tiền
├── gui/                    # Giao diện PyQt6
├── main.py                 # File chạy chính
├── esp32_firmware.ino      # Firmware nạp cho ESP32 Hardware
└── requirements.txt        # Thư viện cần thiết
```
