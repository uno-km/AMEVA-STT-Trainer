from src.frontend.ui.core.qt import *

class ManualExportPage(QWidget):
    """
    [독립 컴포넌트] 특정 과거 태스크를 임의 선택하여 별도 양자화 GGUF 모델을 추출하는 화면
    """
    def __init__(self, parent_wizard):
        super().__init__()
        self.w = parent_wizard
        self.ctx = parent_wizard.ctx
        
        l = QVBoxLayout(self)
        l.setContentsMargins(25, 25, 25, 25)
        l.addWidget(self.w._create_styled_label("📦 수동 최적화", True))
        
        self.export_task_cb = self.w._create_styled_input(QComboBox())
        l.addWidget(self.export_task_cb)
        
        l.addWidget(self.w._create_styled_label("양자화 방식"))
        self.manual_method_cb = self.w._create_styled_input(QComboBox())
        self.manual_method_cb.addItems(["q4_0", "q4_k_m", "q8_0"])
        l.addWidget(self.manual_method_cb)
        
        self.btn_export_run = QPushButton("🚀 내보내기 실행")
        self.btn_export_run.setFixedHeight(45)
        self.btn_export_run.setStyleSheet(f"background-color: {self.ctx.get_color('warning')}; color: {self.ctx.get_color('bg_dark')}; font-weight: bold;")
        l.addWidget(self.btn_export_run)
        
        btn_b = QPushButton("⬅ 메인으로")
        btn_b.setFixedHeight(40)
        btn_b.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.ctx.get_color('bg_dark')};
                color: white;
                border: 1px solid {self.ctx.get_color('border')};
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.ctx.get_color('border')};
                border-color: {self.ctx.get_color('accent')};
            }}
        """)
        btn_b.clicked.connect(lambda: self.w.stack.setCurrentIndex(0))
        l.addWidget(btn_b)
        l.addStretch()
