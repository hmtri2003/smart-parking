import os
import cv2
import datetime
import numpy as np
from typing import Dict, Tuple, Optional
from database import DatabaseManager
from alpr import LicensePlateDetector, LicensePlateOCR
from paths import get_path

class ParkingManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
        # Initialize ALPR components
        self.detector = LicensePlateDetector(model_path=get_path("weights", "best.pt"))
        self.ocr = LicensePlateOCR()

        self.captures_dir = get_path("data", "captures")
        os.makedirs(self.captures_dir, exist_ok=True)

    def process_card_tap(self, card_uid: str, frame: np.ndarray, force_mode: str = "AUTO") -> Dict:
        """
        Main handler when RFID card is tapped.
        force_mode: "AUTO" (auto-detect in/out), "ENTRY" (force entry), "EXIT" (force exit)
        """
        card_info = self.db.register_or_get_card(card_uid)
        active_record = self.db.find_active_record_by_card(card_uid)

        # Determine operation: Entry or Exit
        if force_mode == "ENTRY":
            is_entry = True
        elif force_mode == "EXIT":
            is_entry = False
        else: # AUTO mode
            # If vehicle is currently in park -> process EXIT, else process ENTRY
            is_entry = (active_record is None)

        if is_entry:
            return self._handle_entry(card_info, frame)
        else:
            return self._handle_exit(card_info, active_record, frame)

    def _handle_entry(self, card_info: Dict, frame: np.ndarray) -> Dict:
        """Processes vehicle entry (Xe Vào)."""
        card_uid = card_info["card_uid"]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Run ALPR
        annotated_img, crops, detections = self.detector.detect(frame, conf_threshold=0.25)

        detected_plate = "CHƯA_RÕ_BIỂN"
        confidence = 0.0
        crop_img = None

        if crops:
            crop_img = crops[0]
            detected_plate, confidence = self.ocr.read_plate(crop_img)
            if not detected_plate:
                detected_plate = "KHÔNG_ĐỌC_ĐƯỢC"

        # Save images to disk
        image_in_path = os.path.join(self.captures_dir, f"in_{card_uid}_{timestamp}.jpg")
        crop_in_path = os.path.join(self.captures_dir, f"crop_in_{card_uid}_{timestamp}.jpg")

        cv2.imwrite(image_in_path, annotated_img)
        if crop_img is not None and crop_img.size > 0:
            cv2.imwrite(crop_in_path, crop_img)
        else:
            crop_in_path = image_in_path

        # Add record to DB
        record_id = self.db.add_entry_record(
            card_uid=card_uid,
            plate_in=detected_plate,
            image_in_path=image_in_path,
            crop_in_path=crop_in_path,
            vehicle_type=card_info.get("vehicle_type", "Motorbike")
        )

        return {
            "type": "ENTRY",
            "record_id": record_id,
            "card_uid": card_uid,
            "plate": detected_plate,
            "confidence": confidence,
            "image_path": image_in_path,
            "crop_path": crop_in_path,
            "entry_time": datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
            "vehicle_type": card_info.get("vehicle_type", "Motorbike"),
            "status_ok": True,
            "message": f"XE VÀO THÀNH CÔNG: Biển số [{detected_plate}] - Thẻ [{card_uid}]"
        }

    def _handle_exit(self, card_info: Dict, active_record: Optional[Dict], frame: np.ndarray) -> Dict:
        """Processes vehicle exit (Xe Ra)."""
        card_uid = card_info["card_uid"]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if active_record is None:
            # Fallback if forced exit but no entry record found
            plate_in = "KHÔNG_CÓ_DỮ_LIỆU_VÀO"
            entry_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            record_id = 0
            vehicle_type = card_info.get("vehicle_type", "Motorbike")
        else:
            record_id = active_record["id"]
            plate_in = active_record["plate_in"]
            entry_time_str = active_record["entry_time"]
            vehicle_type = active_record.get("vehicle_type", "Motorbike")

        # Run ALPR for exit
        annotated_img, crops, detections = self.detector.detect(frame, conf_threshold=0.25)

        plate_out = "CHƯA_RÕ_BIỂN"
        confidence = 0.0
        crop_img = None

        if crops:
            crop_img = crops[0]
            plate_out, confidence = self.ocr.read_plate(crop_img)
            if not plate_out:
                plate_out = "KHÔNG_ĐỌC_ĐƯỢC"

        # Save images
        image_out_path = os.path.join(self.captures_dir, f"out_{card_uid}_{timestamp}.jpg")
        crop_out_path = os.path.join(self.captures_dir, f"crop_out_{card_uid}_{timestamp}.jpg")

        cv2.imwrite(image_out_path, annotated_img)
        if crop_img is not None and crop_img.size > 0:
            cv2.imwrite(crop_out_path, crop_img)
        else:
            crop_out_path = image_out_path

        # Calculate duration and fee
        exit_time = datetime.datetime.now()
        exit_time_str = exit_time.strftime("%Y-%m-%d %H:%M:%S")

        fee, duration_str = self.calculate_fee(vehicle_type, entry_time_str, exit_time_str)

        # Check plate match
        plate_match = self.compare_plates(plate_in, plate_out)
        notes = "Khớp biển số" if plate_match else f"CẢNH BÁO: Không khớp biển số (Vào: {plate_in} vs Ra: {plate_out})"

        # Complete record in DB
        if record_id > 0:
            self.db.complete_exit_record(
                record_id=record_id,
                plate_out=plate_out,
                image_out_path=image_out_path,
                crop_out_path=crop_out_path,
                fee=fee,
                notes=notes
            )

        return {
            "type": "EXIT",
            "record_id": record_id,
            "card_uid": card_uid,
            "plate_in": plate_in,
            "plate_out": plate_out,
            "plate_match": plate_match,
            "confidence": confidence,
            "image_in_path": active_record["image_in_path"] if active_record else "",
            "image_out_path": image_out_path,
            "crop_in_path": active_record["crop_in_path"] if active_record else "",
            "crop_out_path": crop_out_path,
            "entry_time": entry_time_str,
            "exit_time": exit_time.strftime("%H:%M:%S %d/%m/%Y"),
            "duration": duration_str,
            "fee": fee,
            "vehicle_type": vehicle_type,
            "status_ok": plate_match,
            "message": f"XE RA THÀNH CÔNG: Phí {fee:,} VNĐ ({duration_str})" if plate_match else f"CẢNH BÁO KHÔNG KHỚP BIỂN SỐ! Phí {fee:,} VNĐ"
        }

    def calculate_fee(self, vehicle_type: str, entry_time_str: str, exit_time_str: str) -> Tuple[int, str]:
        """Calculates parking fee and duration string."""
        try:
            t_in = datetime.datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
            t_out = datetime.datetime.strptime(exit_time_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            t_in = datetime.datetime.now()
            t_out = datetime.datetime.now()

        diff = t_out - t_in
        total_seconds = max(0, int(diff.total_seconds()))

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        duration_str = f"{hours}h {minutes}m"

        # Fixed tariffs requested: 5,000 VND motorbike, 10,000 VND car;
        # any stay crossing midnight is charged the overnight rate of 50,000 VND.
        if t_in.date() != t_out.date():
            fee = 50000
        elif vehicle_type in ("Car", "Ô tô"):
            fee = 10000
        else:
            fee = 5000

        return fee, duration_str

    @staticmethod
    def compare_plates(plate1: str, plate2: str) -> bool:
        """Returns True if plate strings are reasonably matching."""
        if not plate1 or not plate2:
            return True
        clean1 = "".join(c for c in plate1.upper() if c.isalnum())
        clean2 = "".join(c for c in plate2.upper() if c.isalnum())
        if not clean1 or not clean2:
            return True
        return clean1 == clean2 or clean1 in clean2 or clean2 in clean1
