from src.frontend.ui.core.qt import *

class Step2Page(QWidget):
    """
    [독립 컴포넌트] SOP 2단계: Whisper 모델 미세조정(Fine-Tuning) 파라미터 설정 화면
    """
    def __init__(self, parent_wizard):
        super().__init__()
        self.w = parent_wizard
        self.ctx = parent_wizard.ctx
        
        l = QVBoxLayout(self)
        l.setContentsMargins(25, 25, 25, 25)
        
        l.addWidget(self.w._create_styled_label("STEP 2: 모델 학습(Fine-Tuning)", True))
        
        form = QVBoxLayout()
        form.setSpacing(10)
        
        # --- 기반 모델 선택 ---
        form.addWidget(self.w._create_styled_label("기반 모델 (Base Model)"))
        self.model_cb = self.w._create_styled_input(QComboBox())
        self.model_cb.addItems(["openai/whisper-tiny", "openai/whisper-small"])
        form.addWidget(self.model_cb)
        
        self.model_desc_lbl = QLabel("")
        self.model_desc_lbl.setStyleSheet("color: #aaaaaa; font-size: 11px; margin-bottom: 10px;")
        self.model_desc_lbl.setWordWrap(True)
        form.addWidget(self.model_desc_lbl)
        
        # 하이퍼파라미터 그리드 레이아웃
        grid = QGridLayout()
        grid.addWidget(self.w._create_styled_label("최대 학습 스텝 (Max Steps)"), 0, 0)
        self.max_steps_spin = self.w._create_styled_input(QSpinBox())
        self.max_steps_spin.setRange(10, 100000)
        grid.addWidget(self.max_steps_spin, 0, 1)
        
        grid.addWidget(self.w._create_styled_label("학습률 (Learning Rate)"), 1, 0)
        self.lr_edit = self.w._create_styled_input(QLineEdit())
        grid.addWidget(self.lr_edit, 1, 1)
        
        grid.addWidget(self.w._create_styled_label("물리 배치 (Batch Size)"), 2, 0)
        self.batch_spin = self.w._create_styled_input(QSpinBox())
        self.batch_spin.setRange(1, 64)
        grid.addWidget(self.batch_spin, 2, 1)
        
        grid.addWidget(self.w._create_styled_label("그래디언트 누적 (Grad. Accum.)"), 3, 0)
        self.grad_acc_spin = self.w._create_styled_input(QSpinBox())
        self.grad_acc_spin.setRange(1, 128)
        grid.addWidget(self.grad_acc_spin, 3, 1)
        
        form.addLayout(grid)
        l.addLayout(form)
        
        # --- 이벤트 연결 (모델 변경 시 기본값 세팅) ---
        from src.core.config import MODEL_DEFAULTS
        
        def update_hyperparams(index=0):
            model_id = self.model_cb.currentText()
            defaults = MODEL_DEFAULTS.get(model_id, MODEL_DEFAULTS["openai/whisper-tiny"])
            
            self.model_desc_lbl.setText(defaults["description"])
            self.max_steps_spin.setValue(defaults["max_steps"])
            self.lr_edit.setText(str(defaults["learning_rate"]))
            self.batch_spin.setValue(defaults["batch_size"])
            self.grad_acc_spin.setValue(defaults["gradient_accumulation"])
            
        self.model_cb.currentIndexChanged.connect(update_hyperparams)
        # 초기화 시 첫 번째 항목 기준으로 한 번 실행
        update_hyperparams()
        
        l.addStretch()
        
        btns = QHBoxLayout()
        btn_b = QPushButton("⬅ 1단계로"); btn_b.clicked.connect(lambda: self.w.stack.setCurrentIndex(1))
        
        self.btn_s2_start = QPushButton("2단계까지 시작 🚀")
        self.btn_s2_start.setFixedHeight(45)
        self.btn_s2_start.setStyleSheet(f"border: 1px solid {self.ctx.get_color('warning')}; color: {self.ctx.get_color('warning')};")
        
        self.btn_s2_next = QPushButton("3단계 이어설정 ➡️")
        self.btn_s2_next.setFixedHeight(45)
        self.btn_s2_next.setStyleSheet(f"background-color: {self.ctx.get_color('warning')}; color: {self.ctx.get_color('bg_dark')}; font-weight: bold;")
        self.btn_s2_next.clicked.connect(lambda: self.w.stack.setCurrentIndex(3))
        
        btns.addWidget(btn_b); btns.addWidget(self.btn_s2_start); btns.addWidget(self.btn_s2_next)
        l.addLayout(btns)
