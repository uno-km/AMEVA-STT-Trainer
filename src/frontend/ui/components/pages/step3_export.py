from src.frontend.ui.core.qt import *

class Step3Page(QWidget):
    """
    [독립 컴포넌트] SOP 3단계: 완성형 모델의 GGUF 양자화 최적화 설정 화면
    """
    def __init__(self, parent_wizard):
        super().__init__()
        self.w = parent_wizard
        self.ctx = parent_wizard.ctx
        
        l = QVBoxLayout(self)
        l.setContentsMargins(25, 25, 25, 25)
        l.addWidget(self.w._create_styled_label("STEP 3: 최적화 및 내보내기", True))
        
        form = QVBoxLayout()
        self.auto_export_cb = QCheckBox("자동 최적화 및 내보내기 활성화")
        self.auto_export_cb.setChecked(True)
        form.addWidget(self.auto_export_cb)
        
        form.addWidget(self.w._create_styled_label("양자화 방식 (Quantization)"))
        self.auto_method_cb = self.w._create_styled_input(QComboBox())
        self.auto_method_cb.addItems(["q4_0 (추천)", "q4_k_m", "q5_0", "q5_k_m", "q8_0"])
        form.addWidget(self.auto_method_cb)
        
        l.addLayout(form)
        l.addStretch()
        
        btns = QHBoxLayout()
        btn_b = QPushButton("⬅ 2단계로"); btn_b.clicked.connect(lambda: self.w.stack.setCurrentIndex(2))
        self.btn_create_sop = QPushButton("🚀 전체 파이프라인 가동")
        self.btn_create_sop.setFixedHeight(50)
        self.btn_create_sop.setStyleSheet(f"background-color: {self.ctx.get_color('success')}; color: {self.ctx.get_color('bg_dark')}; font-weight: bold; font-size: 14px;")
        
        # 하위 호환성을 위해 알리아스 유지
        self.btn_s3_start = self.btn_create_sop 
        
        btns.addWidget(btn_b); btns.addWidget(self.btn_create_sop)
        l.addLayout(btns)
