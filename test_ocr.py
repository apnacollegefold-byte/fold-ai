"""
Module 16 demo script — run this directly to show students the Roboflow
UPI logo detector working standalone, with no FastAPI endpoint needed yet
(that wiring happens in Module 18).

Run with:
    python test_upi_detector.py path/to/screenshot.jpg
"""

import sys
import os

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
sys.path.insert(0, SRC_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from ocr.upi_detector import UPIAppDetector


def main():
    api_key = os.getenv("ROBOFLOW_API_KEY")
    if not api_key:
        print("Set ROBOFLOW_API_KEY in .env first.")
        return

    model_id = os.getenv("ROBOFLOW_UPI_MODEL_ID", "document-classification/upi/1")
    image_path = sys.argv[1] if len(sys.argv) > 1 else "./assests/demo1.jpg"

    detector = UPIAppDetector(api_key=api_key, model_id=model_id)

    print(f"Running detection on: {image_path}")
    result = detector.detect_with_debug(image_path)
    print("\nFull debug payload:", result)
    provider = detector.detect(image_path)
    print(f"\nDetected provider: {provider}")


if __name__ == "__main__":
    main()
