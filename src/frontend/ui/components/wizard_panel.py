from src.frontend.ui.core.qt import *
from PyQt6.QtWidgets import QFileDialog, QButtonGroup

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
        
        # --- Source Type Selection ---
        source_group = QButtonGroup(self)
        self.radio_youtube = QRadioButton("유튜브 URL 다운로드")
        self.radio_local = QRadioButton("기존 다운로드 폴더 사용")
        self.radio_youtube.setChecked(True)
        source_group.addButton(self.radio_youtube)
        source_group.addButton(self.radio_local)
        
        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.radio_youtube)
        radio_layout.addWidget(self.radio_local)
        form.addLayout(radio_layout)

        # YouTube specific inputs
        self.youtube_widget = QWidget()
        y_layout = QVBoxLayout(self.youtube_widget)
        y_layout.setContentsMargins(0,0,0,0)
        y_layout.addWidget(self._create_styled_label("유튜브 채널/영상 URL"))
        self.task_url_edit = self._create_styled_input(QLineEdit())
        self.task_url_edit.setPlaceholderText("https://www.youtube.com/...")
        y_layout.addWidget(self.task_url_edit)
        
        y_layout.addWidget(self._create_styled_label("최대 수집 영상 개수"))
        self.task_count_spin = self._create_styled_input(QSpinBox())
        self.task_count_spin.setRange(1, 100); self.task_count_spin.setValue(5)
        y_layout.addWidget(self.task_count_spin)
        form.addWidget(self.youtube_widget)

        # Local folder specific inputs
        self.local_widget = QWidget()
        local_layout = QVBoxLayout(self.local_widget)
        local_layout.setContentsMargins(0,0,0,0)
        local_layout.addWidget(self._create_styled_label("로컬 데이터셋 폴더 경로"))
        
        path_layout = QHBoxLayout()
        self.task_folder_edit = self._create_styled_input(QLineEdit())
        self.task_folder_edit.setPlaceholderText("예: C:/ameva/AMEVA-STT-Trainer/dataset/2026/05/17/SYUKA_123")
        self.btn_browse = QPushButton("탐색")
        self.btn_browse.setStyleSheet(f"background-color: {self.ctx.get_color('bg_dark')}; color: white; padding: 8px; border-radius: 6px; border: 1px solid {self.ctx.get_color('border')};")
        path_layout.addWidget(self.task_folder_edit)
        path_layout.addWidget(self.btn_browse)
        local_layout.addLayout(path_layout)
        form.addWidget(self.local_widget)

        self.local_widget.setVisible(False)

        def toggle_source():
            is_local = self.radio_local.isChecked()
            self.youtube_widget.setVisible(not is_local)
            self.local_widget.setVisible(is_local)
            
        self.radio_youtube.toggled.connect(toggle_source)
        
        def browse_folder():
            folder = QFileDialog.getExistingDirectory(self, "데이터셋 폴더 선택", "")
            if folder:
                self.task_folder_edit.setText(folder)
                
        self.btn_browse.clicked.connect(browse_folder)
        
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
        form.setSpacing(10)
        
        # --- 동적 UI 추가 시작 ---
        form.addWidget(self._create_styled_label("기반 모델 (Base Model)"))
        self.model_cb = self._create_styled_input(QComboBox())
        self.model_cb.addItems(["openai/whisper-tiny", "openai/whisper-small"])
        form.addWidget(self.model_cb)
        
        self.model_desc_lbl = QLabel("")
        self.model_desc_lbl.setStyleSheet("color: #aaaaaa; font-size: 11px; margin-bottom: 10px;")
        self.model_desc_lbl.setWordWrap(True)
        form.addWidget(self.model_desc_lbl)
        
        # 하이퍼파라미터 그리드 레이아웃
        grid = QGridLayout()
        grid.addWidget(self._create_styled_label("최대 학습 스텝 (Max Steps)"), 0, 0)
        self.max_steps_spin = self._create_styled_input(QSpinBox())
        self.max_steps_spin.setRange(10, 100000)
        grid.addWidget(self.max_steps_spin, 0, 1)
        
        grid.addWidget(self._create_styled_label("학습률 (Learning Rate)"), 1, 0)
        self.lr_edit = self._create_styled_input(QLineEdit())
        grid.addWidget(self.lr_edit, 1, 1)
        
        grid.addWidget(self._create_styled_label("물리 배치 (Batch Size)"), 2, 0)
        self.batch_spin = self._create_styled_input(QSpinBox())
        self.batch_spin.setRange(1, 64)
        grid.addWidget(self.batch_spin, 2, 1)
        
        grid.addWidget(self._create_styled_label("그래디언트 누적 (Grad. Accum.)"), 3, 0)
        self.grad_acc_spin = self._create_styled_input(QSpinBox())
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
        
        # --- 동적 UI 추가 끝 ---
        
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
        self.btn_create_sop = QPushButton("🚀 전체 파이프라인 가동")
        self.btn_create_sop.setFixedHeight(50)
        self.btn_create_sop.setStyleSheet(f"background-color: {self.ctx.get_color('success')}; color: {self.ctx.get_color('bg_dark')}; font-weight: bold; font-size: 14px;")
        
        # 하위 호환성을 위해 알리아스 유지 (dashboard.py 115번 라인 대응)
        self.btn_s3_start = self.btn_create_sop 
        
        btns.addWidget(btn_b); btns.addWidget(self.btn_create_sop)
        l.addLayout(btns)
        self.stack.addWidget(p)

    def init_load_page(self):
        p = QWidget(); l = QVBoxLayout(p)
        l.setContentsMargins(25, 25, 25, 25)
        l.addWidget(self._create_styled_label("📂 과거 학습 기록 및 이어하기", True))
        
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
        self.btn_load_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        l.addWidget(self.btn_load_back)
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
        btn_b.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        l.addWidget(btn_b)
        l.addStretch()
        self.stack.addWidget(p)

    def init_monitor_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Title
        self.mon_title = QLabel("파이프라인 관제 중...")
        self.mon_title.setFont(self.ctx.fonts['title'])
        layout.addWidget(self.mon_title)
        
        # Status Box
        status_box = QFrame()
        status_box.setStyleSheet(f"background-color: {self.ctx.get_color('bg_dark')}; border-radius: 8px; padding: 15px;")
        sb_layout = QVBoxLayout(status_box)
        
        self.mon_status = QLabel("현재 상태: IDLE")
        self.mon_status.setFont(self.ctx.fonts['main'])
        sb_layout.addWidget(self.mon_status)
        
        layout.addWidget(status_box)
        
        self.mon_task_name = QLabel("실시간 모니터링", font=self.ctx.fonts['title'])
        self.mon_task_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mon_task_name.setStyleSheet(f"color: {self.ctx.get_color('accent')}; margin-bottom: 20px;")
        layout.addWidget(self.mon_task_name)
        
        self.mon_steps = []
        for name in ["데이터 구축", "모델 학습", "최적화/내보내기"]:
            row_widget = QFrame()
            row_widget.setStyleSheet(f"background: {self.ctx.get_color('bg_dark')}; border-radius: 10px; border: 1px solid {self.ctx.get_color('border')};")
            row = QHBoxLayout(row_widget)
            
            lbl_n = QLabel(name); lbl_n.setStyleSheet("font-weight: bold; border: none; padding-left: 10px;")
            lbl_s = QLabel("대기 중"); lbl_s.setStyleSheet(f"color: {self.ctx.get_color('text_dim')}; border: none; padding-right: 10px;")
            
            row.addWidget(lbl_n); row.addStretch(); row.addWidget(lbl_s)
            self.mon_steps.append(lbl_s)
            layout.addWidget(row_widget)
            
        layout.addStretch()
        
        # 강제 종료 버튼
        self.btn_force_stop = QPushButton("🛑 작업 강제 종료 (체크포인트 저장)")
        self.btn_force_stop.setFixedHeight(40)
        self.btn_force_stop.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.ctx.get_color('error')};
                color: #11111b;
                font-weight: bold;
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #f5a6bd;
            }}
        """)
        layout.addWidget(self.btn_force_stop)
        
        # 메인으로 돌아가기 버튼 (대기/종료 시에만 보이게 할 예정)
        self.btn_mon_back = QPushButton("🔙 메인으로 돌아가기")
        self.btn_mon_back.setFixedHeight(40)
        self.btn_mon_back.setStyleSheet(f"""
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
        self.btn_mon_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        layout.addWidget(self.btn_mon_back)
        
        self.stack.addWidget(page)

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
