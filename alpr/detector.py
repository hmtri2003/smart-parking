import os
import sys
import cv2
import numpy as np
from ultralytics import YOLO
from paths import get_path

class LicensePlateDetector:
    def __init__(self, model_path=None):
        """
        Initializes YOLOv8 detector for Vietnamese license plates.
        Fallback to default yolov8n.pt if best.pt is not found.
        """
        if model_path is None:
            model_path = get_path("weights", "best.pt")
        elif not os.path.isabs(model_path):
            model_path = get_path(model_path)

        self.model_path = model_path
        if not os.path.exists(self.model_path):
            print(f"[ALPR Warning] '{self.model_path}' not found. Checking fallback weights...")
            fallback = get_path("weights", "yolov8n.pt")
            if os.path.exists(fallback):
                self.model_path = fallback
            else:
                self.model_path = "yolov8n.pt"

        print(f"[ALPR Detector] Loading YOLO model from: {self.model_path}")
        self.model = YOLO(self.model_path)

    def detect(self, image_input, conf_threshold=0.25):
        """
        Detects license plates in image.
        image_input: image path string or OpenCV BGR numpy array.

        Returns:
            annotated_image: Image with drawn bounding boxes
            crops: List of cropped plate numpy arrays
            detections: Detailed detection info
        """
        if isinstance(image_input, str):
            image = cv2.imread(image_input)
            if image is None:
                raise ValueError(f"Cannot load image from path: {image_input}")
        else:
            image = image_input.copy()

        h, w = image.shape[:2]
        results = self.model(image, conf=conf_threshold, verbose=False)[0]

        annotated_image = image.copy()
        crops = []
        detections = []

        for box in results.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            cls_name = self.model.names.get(cls_id, "Plate")

            detections.append({
                "box": (x1, y1, x2, y2),
                "confidence": conf,
                "class_name": cls_name
            })

            margin_x = int((x2 - x1) * 0.05)
            margin_y = int((y2 - y1) * 0.05)

            crop_x1 = max(0, x1 - margin_x)
            crop_y1 = max(0, y1 - margin_y)
            crop_x2 = min(w, x2 + margin_x)
            crop_y2 = min(h, y2 + margin_y)

            crop = image[crop_y1:crop_y2, crop_x1:crop_x2]
            crops.append(crop)

            color = (0, 255, 128)
            cv2.rectangle(annotated_image, (x1, y1), (x2, y2), color, 3)

            label = f"{cls_name}: {conf:.2f}"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)

            text_y = max(y1 - 5, lh + 5)
            cv2.rectangle(annotated_image, (x1, text_y - lh - 5), (x1 + lw + 4, text_y + 3), color, -1)
            cv2.putText(annotated_image, label, (x1 + 2, text_y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        return annotated_image, crops, detections
