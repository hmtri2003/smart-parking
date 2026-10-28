import time
import serial
import serial.tools.list_ports
from PyQt6.QtCore import QThread, pyqtSignal, QObject

class UARTController(QThread):
    # Signals for Qt GUI
    card_scanned = pyqtSignal(str)            # Emits UID string (e.g. "A1B2C3D4")
    card_scanned_mode = pyqtSignal(str, str) # Emits (UID, mode: "ENTRY" / "EXIT" / "AUTO")
    connection_status = pyqtSignal(bool, str) # Emits (is_connected, message)
    raw_data_received = pyqtSignal(str)   # Emits raw log message

    def __init__(self, port: str = "COM3", baudrate: int = 115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = False
        self.serial_conn = None
        self.simulation_mode = False
        self._config_rev = 0

    @staticmethod
    def get_available_ports():
        """Returns list of available serial port names on system."""
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def set_config(self, port: str, baudrate: int):
        """Applies new settings; the worker thread reconnects on its next loop."""
        self.port = port
        self.baudrate = int(baudrate)
        self._config_rev += 1

    def run(self):
        self.running = True
        print(f"[UART] Worker thread started on port: {self.port} ({self.baudrate} bps)")

        while self.running:
            config_rev = self._config_rev

            if self.simulation_mode or self.port == "SIMULATOR":
                self.connection_status.emit(True, "Virtual UART Simulator Mode")
                time.sleep(0.5)
                continue

            if not self.port:
                self.connection_status.emit(False, "Chưa chọn cổng COM; hãy chọn cổng trong tab Cấu hình.")
                time.sleep(1)
                continue
            try:
                self.connection_status.emit(False, f"Đang kết nối cổng {self.port}...")
                self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1, write_timeout=1)
                self.connection_status.emit(True, f"Đã kết nối {self.port} thành công")
                print(f"[UART] Serial opened successfully on {self.port}")

                while self.running and self.serial_conn and self.serial_conn.is_open:
                    if config_rev != self._config_rev:
                        print("[UART] Settings changed, closing port to reconnect...")
                        self.serial_conn.close()
                        self.serial_conn = None
                        break
                    if self.serial_conn.in_waiting > 0:
                        line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            self.raw_data_received.emit(line)
                            self._process_line(line)
                    time.sleep(0.02)

            except Exception as e:
                self.connection_status.emit(False, f"Lá»—i káº¿t ná»‘i {self.port}: {str(e)}")
                if self.serial_conn and self.serial_conn.is_open:
                    try:
                        self.serial_conn.close()
                    except Exception:
                        pass
                    self.serial_conn = None
                time.sleep(1)

    def _process_line(self, line: str):
        """Parses incoming UART string commands from ESP32."""
        upper_line = line.upper()
        if "CARD_IN:" in upper_line:
            uid = upper_line.split("CARD_IN:")[1].strip()
            if uid:
                print(f"[UART Signal] Entry RFID Scanned: {uid}")
                self.card_scanned_mode.emit(uid, "ENTRY")
                self.card_scanned.emit(uid)
        elif "CARD_OUT:" in upper_line:
            uid = upper_line.split("CARD_OUT:")[1].strip()
            if uid:
                print(f"[UART Signal] Exit RFID Scanned: {uid}")
                self.card_scanned_mode.emit(uid, "EXIT")
                self.card_scanned.emit(uid)
        elif "CARD:" in upper_line:
            uid = upper_line.split("CARD:")[1].strip()
            if uid:
                print(f"[UART Signal] Card UID Scanned: {uid}")
                self.card_scanned_mode.emit(uid, "AUTO")
                self.card_scanned.emit(uid)
        elif "UID:" in upper_line:
            uid = upper_line.split("UID:")[1].strip()
            if uid:
                print(f"[UART Signal] Card UID Scanned: {uid}")
                self.card_scanned_mode.emit(uid, "AUTO")
                self.card_scanned.emit(uid)
        elif len(upper_line) >= 4 and all(c in "0123456789ABCDEF" for c in upper_line):
            # Direct Hex UID string
            self.card_scanned_mode.emit(upper_line, "AUTO")
            self.card_scanned.emit(upper_line)


    def send_command(self, command: str) -> bool:
        """Sends command string to ESP32 (e.g., 'CMD:GATE_OPEN\n')."""
        if self.simulation_mode or self.port == "SIMULATOR":
            print(f"[UART Simulator] Executed command: {command.strip()}")
            self.raw_data_received.emit(f"[OUT SIM]: {command.strip()}")
            return True

        if self.serial_conn and self.serial_conn.is_open:
            try:
                cmd_bytes = (command.strip() + "\n").encode('utf-8')
                self.serial_conn.write(cmd_bytes)
                self.serial_conn.flush()
                self.raw_data_received.emit(f"[OUT]: {command.strip()}")
                return True
            except Exception as e:
                print(f"[UART Send Error] {e}")
                return False
        return False

    def simulate_card_tap(self, card_uid: str):
        """Simulates tapping an RFID card for testing without hardware."""
        uid = card_uid.strip().upper()
        if uid:
            print(f"[UART Simulator] Simulating RFID Card Tap UID: {uid}")
            self.raw_data_received.emit(f"[SIM CARD SCAN]: {uid}")
            self.card_scanned.emit(uid)

    def stop(self):
        self.running = False
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.close()
            except Exception:
                pass
        self.wait(2000)




