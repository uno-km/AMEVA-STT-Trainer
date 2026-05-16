from src.frontend.ui.core.qt import *

class WizardPanel(QWidget):
    """태스크 생성/로드 단계를 관리하는 심플 위저드"""
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {ctx.get_color('bg_panel')}; border: 1px solid {ctx.get_color('border')}; border-radius: 8px;")
        
        # --- Page 0: Main Menu ---
        self.p0 = QWidget()
        l0 = QVBoxLayout(self.p0)
        l0.setSpacing(10)
        l0.addStretch()
        
        self.btn_goto_new = QPushButton("🔥 새 모델 학습하기")
        self.btn_goto_new.setFixedHeight(45)
        self.btn_goto_new.setStyleSheet(f"background-color: {ctx.get_color('accent')}; color: {ctx.get_color('bg_dark')}; font-weight: bold;")
        self.btn_goto_new.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        
        self.btn_goto_load = QPushButton("📂 과거 기록 불러오기")
        self.btn_goto_load.setFixedHeight(45)
        self.btn_goto_load.clicked.connect(self.prepare_load_page)
        
        l0.addWidget(self.btn_goto_new)
        l0.addWidget(self.btn_goto_load)
        l0.addStretch()
        self.stack.addWidget(self.p0)
        
        # --- Page 1: New Task Form ---
        self.p1 = QWidget()
        l1 = QVBoxLayout(self.p1)
        l1.addWidget(QLabel("📝 새 태스크 설정", font=ctx.fonts['title']))
        
        self.task_name_input = QLineEdit()
        self.task_name_input.setPlaceholderText("태스크 이름을 입력하세요...")
        self.task_name_input.setStyleSheet(f"padding: 8px; background: {ctx.get_color('bg_dark')};")
        l1.addWidget(self.task_name_input)
        
        self.model_cb = QComboBox()
        self.model_cb.addItems(["Whisper Large-v3", "Whisper Medium", "Whisper Small"])
        l1.addWidget(self.model_cb)
        
        self.btn_start = QPushButton("🚀 학습 시작")
        self.btn_start.setFixedHeight(35)
        l1.addWidget(self.btn_start)
        
        btn_back1 = QPushButton("🔙 뒤로가기")
        btn_back1.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        l1.addWidget(btn_back1)
        l1.addStretch()
        self.stack.addWidget(self.p1)
        
        # --- Page 2: Load Task Form ---
        self.p2 = QWidget()
        l2 = QVBoxLayout(self.p2)
        l2.addWidget(QLabel("📂 과거 기록 선택", font=ctx.fonts['title']))
        
        self.task_list_cb = QComboBox()
        self.task_list_cb.setStyleSheet(f"padding: 5px; background: {ctx.get_color('bg_dark')};")
        l2.addWidget(self.task_list_cb)
        
        self.btn_load_confirm = QPushButton("📥 리포트 열기")
        self.btn_load_confirm.setFixedHeight(35)
        l2.addWidget(self.btn_load_confirm)
        
        btn_back2 = QPushButton("🔙 뒤로가기")
        btn_back2.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        l2.addWidget(btn_back2)
        l2.addStretch()
        self.stack.addWidget(self.p2)
        
        layout.addWidget(self.stack)

    def prepare_load_page(self):
        # 대시보드에서 데이터를 채우도록 신호를 주거나 직접 API 호출 (여기서는 페이지 이동만)
        self.stack.setCurrentIndex(2)

    def get_task_name(self):
        return self.task_name_input.text()
