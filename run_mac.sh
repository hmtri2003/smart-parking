#!/usr/bin/env bash
# Script chạy ứng dụng Bãi Xe trên macOS từ Ổ Cứng Di Động (Portable)

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "============================================================"
echo " KHỞI ĐỘNG HỆ THỐNG QUẢN LÝ BÃI XE (PORTABLE MACOS)"
echo " Thư mục chạy: $SCRIPT_DIR"
echo "============================================================"

VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "[!] Tạo môi trường ảo .venv trên macOS..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r requirements.txt
fi

PYTHON_BIN="$VENV_DIR/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

"$PYTHON_BIN" "$SCRIPT_DIR/main.py"
