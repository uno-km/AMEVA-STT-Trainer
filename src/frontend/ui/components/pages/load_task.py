from src.frontend.ui.core.qt import *

class LoadPage(QWidget):
    """
    [독립 컴포넌트] 과거 기록 리스트 로드 및 2단계 중단 작업 복구/이어하기 화면
    """
    def __init__(self, parent_wizard):
        super().__init__()
        self.w = parent_wizard
        self.ctx = parent_wizard.ctx
        
        l = QVBoxLayout(self)
        l.setContentsMargins(25, 25, 25, 25)
        l.addWidget(self.w._create_styled_label("📂 과거 학습 기록 및 이어하기", True))
        
        desc = QLabel("과거에 수행했거나 진행 중 멈춘 모든 태스크 목록입니다. 목록에서 복구할 대상을 선택하세요.")
        desc.setStyleSheet(f"color: {self.ctx.get_color('text_dim')}; font-size: 11px; margin-bottom: 10px;")
        desc.setWordWrap(True)
        l.addWidget(desc)
        
        self.task_list_widget = QListWidget()
        self.task_list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {self.ctx.get_color('bg_dark')};
                border: 1px solid {self.ctx.get_color('border')};
                border-radius: 8px;
                color: white;
                padding: 6px;
            }}
            QListWidget::item {{
                background-color: {self.ctx.get_color('bg_panel')};
                border: 1px solid {self.ctx.get_color('border')};
                border-radius: 6px;
                margin: 4px 2px;
                padding: 12px;
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: {self.ctx.get_color('border')};
                border-color: {self.ctx.get_color('accent')};
            }}
            QListWidget::item:selected {{
                background-color: {self.ctx.get_color('accent')};
                color: {self.ctx.get_color('bg_dark')};
                font-weight: bold;
            }}
        """)
        l.addWidget(self.task_list_widget)
        
        self.btn_load_confirm = QPushButton("선택한 태스크 불러오기 🔓")
        self.btn_load_confirm.setFixedHeight(45)
        self.btn_load_confirm.setStyleSheet(f"background-color: {self.ctx.get_color('accent')}; color: {self.ctx.get_color('bg_dark')}; font-weight: bold; font-size: 13px;")
        l.addWidget(self.btn_load_confirm)
        
        self.btn_load_back = QPushButton("🔙 메인으로 돌아가기")
        self.btn_load_back.setFixedHeight(40)
        self.btn_load_back.setStyleSheet(f"""
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
        self.btn_load_back.clicked.connect(lambda: self.w.stack.setCurrentIndex(0))
        l.addWidget(self.btn_load_back)
        l.addStretch()
