import os
import re
import cv2
import numpy as np

# Disable oneDNN / MKLDNN bug in PaddlePaddle 3.x on CPU
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"

class LicensePlateOCR:
    def __init__(self):
        """
        Initializes ALPR OCR engine (EasyOCR / PaddleOCR).
        """
        print("[ALPR OCR] Initializing License Plate OCR engine...")
        self.easyocr_reader = None
        self.ocr = None

        # 1. Try EasyOCR (PyTorch native, fast & 100% stable)
        try:
            import easyocr
            self.easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            print("[ALPR OCR] EasyOCR engine loaded successfully.")
        except Exception as e:
            print(f"[ALPR OCR Warning] EasyOCR not available: {e}")

        # 2. Try PaddleOCR fallback if EasyOCR is missing
        if self.easyocr_reader is None:
            try:
                from paddleocr import PaddleOCR
                self.ocr = PaddleOCR(
                    lang='en',
                    enable_mkldnn=False,
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False
                )
                print("[ALPR OCR] PaddleOCR engine loaded successfully.")
            except Exception as e:
                print(f"[ALPR OCR Warning] PaddleOCR not available: {e}")


    def preprocess_crop(self, crop_image: np.ndarray) -> np.ndarray:
        """
        Applies image resolution upscaling (3x cubic) and CLAHE contrast enhancement
        to cleanly separate letters (A, B, G, F, T...) from digits (1, 4, 7, 8...).
        """
        if crop_image is None or crop_image.size == 0:
            return crop_image

        h, w = crop_image.shape[:2]
        # Upscale 3x using cubic interpolation for higher character clarity
        resized = cv2.resize(crop_image, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)

        # Contrast Limited Adaptive Histogram Equalization (CLAHE)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    def fix_line_order(self, lines: list) -> list:
        """
        Detects if OCR read bottom sequence line before top header line (city code + series)
        and reorders lines to standard [Header Line, Sequence Line].
        """
        if not lines or len(lines) < 2:
            return lines

        l0_raw = re.sub(r'[^A-Z0-9]', '', lines[0].upper())
        l1_raw = re.sub(r'[^A-Z0-9]', '', lines[1].upper())

        l0_clean = self.correct_confusion_characters(l0_raw)
        l1_clean = self.correct_confusion_characters(l1_raw)

        is_l0_digits = l0_clean.isdigit() and len(l0_clean) in [4, 5]
        is_l1_header = bool(re.match(r'^\d{2}[A-Z]{1}', l1_clean))

        if is_l0_digits and is_l1_header:
            return [lines[1], lines[0]]

        return lines

    def format_plate_text(self, text: str, is_2line: bool = False, vehicle_type: str = "AUTO", lines: list = None) -> str:
        """
        Formats recognized OCR string according to Vietnamese Traffic Standards:
        - 2-line Car Plate: 51H-919.91, 30F-12.34
        - Motorbike 5-Digit Sequence: 15-P1 037.37, 59-K2 123.45
        - Motorbike 4-Digit Sequence: 54-L1 9999, 50-CA 5874
        - Car 1-Line Plate: 68A-668.88, 51G-100.96
        """
        # 1. Line-aware formatting (for 2-line crops from EasyOCR / PaddleOCR)
        if lines and len(lines) >= 2:
            lines = self.fix_line_order(lines)
            l1 = re.sub(r'[^A-Z0-9]', '', lines[0].upper())
            l2 = re.sub(r'[^A-Z0-9]', '', lines[1].upper())

            # Apply position-based corrections on Line 1
            l1_chars = list(l1)
            letter_to_digit = {'O':'0','D':'0','Q':'0','I':'1','L':'1','J':'1','S':'5','B':'8','G':'6','Z':'2','A':'4','T':'7'}
            digit_to_letter = {'4':'A','8':'B','0':'D','6':'G','5':'S','2':'Z','3':'E','9':'P'}
            for i in range(min(2, len(l1_chars))):
                if l1_chars[i] in letter_to_digit:
                    l1_chars[i] = letter_to_digit[l1_chars[i]]
            if len(l1_chars) >= 3 and l1_chars[2].isdigit() and l1_chars[2] in digit_to_letter:
                l1_chars[2] = digit_to_letter[l1_chars[2]]
            l1 = "".join(l1_chars)

            # Line 2 MUST be sequence digits ONLY
            l2_chars = list(l2)
            for i in range(len(l2_chars)):
                if l2_chars[i] in letter_to_digit:
                    l2_chars[i] = letter_to_digit[l2_chars[i]]
            l2 = "".join([c for c in l2_chars if c.isdigit()])

            # Case A: 2-line Car Plate (Line 1 has 3 chars: e.g. 51H, 60A, 30F)
            m_car_l1 = re.match(r'^(\d{2})([A-Z]{1})$', l1)
            if m_car_l1:
                c, s = m_car_l1.group(1), m_car_l1.group(2)
                if len(l2) == 5:
                    return f"{c}{s}-{l2[:3]}.{l2[3:]}"
                elif len(l2) == 4:
                    return f"{c}{s}-{l2[:2]}.{l2[2:]}"
                elif len(l2) > 5:
                    return f"{c}{s}-{l2[:3]}.{l2[3:5]}"

            # Case B: 2-line Motorbike / 2-letter Car Plate (Line 1 has 4 chars: e.g. 15P1, 54L1, 50CA, 29AA, 51LD)
            m_mb_l1 = re.match(r'^(\d{2})([A-Z]{1}[A-Z0-9]{1})$', l1)
            if m_mb_l1:
                c, s = m_mb_l1.group(1), m_mb_l1.group(2)
                if vehicle_type in ["Car", "Xe ô tô"] or (s.isalpha() and len(l2) == 5 and not is_2line):
                    return f"{c}{s}-{l2[:3]}.{l2[3:]}"
                else:
                    if len(l2) == 5:
                        return f"{c}-{s} {l2[:3]}.{l2[3:]}"
                    elif len(l2) == 4:
                        return f"{c}-{s} {l2}"
                    elif len(l2) > 5:
                        return f"{c}-{s} {l2[:3]}.{l2[3:5]}"

        # 2. Fallback to raw string parsing
        if not text and lines:
            text = "".join(lines)
        if not text:
            return ""

        text = text.upper()
        raw = re.sub(r'[^A-Z0-9]', '', text)
        if not raw or len(raw) < 5:
            return text

        # Check if sequence numbers come BEFORE city code + series (inverted OCR read)
        m_inv = re.match(r'^(\d{4,5})(\d{2}[A-Z]{1}[A-Z0-9]{0,2})$', raw)
        if m_inv:
            raw = m_inv.group(2) + m_inv.group(1)

        # Apply positional heuristic fixes
        raw = self.correct_confusion_characters(raw)

        # Fix OCR misreading hyphen '-' or bolt head as digit '7' or '1' right after series letter
        match_stray_hyphen = re.match(r'^(\d{2}[A-Z]{1})[71](\d{4,5})$', raw)
        if match_stray_hyphen and not is_2line:
            raw = match_stray_hyphen.group(1) + match_stray_hyphen.group(2)

        # Enforce 5-digit maximum sequence rule
        raw = self.truncate_excess_sequence_digits(raw)

        # 1. 9-character Motorbike 5-digit sequence (e.g. 15P103737 -> 15-P1 037.37, 59K212345 -> 59-K2 123.45)
        if len(raw) == 9:
            m_mb9 = re.match(r'^(\d{2})([A-Z]{1}[A-Z0-9]{1})(\d{5})$', raw)
            if m_mb9:
                c, s, n = m_mb9.group(1), m_mb9.group(2), m_mb9.group(3)
                return f"{c}-{s} {n[:3]}.{n[3:]}"

        # 2. 8-character Motorbike 4-digit sequence (e.g. 54L19999 -> 54-L1 9999)
        if len(raw) == 8 and (is_2line or vehicle_type in ["Motorbike", "Xe máy"]):
            m_mb8 = re.match(r'^(\d{2})([A-Z]{1}[A-Z0-9]{1})(\d{4})$', raw)
            if m_mb8:
                c, s, n = m_mb8.group(1), m_mb8.group(2), m_mb8.group(3)
                return f"{c}-{s} {n}"

        # 3. 8-character Car 5-digit sequence (e.g. 51H91991 -> 51H-919.91, 68A66888 -> 68A-668.88)
        if len(raw) == 8:
            m_car8 = re.match(r'^(\d{2})([A-Z]{1,2})(\d{5})$', raw)
            if m_car8:
                c, s, n = m_car8.group(1), m_car8.group(2), m_car8.group(3)
                return f"{c}{s}-{n[:3]}.{n[3:]}"

        # 4. 7-character Car 4-digit sequence (e.g. 30F1234 -> 30F-12.34)
        if len(raw) == 7:
            m_car7 = re.match(r'^(\d{2})([A-Z]{1,2})(\d{4})$', raw)
            if m_car7:
                c, s, n = m_car7.group(1), m_car7.group(2), m_car7.group(3)
                return f"{c}{s}-{n[:2]}.{n[2:]}"

        # General Fallback Pattern Matching
        if is_2line or vehicle_type in ["Motorbike", "Xe máy"]:
            m_mb_any = re.match(r'^(\d{2})([A-Z]{1}[A-Z0-9]{1})(\d{4,5})$', raw)
            if m_mb_any:
                c, s, n = m_mb_any.group(1), m_mb_any.group(2), m_mb_any.group(3)
                n_fmt = f"{n[:3]}.{n[3:]}" if len(n) == 5 else n
                return f"{c}-{s} {n_fmt}"

        m_car_any = re.match(r'^(\d{2})([A-Z]{1,2})(\d{4,5})$', raw)
        if m_car_any:
            c, s, n = m_car_any.group(1), m_car_any.group(2), m_car_any.group(3)
            n_fmt = f"{n[:3]}.{n[3:]}" if len(n) == 5 else f"{n[:2]}.{n[2:]}"
            return f"{c}{s}-{n_fmt}"

        return raw

    def truncate_excess_sequence_digits(self, raw: str) -> str:
        """
        Enforces Vietnamese License Plate rule: Sequence numbers after series code MUST NOT exceed 5 digits.
        Motorbike sequence can be 4 or 5 digits (e.g. 54-L1 9999 or 15-P1 037.37).
        Car sequence can be 4 or 5 digits (e.g. 30F-12.34 or 68A-668.88).
        """
        # If raw is a valid 9-character motorbike/car plate (2-char city + 2-char series + 5 sequence digits), DO NOT truncate!
        if len(raw) == 9 and re.match(r'^\d{2}[A-Z]{1}[A-Z0-9]{1}\d{5}$', raw):
            return raw

        # 1. Car 1-letter series (e.g. 30F) followed by 6+ sequence digits where total length >= 10
        m1 = re.match(r'^(\d{2}[A-Z]{1})(\d{5})\d{2,}$', raw)
        if m1:
            return m1.group(1) + m1.group(2)

        # 2. Car 2-letter series with 6+ sequence digits (e.g. 51LD123456 -> 51LD12345)
        m2 = re.match(r'^(\d{2}[A-Z]{2})(\d{5})\d+$', raw)
        if m2:
            return m2.group(1) + m2.group(2)

        # 3. Motorbike 2-char series with 6+ sequence digits (e.g. 15P1037379 -> 15P103737)
        m3 = re.match(r'^(\d{2}[A-Z]{1}[A-Z0-9]{1})(\d{5})\d+$', raw)
        if m3:
            return m3.group(1) + m3.group(2)

        return raw

    def correct_confusion_characters(self, raw: str) -> str:
        """
        Position-based character correction for Vietnamese license plates:
        - Positions 0 & 1: MUST be digits (City Code: 29, 30, 51, 59, 68...)
        - Position 2: MUST be a letter (Series Letter: A, B, C, D, E, F, G, H, K, L, M, N, P, S, T, U, V, X, Y, Z)
        - Positions 4 to End: MUST be digits (Sequence numbers)
        """
        chars = list(raw)
        n = len(chars)
        if n < 5:
            return raw

        digit_to_letter = {
            '4': 'A', '8': 'B', '0': 'D',
            '6': 'G', '5': 'S', '2': 'Z', '3': 'E', '9': 'P'
        }

        letter_to_digit = {
            'O': '0', 'D': '0', 'Q': '0',
            'I': '1', 'L': '1', 'J': '1',
            'S': '5', 'B': '8',
            'G': '6', 'Z': '2', 'A': '4', 'T': '7'
        }

        # 1. First 2 characters (City Code) -> MUST BE DIGITS
        for i in range(min(2, n)):
            if chars[i].isalpha() and chars[i] in letter_to_digit:
                chars[i] = letter_to_digit[chars[i]]

        # 2. 3rd character (Series Letter) -> MUST BE A LETTER
        if n >= 3 and chars[2].isdigit() and chars[2] in digit_to_letter:
            chars[2] = digit_to_letter[chars[2]]

        # 3. Sequence numbers (from index 4 to end) -> MUST BE DIGITS
        start_digits_idx = 4 if (n > 5 and chars[3].isalnum()) else 3

        for i in range(start_digits_idx, n):
            if chars[i].isalpha() and chars[i] in letter_to_digit:
                chars[i] = letter_to_digit[chars[i]]

        return "".join(chars)

    def read_plate(self, crop_image: np.ndarray, vehicle_type: str = "AUTO"):
        """
        Performs aspect-ratio aware OCR on a cropped plate image with resolution & contrast preprocessing.

        Returns:
            formatted_text (str): Standardized license plate text (e.g. 15-P1 037.37 or 54-L1 9999 or 68A-668.88)
            confidence (float): Confidence percentage (0.0 to 100.0)
        """
        if crop_image is None or crop_image.size == 0:
            return "", 0.0

        h, w = crop_image.shape[:2]
        aspect_ratio = w / max(1, h)
        is_2line = (aspect_ratio <= 2.0)

        prep_crop = self.preprocess_crop(crop_image)

        # Attempt 1: EasyOCR with preprocessed image
        if self.easyocr_reader is not None:
            try:
                res = self.easyocr_reader.readtext(prep_crop)
                if not res:
                    res = self.easyocr_reader.readtext(crop_image)

                if res:
                    items = []
                    for item in res:
                        box = item[0]
                        text = item[1]
                        score = item[2]
                        xs = [pt[0] for pt in box]
                        ys = [pt[1] for pt in box]
                        cx = sum(xs) / len(xs)
                        cy = sum(ys) / len(ys)
                        height = max(ys) - min(ys)
                        items.append({
                            "cx": cx, "cy": cy, "height": height,
                            "text": text, "confidence": score
                        })

                    items.sort(key=lambda x: x["cy"])
                    rows = []
                    current_row = [items[0]]
                    avg_height = items[0]["height"]

                    for item in items[1:]:
                        if abs(item["cy"] - current_row[-1]["cy"]) < (avg_height * 0.6):
                            current_row.append(item)
                            avg_height = sum(x["height"] for x in current_row) / len(current_row)
                        else:
                            rows.append(current_row)
                            current_row = [item]
                            avg_height = item["height"]
                    rows.append(current_row)

                    final_text_parts = []
                    confidences = []

                    for row in rows:
                        row.sort(key=lambda x: x["cx"])
                        row_text = "".join(x["text"] for x in row)
                        final_text_parts.append(row_text)
                        confidences.extend([x["confidence"] for x in row])

                    raw_combined = "".join(final_text_parts)
                    avg_score = (sum(confidences) / len(confidences)) * 100.0 if confidences else 0.0
                    return self.format_plate_text(raw_combined, is_2line, vehicle_type, lines=final_text_parts), round(avg_score, 1)
            except Exception as e:
                print(f"[ALPR EasyOCR Error] {e}")

        # Attempt 2: PaddleOCR with preprocessed image
        if self.ocr is not None:
            try:
                results = self.ocr.ocr(prep_crop)
                if not results or results[0] is None:
                    results = self.ocr.ocr(crop_image)

                if results and results[0] is not None:
                    items = []
                    if isinstance(results[0], dict):
                        res_dict = results[0]
                        rec_texts = res_dict.get('rec_texts', [])
                        rec_scores = res_dict.get('rec_scores', [])
                        rec_polys = res_dict.get('rec_polys', [])

                        for i in range(len(rec_texts)):
                            text = rec_texts[i]
                            conf = rec_scores[i]
                            box = rec_polys[i] if i < len(rec_polys) else None
                            if box is None or len(box) == 0:
                                continue
                            xs = [pt[0] for pt in box]
                            ys = [pt[1] for pt in box]
                            cx = sum(xs) / len(xs)
                            cy = sum(ys) / len(ys)
                            height = max(ys) - min(ys)

                            items.append({
                                "cx": cx, "cy": cy, "height": height,
                                "text": text, "confidence": conf
                            })
                    else:
                        for det in results[0]:
                            box = det[0]
                            text = det[1][0]
                            conf = det[1][1]
                            xs = [pt[0] for pt in box]
                            ys = [pt[1] for pt in box]
                            cx = sum(xs) / len(xs)
                            cy = sum(ys) / len(ys)
                            height = max(ys) - min(ys)

                            items.append({
                                "cx": cx, "cy": cy, "height": height,
                                "text": text, "confidence": conf
                            })

                    if items:
                        items.sort(key=lambda x: x["cy"])
                        rows = []
                        current_row = [items[0]]
                        avg_height = items[0]["height"]

                        for item in items[1:]:
                            if abs(item["cy"] - current_row[-1]["cy"]) < (avg_height * 0.6):
                                current_row.append(item)
                                avg_height = sum(x["height"] for x in current_row) / len(current_row)
                            else:
                                rows.append(current_row)
                                current_row = [item]
                                avg_height = item["height"]
                        rows.append(current_row)

                        final_text_parts = []
                        confidences = []

                        for row in rows:
                            row.sort(key=lambda x: x["cx"])
                            row_text = "".join(x["text"] for x in row)
                            final_text_parts.append(row_text)
                            confidences.extend([x["confidence"] for x in row])

                        raw_combined = "".join(final_text_parts)
                        formatted_text = self.format_plate_text(raw_combined, is_2line, vehicle_type, lines=final_text_parts)
                        avg_conf = (sum(confidences) / len(confidences)) * 100.0 if confidences else 0.0

                        return formatted_text, round(avg_conf, 1)

            except Exception as e:
                print(f"[ALPR PaddleOCR Error] {e}")

        return "", 0.0
