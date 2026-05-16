from src.frontend.ui.core.qt import *

class ResourcePanel(QFrame):
    """좌측 하단에 위치할 슬림한 리소스 모니터링 패널"""
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #181825; border-radius: 8px; padding: 5px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Info row
        self.cpu_info_label = QLabel("CPU: --% | RAM: --MB")
        self.cpu_info_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.cpu_info_label.setStyleSheet("color: #a6e3a1;")
        layout.addWidget(self.cpu_info_label)
        
        # Slider row
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("Threads:", font=QFont("Segoe UI", 8)))
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 16)
        self.slider.setValue(16)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal { border-radius: 2px; height: 4px; background: #313244; }
            QSlider::handle:horizontal { background: #89b4fa; width: 10px; height: 10px; margin: -3px 0; border-radius: 5px; }
        """)
        slider_layout.addWidget(self.slider)
        
        self.threads_label = QLabel("16/16")
        self.threads_label.setFont(QFont("Segoe UI", 8))
        slider_layout.addWidget(self.threads_label)
        
        layout.addLayout(slider_layout)

    def update_status(self, cpu_pct, mem_mb, allocated, total):
        self.cpu_info_label.setText(f"CPU: {cpu_pct}% | RAM: {mem_mb:.0f}MB")
        self.threads_label.setText(f"{allocated}/{total}")
        if self.slider.maximum() != total:
            self.slider.setMaximum(total)
            self.slider.setValue(allocated)
