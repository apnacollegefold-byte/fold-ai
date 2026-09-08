import cv2
import numpy as np
import torch
from paddleocr import PaddleOCR

class ReceiptOCR:
    def __init__(self, lang='en'):
        """
        Initialize the OCR engine using PaddleOCR.
        PaddleOCR is used because it has excellent accuracy for
        multi-language text (English + Hindi) found on Indian receipts.
        """
        self.reader = PaddleOCR(use_angle_cls=True, lang=lang)

    # ─── OCR Extraction ─────────────────────────────────────────────────

    def extract_raw_text(self, image: np.ndarray) -> list:
        """Pass an image matrix to PaddleOCR and return bounding-box data."""
        # PaddleOCR expects a 3-channel BGR array
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        results = self.reader.ocr(image, cls=True)

        extracted = []
        if results and results[0]:
            for line in results[0]:     #line= [bbox, (text, confidence)]
                bbox = line[0]
                text = line[1][0]
                conf = line[1][1]
                extracted.append({"bbox": bbox, "text": text, "confidence": conf})
        return extracted

    # ─── Spatial Sorting ────────────────────────────────────────────────

    def sort_spatially(self, extracted_data: list, y_threshold: int = 15) -> list:
        """
        Steps:
            1. Compute center-Y and height for each text box.
            2. Group boxes whose center-Y values are close together (same row).
            3. Sort each group left-to-right by X position.
            4. Join each group into a single line string.
        """
        if not extracted_data:
            return []

        # Calculate position info for each text fragment
        for item in extracted_data:     #item["bbox"] is 4 corner points: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            ys = [pt[1] for pt in item["bbox"]]
            xs = [pt[0] for pt in item["bbox"]]
            item["center_y"] = sum(ys) / len(ys)
            item["min_x"] = min(xs)
            item["height"] = max(ys) - min(ys)

        # Dynamic threshold: 50% of average font height
        # This prevents merging separate rows while correctly grouping
        # fragments that belong to the same row but jitter vertically
        avg_height = sum(d["height"] for d in extracted_data) / len(extracted_data)
        dynamic_thresh = max(y_threshold, int(avg_height * 0.5))

        # Sort all fragments top-to-bottom
        extracted_data.sort(key=lambda d: d["center_y"])    #(bbox, text, confidence, center_y, min_x, height). .sort()

        # Group fragments into lines based on Y proximity
        lines = []
        current_line = [extracted_data[0]]
        current_y = extracted_data[0]["center_y"]

        for item in extracted_data[1:]:
            if abs(item["center_y"] - current_y) <= dynamic_thresh:
                # Same line — add to current group
                current_line.append(item)
                current_y = sum(i["center_y"] for i in current_line) / len(current_line)
            else:
                # New line — save current group and start a new one
                lines.append(current_line)
                current_line = [item]
                current_y = item["center_y"]
        lines.append(current_line)

        # Sort each line left-to-right and join into strings
        rebuilt = []
        for line in lines:
            line.sort(key=lambda d: d["min_x"])
            rebuilt.append(" ".join(item["text"] for item in line))
        return rebuilt

    # ─── End-to-End Pipeline ────────────────────────────────────────────

    def process_receipt(self, image_path: str) -> dict:

        img = cv2.imread(image_path)
        raw_data = self.extract_raw_text(img)
        all_lines = self.sort_spatially(raw_data)

        return {
            "all_lines": all_lines,
            "raw_text": " ".join(all_lines),
        }


# ═══════════════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    IMG = "../../assests/demo1.jpg"

    ocr = ReceiptOCR()
    result = ocr.process_receipt(IMG)

    print("\n========== RECONSTRUCTED LINES ==========")
    for line in result["all_lines"]:
        print(f"  >> {line}")

    print("\n========== RAW TEXT ==========")
    print(result["raw_text"])
