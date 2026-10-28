import html
import json
import socket
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2


class PaymentInfoServer:
    """Serves the active parking bill to phones on the same Wi-Fi network."""
    def __init__(self, port=8765):
        self.port = port
        self._lock = threading.Lock()
        self._bills = {}
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                token = self.path.strip("/").split("/")[-1]
                with owner._lock:
                    bill = owner._bills.get(token)
                if not bill:
                    body = "<h2>Hóa đơn không tồn tại hoặc đã hết hạn.</h2>"
                else:
                    body = (
                        "<h1>Thông tin thanh toán</h1>"
                        f"<p>Biển số: <b>{html.escape(bill['plate'])}</b></p>"
                        f"<p>Loại xe: {html.escape(bill['vehicle'])}</p>"
                        f"<p>Thời gian gửi: {html.escape(bill['duration'])}</p>"
                        f"<p class='amount'>{bill['amount']:,} VNĐ</p>"
                        "<p>Vui lòng thanh toán tại quầy. Trang này chỉ hiển thị số tiền, "
                        "chưa xác nhận giao dịch ngân hàng.</p>"
                    )
                page = ("<!doctype html><html lang='vi'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                        "<meta charset='utf-8'><title>Thanh toán gửi xe</title>"
                        "<style>body{font:18px Arial;max-width:520px;margin:40px auto;padding:24px;color:#172033}"
                        ".amount{font-size:36px;font-weight:bold;color:#087443}</style><body>" + body + "</body></html>").encode("utf-8")
                self.send_response(200 if bill else 404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)

            def log_message(self, fmt, *args):
                pass

        self.server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = self._local_ip()

    @staticmethod
    def _local_ip():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"
        finally:
            sock.close()

    def create_bill(self, result):
        token = uuid.uuid4().hex
        bill = {
            "plate": str(result.get("plate_out") or result.get("plate_in") or "Chưa nhận diện"),
            "vehicle": str(result.get("vehicle_type") or "Xe"),
            "duration": str(result.get("duration") or ""),
            "amount": int(result.get("fee", 0)),
        }
        with self._lock:
            self._bills[token] = bill
        return f"http://{self.host}:{self.port}/{token}", bill

    @staticmethod
    def make_qr(url):
        encoder = cv2.QRCodeEncoder_create()
        matrix = encoder.encode(url)
        # QR scanners require a quiet zone; integer scaling preserves square modules.
        matrix = cv2.copyMakeBorder(matrix, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=255)
        return cv2.resize(matrix, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)

    def close(self):
        self.server.shutdown()
        self.server.server_close()

