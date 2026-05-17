from src.frontend.ui.core.qt import *

class ResourcePanel(QFrame):
    """
    AMEVA Premium Resource Monitor
    - Real-time CPU, RAM, GPU Usage tracking
    - Modern dark aesthetics with progress bars
    """
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setFixedWidth(200)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ctx.get_color('bg_panel')};
                border: 1px solid {ctx.get_color('border')};
                border-radius: 10px;
                padding: 10px;
            }}
            QLabel {{ color: {ctx.get_color('text')}; font-size: 11px; font-weight: bold; border: none; }}
            QProgressBar {{
                background-color: {ctx.get_color('bg_dark')};
                border: none;
                border-radius: 4px;
                height: 6px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {ctx.get_color('accent')};
                border-radius: 4px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # CPU
        self.cpu_lbl = QLabel("CPU USAGE: 0%")
        self.cpu_bar = QProgressBar()
        layout.addWidget(self.cpu_lbl)
        layout.addWidget(self.cpu_bar)
        
        # RAM
        self.ram_lbl = QLabel("RAM USAGE: 0%")
        self.ram_bar = QProgressBar()
        layout.addWidget(self.ram_lbl)
        layout.addWidget(self.ram_bar)
        
        # GPU
        self.gpu_lbl = QLabel("GPU USAGE: 0%")
        self.gpu_bar = QProgressBar()
        self.gpu_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {ctx.get_color('warning')}; }}")
        layout.addWidget(self.gpu_lbl)
        layout.addWidget(self.gpu_bar)
        
    def update_stats(self, res):
        """API 결과({"cpu": n, "ram": n, "gpu": n})를 화면에 반영"""
        cpu = res.get("cpu", 0)
        ram = res.get("ram", 0)
        gpu = res.get("gpu", 0)
        
        self.cpu_lbl.setText(f"CPU USAGE: {cpu:.1f}%")
        self.cpu_bar.setValue(int(cpu))
        
        self.ram_lbl.setText(f"RAM USAGE: {ram:.1f}%")
        self.ram_bar.setValue(int(ram))
        
        self.gpu_lbl.setText(f"GPU USAGE: {gpu:.1f}%")
        self.gpu_bar.setValue(int(gpu))
