from src.frontend.ui.core.qt import *

class ResourcePanel(QFrame):
    """
    AMEVA Premium Resource Monitor (Slim Horizontal Edition)
    - Real-time CPU, RAM, GPU Usage tracking
    - Optimized to fit into a single horizontal row for maximum space efficiency
    """
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setFixedHeight(52) # 높이를 52px로 극단적인 슬림화
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ctx.get_color('bg_panel')};
                border: 1px solid {ctx.get_color('border')};
                border-radius: 8px;
            }}
            QLabel {{ 
                color: {ctx.get_color('text')}; 
                font-size: 10px; 
                font-weight: bold; 
                border: none;
                background: transparent;
            }}
            QProgressBar {{
                background-color: {ctx.get_color('bg_dark')};
                border: none;
                border-radius: 2px;
                height: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {ctx.get_color('accent')};
                border-radius: 2px;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(15)
        
        # 3열 구성을 위한 헬퍼 함수
        def create_column(title):
            col_widget = QWidget()
            col_widget.setStyleSheet("background: transparent; border: none;")
            col_layout = QVBoxLayout(col_widget)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setSpacing(3)
            
            lbl = QLabel(title)
            bar = QProgressBar()
            bar.setTextVisible(False) # 바 내부의 난잡한 텍스트 숨김 (레이블에 표시되므로)
            bar.setFixedHeight(4)
            
            col_layout.addWidget(lbl)
            col_layout.addWidget(bar)
            return col_widget, lbl, bar

        # CPU
        cpu_col, self.cpu_lbl, self.cpu_bar = create_column("CPU: 0%")
        layout.addWidget(cpu_col)
        
        # RAM
        ram_col, self.ram_lbl, self.ram_bar = create_col = create_column("RAM: 0%")
        layout.addWidget(ram_col)
        
        # GPU
        gpu_col, self.gpu_lbl, self.gpu_bar = create_column("GPU: 0%")
        self.gpu_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {ctx.get_color('warning')}; }}")
        layout.addWidget(gpu_col)
        
    def update_stats(self, res):
        """API 결과({"cpu": n, "ram": n, "gpu": n})를 화면에 반영"""
        cpu = res.get("cpu", 0)
        ram = res.get("ram", 0)
        gpu = res.get("gpu", 0)
        
        self.cpu_lbl.setText(f"CPU: {cpu:.1f}%")
        self.cpu_bar.setValue(int(cpu))
        
        self.ram_lbl.setText(f"RAM: {ram:.1f}%")
        self.ram_bar.setValue(int(ram))
        
        self.gpu_lbl.setText(f"GPU: {gpu:.1f}%")
        self.gpu_bar.setValue(int(gpu))

