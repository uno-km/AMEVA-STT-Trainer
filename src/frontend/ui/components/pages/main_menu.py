from src.frontend.ui.core.qt import *

class MainMenuPage(QWidget):
    """
    [독립 컴포넌트] AMEVA MLOps 대시보드 웰컴 메인 메뉴 스크린
    """
    def __init__(self, parent_wizard):
        super().__init__()
        self.w = parent_wizard
        self.ctx = parent_wizard.ctx
        
        l = QVBoxLayout(self)
        l.setContentsMargins(30, 40, 30, 40)
        l.setSpacing(20)
        
        # Header Area
        header = QLabel("AMEVA STT TRAINER")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(f"font-size: 18px; font-weight: 900; color: {self.ctx.get_color('accent')}; letter-spacing: 2px;")
        l.addWidget(header)
        
        desc = QLabel("상태 기반 MLOps 자동화 시스템")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(f"color: {self.ctx.get_color('text_dim')}; margin-bottom: 20px;")
        l.addWidget(desc)
        
        l.addStretch()
        
        self.btn_new = QPushButton("🔥 새 모델 학습 (SOP 가동)")
        self.btn_new.setFixedHeight(55)
        self.btn_new.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {self.ctx.get_color('accent')}, stop:1 #4facfe);
                color: {self.ctx.get_color('bg_dark')};
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{ background: #4facfe; }}
        """)
        self.btn_new.clicked.connect(lambda: self.w.stack.setCurrentIndex(1))
        
        self.btn_load = QPushButton("📂 과거 기록 / 이어하기")
        self.btn_load.setFixedHeight(50)
        self.btn_load.clicked.connect(self.w.prepare_load_page)

        self.btn_manual = QPushButton("📦 수동 최적화 및 내보내기")
        self.btn_manual.setFixedHeight(50)
        self.btn_manual.clicked.connect(lambda: self.w.stack.setCurrentIndex(5))
        
        l.addWidget(self.btn_new)
        l.addWidget(self.btn_load)
        l.addWidget(self.btn_manual)
        l.addStretch()
