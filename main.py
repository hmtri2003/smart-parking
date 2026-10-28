#!/usr/bin/env python3
"""
Parking Lot Management System with ESP32 UART RFID & Vietnam ALPR OCR
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

def main():
    # Set workdir to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    app = QApplication(sys.argv)
    app.setApplicationName("Quản Lý Bãi Giữ Xe Thông Minh")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
