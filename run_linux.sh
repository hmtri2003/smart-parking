#!/usr/bin/env bash
# Script chạy ứng dụng Bãi Xe trên Linux từ Ổ Cứng Di Động (Portable exFAT/NTFS friendly)

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "============================================================"
echo " KHỞI ĐỘNG HỆ THỐNG QUẢN LÝ BÃI XE (PORTABLE LINUX)"
echo " Thư mục chạy: $SCRIPT_DIR"
echo "============================================================"

# Danh sách các đường dẫn Python tiềm năng
PYTHON_CANDIDATES=(
    "$SCRIPT_DIR/.venv/bin/python"
    "$HOME/Documents/Antigravity/venv_alpr/bin/python"
    "$HOME/.cache/parking_app_venv/bin/python"
    "$HOME/.venv/bin/python"
    "/usr/bin/python3"
    "python3"
    "python"
)

PYTHON_BIN=""

# 1. Tự động tìm Python environment có sẵn đủ thư viện PyQt6
for py in "${PYTHON_CANDIDATES[@]}"; do
    if [ -f "$py" ] || command -v "$py" &> /dev/null; then
        if "$py" -c "import PyQt6, ultralytics" &> /dev/null; then
            PYTHON_BIN="$py"
            echo "[+] Phát hiện môi trường Python tương thích: $PYTHON_BIN"
            break
        fi
    fi
done

# 2. Nếu chưa có môi trường đủ thư viện -> Tự động cài đặt
if [ -z "$PYTHON_BIN" ]; then
    echo "[!] Chưa phát hiện thư viện PyQt6. Đang tự động cấu hình..."
    
    # Thử tạo .venv trong ~/.cache (tránh lỗi exFAT/NTFS symlink trên ổ di động)
    CACHE_VENV="$HOME/.cache/parking_app_venv"
    if python3 -m venv "$CACHE_VENV" 2>/dev/null; then
        echo "[+] Đang cài đặt thư viện vào $CACHE_VENV..."
        "$CACHE_VENV/bin/pip" install --upgrade pip
        "$CACHE_VENV/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
        PYTHON_BIN="$CACHE_VENV/bin/python"
    else
        echo "[+] Đang cài đặt thư viện qua pip user..."
        python3 -m pip install --user -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null || python3 -m pip install --break-system-packages -r "$SCRIPT_DIR/requirements.txt"
        PYTHON_BIN="python3"
    fi
fi

echo "[+] Đang khởi chạy giao diện ứng dụng..."
"$PYTHON_BIN" "$SCRIPT_DIR/main.py"
