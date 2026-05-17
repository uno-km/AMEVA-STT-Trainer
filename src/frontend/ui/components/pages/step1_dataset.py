from src.frontend.ui.core.qt import *
from PyQt6.QtWidgets import QFileDialog, QButtonGroup

class Step1Page(QWidget):
    """
    [독립 컴포넌트] SOP 1단계: 데이터 구축 및 전처리 설정 화면
    """
    def __init__(self, parent_wizard):
        super().__init__()
        self.w = parent_wizard
        self.ctx = parent_wizard.ctx
        
        l = QVBoxLayout(self)
        l.setContentsMargins(25, 25, 25, 25)
        
        l.addWidget(self.w._create_styled_label("STEP 1: 데이터 구축", True))
        
        form = QVBoxLayout()
        form.setSpacing(12)
        
        form.addWidget(self.w._create_styled_label("태스크 명칭 (영문/숫자)"))
        self.task_name_edit = self.w._create_styled_input(QLineEdit())
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
        y_layout.addWidget(self.w._create_styled_label("유튜브 채널/영상 URL"))
        self.task_url_edit = self.w._create_styled_input(QLineEdit())
        self.task_url_edit.setPlaceholderText("https://www.youtube.com/...")
        y_layout.addWidget(self.task_url_edit)
        
        y_layout.addWidget(self.w._create_styled_label("최대 수집 영상 개수"))
        self.task_count_spin = self.w._create_styled_input(QSpinBox())
        self.task_count_spin.setRange(1, 100); self.task_count_spin.setValue(5)
        y_layout.addWidget(self.task_count_spin)
        form.addWidget(self.youtube_widget)

        # Local folder specific inputs
        self.local_widget = QWidget()
        local_layout = QVBoxLayout(self.local_widget)
        local_layout.setContentsMargins(0,0,0,0)
        local_layout.addWidget(self.w._create_styled_label("로컬 데이터셋 폴더 경로"))
        
        path_layout = QHBoxLayout()
        self.task_folder_edit = self.w._create_styled_input(QLineEdit())
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
        self.btn_s1_back.clicked.connect(lambda: self.w.stack.setCurrentIndex(0))
        
        self.btn_s1_start = QPushButton("1단계만 시작 🚀")
        self.btn_s1_start.setFixedHeight(45)
        self.btn_s1_start.setStyleSheet(f"border: 1px solid {self.ctx.get_color('accent')}; color: {self.ctx.get_color('accent')};")
        
        self.btn_s1_next = QPushButton("2단계 이어설정 ➡️")
        self.btn_s1_next.setFixedHeight(45)
        self.btn_s1_next.setStyleSheet(f"background-color: {self.ctx.get_color('accent')}; color: {self.ctx.get_color('bg_dark')}; font-weight: bold;")
        self.btn_s1_next.clicked.connect(lambda: self.w.stack.setCurrentIndex(2))
        
        btns.addWidget(self.btn_s1_back)
        btns.addWidget(self.btn_s1_start)
        btns.addWidget(self.btn_s1_next)
        l.addLayout(btns)
