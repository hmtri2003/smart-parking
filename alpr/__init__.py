# ALPR Module Initialization
from .detector import LicensePlateDetector
from .ocr import LicensePlateOCR

__all__ = ["LicensePlateDetector", "LicensePlateOCR"]
