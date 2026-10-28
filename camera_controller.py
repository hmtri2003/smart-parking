import cv2
import time
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

class CameraController(QThread):
    frame_received = pyqtSignal(np.ndarray) # Emits BGR frame for live video UI
    camera_status = pyqtSignal(bool, str)   # Emits (is_running, status_message)

    def __init__(self, camera_source="0"):
        super().__init__()
        self.camera_source = camera_source
        self.running = False
        self.cap = None
        self.current_frame = None

    def set_source(self, source):
        self.camera_source = source

    def run(self):
        self.running = True
        print(f"[Camera Thread] Starting camera stream from source: {self.camera_source}")

        # Parse source (int for webcam, string for video file / IP cam)
        src = self.camera_source
        if str(src).isdigit():
            src = int(src)

        try:
            self.cap = cv2.VideoCapture(src)
            if not self.cap.isOpened():
                self.camera_status.emit(False, f"Không thể mở Camera nguồn: {self.camera_source}")
                # Fallback generator: create test pattern frame if camera unavailable
                self._run_fallback_loop()
                return

            self.camera_status.emit(True, f"Camera hoạt động (Nguồn: {self.camera_source})")

            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    # Loop video if source is video file
                    if isinstance(src, str) and not src.isdigit():
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        time.sleep(0.05)
                        continue

                self.current_frame = frame.copy()
                self.frame_received.emit(frame)
                time.sleep(0.03) # ~30 FPS loop

        except Exception as e:
            self.camera_status.emit(False, f"Lỗi Camera: {str(e)}")
            self._run_fallback_loop()

        finally:
            if self.cap and self.cap.isOpened():
                self.cap.release()

    def _run_fallback_loop(self):
        """Generates mock camera preview canvas if physical camera is missing."""
        print("[Camera Thread] Running placeholder canvas loop.")
        blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        while self.running:
            # Draw synthetic test screen
            img = blank_frame.copy()
            cv2.putText(img, "CAMERA PREVIEW (FALLBACK)", (80, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
            cv2.putText(img, "Nạp ảnh thủ công hoặc chọn webcam trong Cài Đặt", (60, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            t_str = time.strftime("%H:%M:%S")
            cv2.putText(img, f"Live: {t_str}", (240, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            self.current_frame = img
            self.frame_received.emit(img)
            time.sleep(0.05)

    def capture_frame(self) -> np.ndarray:
        if self.current_frame is not None:
            return self.current_frame.copy()
        # Fallback dummy image
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(blank, "SNAPSHOT CAPTURED", (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        return blank

    def stop(self):
        self.running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.wait(1500)
