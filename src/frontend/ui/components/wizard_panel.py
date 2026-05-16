from src.frontend.ui.core.qt import *

class WizardPanel(QWidget):
    """
    AMEVA Premium SOP Wizard Panel
    - 3-Stage Linear SOP Flow
    - Real-time Monitoring Page
    - High-End Aesthetics with Rich Styling
    """
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"""
            QStackedWidget {{
                background-color: {ctx.get_color('bg_panel')};
                border: 1px solid {ctx.get_color('border')};
                border-radius: 12px;
            }}
        """)
        
        # --- Initialize Pages ---
        self.init_main_menu()      # Index 0
        self.init_sop_step1()      # Index 1
        self.init_sop_step2()      # Index 2
        self.init_sop_step3()      # Index 3
        self.init_load_page()      # Index 4
        self.init_manual_export()  # Index 5
        self.init_monitor_page()   # Index 6

        layout.addWidget(self.stack)

    def _create_styled_label(self, text, is_title=False):
        lbl = QLabel(text)
        if is_title:
            lbl.setFont(self.ctx.fonts['title'])
            lbl.setStyleSheet(f"color: {self.ctx.get_color('accent')}; margin-bottom: 10px;")
        else:
            lbl.setStyleSheet(f"color: {self.ctx.get_color('text')}; font-weight: normal;")
        return lbl

    def _create_styled_input(self, widget):
        widget.setStyleSheet(f"""
            padding: 8px;
            background-color: {self.ctx.get_color('bg_dark')};
            border: 1px solid {self.ctx.get_color('border')};
            border-radius: 6px;
            color: white;
        """)
        return widget

    def init_main_menu(self):
        p = QWidget()
        l = QVBoxLayout(p)
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
        self.btn_new.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        
        self.btn_load = QPushButton("📂 과거 기록 / 이어하기")
        self.btn_load.setFixedHeight(50)
        self.btn_load.clicked.connect(self.prepare_load_page)

        self.btn_manual = QPushButton("📦 수동 최적화 및 내보내기")
        self.btn_manual.setFixedHeight(50)
        
        l.addWidget(self.btn_new)
        l.addWidget(self.btn_load)
        l.addWidget(self.btn_manual)
        l.addStretch()
        self.stack.addWidget(p)

    def init_sop_step1(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(25, 25, 25, 25)
        
        l.addWidget(self._create_styled_label("STEP 1: 데이터 구축", True))
        
        form = QVBoxLayout()
        form.setSpacing(12)
        
        form.addWidget(self._create_styled_label("태스크 명칭 (영문/숫자)"))
        self.task_name_edit = self._create_styled_input(QLineEdit())
        self.task_name_edit.setPlaceholderText("예: Syuka_Project_2026")
        form.addWidget(self.task_name_edit)
        
        form.addWidget(self._create_styled_label("유튜브 채널/영상 URL"))
        self.task_url_edit = self._create_styled_input(QLineEdit())
        self.task_url_edit.setPlaceholderText("https://www.youtube.com/...")
        form.addWidget(self.task_url_edit)
        
        form.addWidget(self._create_styled_label("최대 수집 영상 개수"))
        self.task_count_spin = self._create_styled_input(QSpinBox())
        self.task_count_spin.setRange(1, 100); self.task_count_spin.setValue(5)
        form.addWidget(self.task_count_spin)
        
        l.addLayout(form)
        l.addStretch()
        
        btns = QHBoxLayout()
        self.btn_s1_back = QPushButton("🔙 취소")
        self.btn_s1_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        
        self.btn_s1_start = QPushButton("1단계만 시작 🚀")
        self.btn_s1_start.setFixedHeight(45)
        self.btn_s1_start.setStyleSheet(f"border: 1px solid {self.ctx.get_color('accent')}; color: {self.ctx.get_color('accent')};")
        
        self.btn_s1_next = QPushButton("2단계 이어설정 ➡️")
        self.btn_s1_next.setFixedHeight(45)
        self.btn_s1_next.setStyleSheet(f"background-color: {self.ctx.get_color('accent')}; color: {self.ctx.get_color('bg_dark')}; font-weight: bold;")
        self.btn_s1_next.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        
        btns.addWidget(self.btn_s1_back)
        btns.addWidget(self.btn_s1_start)
        btns.addWidget(self.btn_s1_next)
        l.addLayout(btns)
        self.stack.addWidget(p)

    def init_sop_step2(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(25, 25, 25, 25)
        
        l.addWidget(self._create_styled_label("STEP 2: 모델 학습(Fine-Tuning)", True))
        
        form = QVBoxLayout()
        form.addWidget(self._create_styled_label("최대 학습 스텝 (Max Steps)"))
        self.max_steps_spin = self._create_styled_input(QSpinBox())
        self.max_steps_spin.setRange(10, 100000); self.max_steps_spin.setValue(100)
        form.addWidget(self.max_steps_spin)
        l.addLayout(form)
        
        l.addStretch()
        
        btns = QHBoxLayout()
        btn_b = QPushButton("⬅ 1단계로"); btn_b.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        
        self.btn_s2_start = QPushButton("2단계까지 시작 🚀")
        self.btn_s2_start.setFixedHeight(45)
        self.btn_s2_start.setStyleSheet(f"border: 1px solid {self.ctx.get_color('warning')}; color: {self.ctx.get_color('warning')};")
        
        self.btn_s2_next = QPushButton("3단계 이어설정 ➡️")
        self.btn_s2_next.setFixedHeight(45)
        self.btn_s2_next.setStyleSheet(f"background-color: {self.ctx.get_color('warning')}; color: {self.ctx.get_color('bg_dark')}; font-weight: bold;")
        self.btn_s2_next.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        
        btns.addWidget(btn_b); btns.addWidget(self.btn_s2_start); btns.addWidget(self.btn_s2_next)
        l.addLayout(btns)
        self.stack.addWidget(p)

    def init_sop_step3(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(25, 25, 25, 25)
        l.addWidget(self._create_styled_label("STEP 3: 최적화 및 내보내기", True))
        
        form = QVBoxLayout()
        self.auto_export_cb = QCheckBox("자동 최적화 및 내보내기 활성화")
        self.auto_export_cb.setChecked(True)
        form.addWidget(self.auto_export_cb)
        
        form.addWidget(self._create_styled_label("양자화 방식 (Quantization)"))
        self.auto_method_cb = self._create_styled_input(QComboBox())
        self.auto_method_cb.addItems(["q4_0 (추천)", "q4_k_m", "q5_0", "q5_k_m", "q8_0"])
        form.addWidget(self.auto_method_cb)
        
        l.addLayout(form)
        l.addStretch()
        
        btns = QHBoxLayout()
        btn_b = QPushButton("⬅ 2단계로"); btn_b.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        self.btn_s3_start = QPushButton("🚀 전체 파이프라인 가동")
        self.btn_s3_start.setFixedHeight(50)
        self.btn_s3_start.setStyleSheet(f"background-color: {self.ctx.get_color('success')}; color: {self.ctx.get_color('bg_dark')}; font-weight: bold; font-size: 14px;")
        
        btns.addWidget(btn_b); btns.addWidget(self.btn_s3_start)
        l.addLayout(btns)
        self.stack.addWidget(p)

    def init_load_page(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(25, 25, 25, 25)
        l.addWidget(self._create_styled_label("📂 과거 기록 불러오기", True))
        
        self.task_list_cb = self._create_styled_input(QComboBox())
        l.addWidget(self.task_list_cb)
        
        self.btn_load_confirm = QPushButton("이전 결과 확인 / 이어하기")
        self.btn_load_confirm.setFixedHeight(45)
        self.btn_load_confirm.setStyleSheet(f"background-color: {self.ctx.get_color('accent')}; color: {self.ctx.get_color('bg_dark')}; font-weight: bold;")
        l.addWidget(self.btn_load_confirm)
        
        btn_b = QPushButton("⬅ 메인으로"); btn_b.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        l.addWidget(btn_b)
        l.addStretch()
        self.stack.addWidget(p)

    def init_manual_export(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(25, 25, 25, 25)
        l.addWidget(self._create_styled_label("📦 수동 최적화", True))
        
        self.export_task_cb = self._create_styled_input(QComboBox())
        l.addWidget(self.export_task_cb)
        
        l.addWidget(self._create_styled_label("양자화 방식"))
        self.manual_method_cb = self._create_styled_input(QComboBox())
        self.manual_method_cb.addItems(["q4_0", "q4_k_m", "q8_0"])
        l.addWidget(self.manual_method_cb)
        
        self.btn_export_run = QPushButton("🚀 내보내기 실행")
        self.btn_export_run.setFixedHeight(45)
        self.btn_export_run.setStyleSheet(f"background-color: {self.ctx.get_color('warning')}; color: {self.ctx.get_color('bg_dark')}; font-weight: bold;")
        l.addWidget(self.btn_export_run)
        
        btn_b = QPushButton("⬅ 메인으로"); btn_b.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        l.addWidget(btn_b)
        l.addStretch()
        self.stack.addWidget(p)

    def init_monitor_page(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(30, 30, 30, 30)
        
        self.mon_task_name = QLabel("실시간 모니터링", font=self.ctx.fonts['title'])
        self.mon_task_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mon_task_name.setStyleSheet(f"color: {self.ctx.get_color('accent')}; margin-bottom: 20px;")
        l.addWidget(self.mon_task_name)
        
        self.mon_steps = []
        for name in ["데이터 구축", "모델 학습", "최적화/내보내기"]:
            row_widget = QFrame()
            row_widget.setStyleSheet(f"background: {self.ctx.get_color('bg_dark')}; border-radius: 10px; border: 1px solid {self.ctx.get_color('border')};")
            row = QHBoxLayout(row_widget)
            
            lbl_n = QLabel(name); lbl_n.setStyleSheet("font-weight: bold; border: none; padding-left: 10px;")
            lbl_s = QLabel("대기 중"); lbl_s.setStyleSheet(f"color: {self.ctx.get_color('text_dim')}; border: none; padding-right: 10px;")
            
            row.addWidget(lbl_n); row.addStretch(); row.addWidget(lbl_s)
            self.mon_steps.append(lbl_s)
            l.addWidget(row_widget)
            
        l.addStretch()
        btn_back = QPushButton("메인으로 (백그라운드 유지)")
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        l.addWidget(btn_back)
        self.stack.addWidget(p)

    def update_monitor(self, task_name, level, status):
        self.mon_task_name.setText(f"🏃 {task_name}")
        for i, lbl in enumerate(self.mon_steps):
            step_lv = i + 1
            if step_lv < level:
                lbl.setText("✅ 완료"); lbl.setStyleSheet(f"color: {self.ctx.get_color('success')}; border: none;")
            elif step_lv == level:
                txt = "⏳ 진행 중" if status == "RUNNING" else ("✅ 완료" if status == "SUCCESS" else "❌ 실패")
                color = self.ctx.get_color("warning") if status == "RUNNING" else (self.ctx.get_color("success") if status == "SUCCESS" else self.ctx.get_color("error"))
                lbl.setText(txt); lbl.setStyleSheet(f"color: {color}; font-weight: bold; border: none;")
            else:
                lbl.setText("💤 대기"); lbl.setStyleSheet(f"color: {self.ctx.get_color('text_dim')}; border: none;")

    def prepare_load_page(self):
        self.stack.setCurrentIndex(4)
