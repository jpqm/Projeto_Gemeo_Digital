import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage


class DetectionThread(QThread):
    frame_ready = pyqtSignal(QImage)
    detections_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    WARMUP_FRAMES = 5

    def __init__(self, cap, detector):
        super().__init__()
        self.cap = cap
        self.detector = detector

    def run(self):
        if not self.cap or not self.cap.isOpened():
            self.error_occurred.emit("Camera nao disponivel")
            return

        frame = None
        for _ in range(self.WARMUP_FRAMES):
            ok, f = self.cap.read()
            if ok:
                frame = f

        if frame is None:
            self.error_occurred.emit("Nao foi possivel capturar um frame da camera")
            return

        annotated, detections = self.detector.detect(frame)

        rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).copy()

        self.frame_ready.emit(image)
        self.detections_ready.emit(detections)
