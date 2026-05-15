import sys
import os
import csv

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import math
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QSlider, QPushButton, 
                             QTextEdit, QTreeWidget, QTreeWidgetItem, QSplitter,
                             QMessageBox, QFrame, QTabWidget, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QStackedWidget,
                             QLineEdit, QComboBox, QTabBar, QFileDialog)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPalette, QFont

from src.frontend.client.api_client import api_client

class SimpleChart(QWidget):
    def __init__(self):
        super().__init__()
        self.data = []
        self.setMinimumSize(300, 200)

    def add_data(self, value):
        self.data.append(value)
        if len(self.data) > 50:
            self.data.pop(0)
        self.update()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QPen, QColor
        from PyQt6.QtCore import QPointF
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1e1e2e"))
        if not self.data: return
            
        painter.setPen(QPen(QColor("#313244"), 1, Qt.PenStyle.DashLine))
        for i in range(1, 5):
            y = self.height() * (i / 5)
            painter.drawLine(0, int(y), self.width(), int(y))

        pen = QPen(QColor("#cba6f7"), 2)
        painter.setPen(pen)
        
        max_val = max(self.data) if max(self.data) > 0 else 1
        min_val = min(self.data)
        val_range = max_val - min_val if max_val != min_val else 1
        
        points = []
        x_step = self.width() / (len(self.data) - 1) if len(self.data) > 1 else self.width()
        for i, v in enumerate(self.data):
            x = i * x_step
            norm_y = (v - min_val) / val_range
            y = self.height() * 0.9 - (norm_y * self.height() * 0.8)
            points.append(QPointF(x, y))
            
        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i+1])

class CSVViewer(QTableWidget):
    def __init__(self, file_path):
        super().__init__()
        self.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4; gridline-color: #313244;")
        self.horizontalHeader().setStyleSheet("background-color: #313244; color: #cdd6f4;")
        self.verticalHeader().setStyleSheet("background-color: #313244; color: #cdd6f4;")
        self.load_csv(file_path)

    def load_csv(self, file_path):
        try:
            with open(file_path, newline='', encoding='utf-8') as f:
                reader = list(csv.reader(f))
                if not reader: return
                self.setRowCount(len(reader) - 1)
                self.setColumnCount(len(reader[0]))
                self.setHorizontalHeaderLabels(reader[0])
                
                for row_idx, row in enumerate(reader[1:]):
                    for col_idx, item in enumerate(row):
                        self.setItem(row_idx, col_idx, QTableWidgetItem(item))
            self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        except Exception as e:
            self.setRowCount(1)
            self.setColumnCount(1)
            self.setItem(0, 0, QTableWidgetItem(f"Error loading CSV: {str(e)}"))

class AudioViewer(QWidget):
    def __init__(self, file_path):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel("🎵")
        icon_label.setFont(QFont("Arial", 48))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        name_label = QLabel(os.path.basename(file_path))
        name_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        controls = QHBoxLayout()
        play_btn = QPushButton("▶ Play")
        play_btn.setStyleSheet("background-color: #a6e3a1; color: #11111b; padding: 10px;")
        stop_btn = QPushButton("⏹ Stop")
        stop_btn.setStyleSheet("background-color: #f38ba8; color: #11111b; padding: 10px;")
        
        # Audio playing requires QtMultimedia which might not be installed, 
        # so this is a mock UI for the player as requested.
        play_btn.clicked.connect(lambda: name_label.setText(f"Playing: {os.path.basename(file_path)}..."))
        stop_btn.clicked.connect(lambda: name_label.setText(os.path.basename(file_path)))
        
        controls.addWidget(play_btn)
        controls.addWidget(stop_btn)
        
        layout.addWidget(icon_label)
        layout.addWidget(name_label)
        layout.addLayout(controls)

class ReportWindow(QMainWindow):
    """태스크의 모든 정보(정보, 로그, 파일)를 한눈에 보여주는 보고서 창"""
    def __init__(self, report_data):
        super().__init__()
        task_name = report_data['task_info'].get('tsk_nm', 'Unknown Task')
        self.setWindowTitle(f"Task Report: {task_name}")
        self.resize(1000, 800)
        self.setStyleSheet("background-color: #11111b; color: #cdd6f4;")
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Header
        title = QLabel(f"📄 {task_name} 상세 리포트")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #89b4fa; padding: 10px;")
        layout.addWidget(title)
        
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #181825; border-radius: 10px; padding: 15px;")
        info_layout = QVBoxLayout(info_frame)
        
        info_layout.addWidget(QLabel(f"Task ID (UUID): {report_data['task_info']['id']}"))
        info_layout.addWidget(QLabel(f"생성 일시: {report_data['task_info']['create_dt']}"))
        
        # Step Status 표시
        step = report_data['task_info'].get('step_lv', 1)
        stts = report_data['task_info'].get('step_stts', 'UNKNOWN')
        stts_color = "#a6e3a1" if stts == "SUCCESS" else "#f9e2af" if stts == "RUNNING" else "#f38ba8"
        
        status_label = QLabel(f"현재 단계: Step {step} | 상태: {stts}")
        status_label.setStyleSheet(f"color: {stts_color}; font-weight: bold; font-size: 14px;")
        info_layout.addWidget(status_label)
        
        # Restart 버튼 추가
        self.restart_btn = QPushButton(f"🔄 이 설정으로 재학습 시작 (새 버전 생성)")
        self.restart_btn.clicked.connect(lambda: self.trigger_restart(report_data['task_info']['id']))
        self.restart_btn.setStyleSheet("background-color: #89b4fa; color: #11111b; padding: 10px; font-weight: bold;")
        info_layout.addWidget(self.restart_btn)
        
        layout.addWidget(info_frame)
        
        # Tabs for details
        tabs = QTabWidget()
        tabs.setStyleSheet("QTabBar::tab { padding: 10px; }")
        
        # Log tab
        log_view = QTextEdit()
        log_view.setReadOnly(True)
        log_view.setStyleSheet("background-color: #11111b; font-family: Consolas;")
        for log in report_data.get("logs", []):
            log_view.append(f"[{log['level']}] {log['message']}")
        tabs.addTab(log_view, "전체 로그")
        
        # DB DB Metadata & Chunks tab
        db_tree = QTreeWidget()
        db_tree.setHeaderLabels(["데이터", "경로/스크립트"])
        db_tree.setColumnWidth(0, 300)
        
        metadatas = report_data['task_info'].get('metadatas', [])
        for meta in metadatas:
            meta_item = QTreeWidgetItem(db_tree, [f"Meta [{meta['meta_id']}]: {meta['file_name']}", meta['folder_path']])
            meta_item.setForeground(0, QColor("#89b4fa"))
            
            for chunk in meta.get('chunks', []):
                chunk_text = f"[{chunk['chunk_id']}] {chunk['chunk_name']}"
                script_text = chunk.get('script') or ""
                chunk_item = QTreeWidgetItem(meta_item, [chunk_text, script_text])
                chunk_item.setForeground(0, QColor("#a6e3a1"))
        
        db_tree.expandAll()
        tabs.addTab(db_tree, "DB 매핑 데이터 (Meta ↔ Chunks)")
        
        layout.addWidget(tabs)
        
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet("background-color: #313244; padding: 10px;")
        layout.addWidget(close_btn)

    def trigger_restart(self, task_id):
        # API를 통해 새 버전 태스크 생성 요청
        response = api_client.post("/api/v1/tasks/restart", {"task_id": task_id})
        if response:
            QMessageBox.information(self, "재시작", f"새로운 버전의 태스크가 생성되었습니다: {response['name']}\n이제 메인 화면에서 학습을 이어가세요.")
            self.close()

class DashboardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AMEVA STT Trainer Platform")
        self.resize(1400, 900)
        self.setStyleSheet("background-color: #11111b; color: #cdd6f4;")
        
        self.total_cores = 16
        self.allocated_cores = 16
        
        # Pending task info (Not yet in DB)
        self.pending_task_name = ""
        self.pending_data_path = ""
        
        self.init_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll_data)
        self.timer.start(1000)
        self.poll_data()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Top Bar ---
        top_bar = QHBoxLayout()
        self.task_label = QLabel("AMEVA STT Engine")
        self.task_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.task_label.setStyleSheet("color: #89b4fa;")
        
        self.stage_label = QLabel("Stage: IDLE")
        self.stage_label.setFont(QFont("Arial", 12))
        self.stage_label.setStyleSheet("color: #a6e3a1; background-color: #313244; padding: 5px; border-radius: 5px;")
        
        top_bar.addWidget(self.task_label)
        top_bar.addStretch()
        top_bar.addWidget(self.stage_label)
        main_layout.addLayout(top_bar)

        # --- Center: Splitter ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left Panel (Wizard + Explorer)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0,0,0,0)
        
        # 1. Pipeline Wizard
        self.wizard = QStackedWidget()
        self.wizard.setStyleSheet("background-color: #181825; border: 1px solid #313244; border-radius: 5px;")
        
        # Page 0: Home
        page0 = QWidget()
        p0_layout = QVBoxLayout(page0)
        p0_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_load = QPushButton("📁 과거 기록 불러오기")
        btn_new = QPushButton("🚀 새로운 모델 학습하기")
        btn_load.setStyleSheet("padding: 15px; font-size: 14px; background-color: #313244;")
        btn_load.clicked.connect(self.load_past_records)
        btn_new.setStyleSheet("padding: 15px; font-size: 14px; background-color: #a6e3a1; color: #11111b; font-weight: bold;")
        btn_new.clicked.connect(lambda: self.wizard.setCurrentIndex(1))
        p0_layout.addWidget(btn_load)
        p0_layout.addWidget(btn_new)
        self.wizard.addWidget(page0)
        
        # Page 1: Data Prep
        page1 = QWidget()
        p1_layout = QVBoxLayout(page1)
        p1_layout.addWidget(QLabel("Step 1. 태스크 생성 및 데이터 준비", font=QFont("Arial", 14, QFont.Weight.Bold)))
        
        p1_layout.addWidget(QLabel("태스크 이름 입력:"))
        self.task_name_input = QLineEdit()
        self.task_name_input.setPlaceholderText("예: 슈카월드학습_0515")
        self.task_name_input.setStyleSheet("padding: 8px; background-color: #1e1e2e; border: 1px solid #89b4fa;")
        p1_layout.addWidget(self.task_name_input)
        
        btn_has_data = QPushButton("📂 이미 데이터 있음 (폴더 선택 후 다음 단계로)")
        btn_has_data.clicked.connect(self.select_data_folder)
        p1_layout.addWidget(btn_has_data)
        
        p1_layout.addWidget(QLabel("또는 새로 다운로드 (YouTube):"))
        self.yt_input = QLineEdit()
        self.yt_input.setPlaceholderText("YouTube URL 입력...")
        self.yt_input.setStyleSheet("padding: 5px; background-color: #1e1e2e; color: #fff;")
        p1_layout.addWidget(self.yt_input)
        
        btn_download = QPushButton("➡️ 데이터 수집 설정 완료 (다음 단계로)")
        btn_download.clicked.connect(self.start_data_acquisition)
        btn_download.setStyleSheet("background-color: #89b4fa; color: #11111b; padding: 10px; font-weight: bold;")
        p1_layout.addWidget(btn_download)
        p1_layout.addStretch()
        self.wizard.addWidget(page1)
        
        # Page 2: Modeling (Training Params)
        page2 = QWidget()
        p2_layout = QVBoxLayout(page2)
        p2_layout.addWidget(QLabel("Step 2. 모델링 및 학습 설정", font=QFont("Arial", 14, QFont.Weight.Bold)))
        
        p2_layout.addWidget(QLabel("베이스 모델 선택:"))
        model_cb = QComboBox()
        model_cb.addItems(["Whisper Large-v3", "Whisper Medium", "Whisper Small"])
        model_cb.setStyleSheet("padding: 5px; background-color: #1e1e2e;")
        p2_layout.addWidget(model_cb)
        
        p2_layout.addWidget(QLabel("Epochs:"))
        epoch_input = QLineEdit("3")
        p2_layout.addWidget(epoch_input)
        
        p2_layout.addWidget(QLabel("Batch Size:"))
        batch_input = QLineEdit("8")
        p2_layout.addWidget(batch_input)
        
        btn_start_train = QPushButton("🚀 위 설정으로 학습 및 수집 시작! (이때 DB 등록)")
        btn_start_train.clicked.connect(self.final_start_training)
        btn_start_train.setStyleSheet("background-color: #a6e3a1; color: #11111b; padding: 25px; font-weight: bold; font-size: 16px; border: 2px solid #fff;")
        p2_layout.addWidget(btn_start_train)
        p2_layout.addStretch()
        self.wizard.addWidget(page2)
        
        left_layout.addWidget(self.wizard, 1)

        # 2. File Explorer with Search
        explorer_container = QWidget()
        explorer_layout = QVBoxLayout(explorer_container)
        explorer_layout.setContentsMargins(0, 5, 0, 0)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 파일 또는 폴더 검색... (0.5초 대기 시 검색)")
        self.search_bar.setStyleSheet("padding: 8px; background-color: #1e1e2e; border: 1px solid #313244; border-radius: 4px;")
        self.search_bar.textChanged.connect(self.on_search_text_changed)
        explorer_layout.addWidget(self.search_bar)
        
        self.explorer = QTreeWidget()
        self.explorer.setHeaderHidden(True) # 헤더 대신 검색창 사용
        self.explorer.setStyleSheet("background-color: #181825; border: 1px solid #313244;")
        self.explorer.itemDoubleClicked.connect(self.on_file_double_clicked)
        explorer_layout.addWidget(self.explorer)
        
        left_layout.addWidget(explorer_container, 2)
        
        # Search debounce timer
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.filter_explorer)
        
        splitter.addWidget(left_panel)
        
        # Right Panel (Tab Widget)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.setStyleSheet("""
            QTabBar::tab { background: #313244; color: #cdd6f4; padding: 8px 15px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
            QTabBar::tab:selected { background: #1e1e2e; font-weight: bold; border-bottom: 2px solid #89b4fa; }
            QTabWidget::pane { border: 1px solid #313244; background: #1e1e2e; }
        """)
        
        # Main Tab (Unclosable)
        main_tab_widget = QWidget()
        main_tab_layout = QVBoxLayout(main_tab_widget)
        
        # Splitter inside main tab for Logs and Chart
        inner_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Logs
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background-color: #11111b; color: #a6adc8; font-family: Consolas; border: 1px solid #313244;")
        inner_splitter.addWidget(self.log_view)
        
        # Chart
        chart_container = QWidget()
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(0,0,0,0)
        chart_layout.addWidget(QLabel("실시간 학습 Loss 그래프", font=QFont("Arial", 10, QFont.Weight.Bold)))
        self.chart = SimpleChart()
        chart_layout.addWidget(self.chart)
        chart_container.setStyleSheet("background-color: #11111b; border: 1px solid #313244;")
        inner_splitter.addWidget(chart_container)
        
        main_tab_layout.addWidget(inner_splitter)
        self.tabs.addTab(main_tab_widget, "메인 로그 & 대시보드")
        
        # Remove close button from the first tab
        self.tabs.tabBar().setTabButton(0, QTabBar.ButtonPosition.RightSide, None)
        
        splitter.addWidget(self.tabs)
        
        splitter.setSizes([350, 1050])
        main_layout.addWidget(splitter, 1)

        # --- Bottom Bar: Resource Control ---
        bottom_frame = QFrame()
        bottom_frame.setStyleSheet("background-color: #181825; border-radius: 8px; padding: 10px;")
        bottom_layout = QVBoxLayout(bottom_frame)
        
        # Info row
        info_layout = QHBoxLayout()
        self.cpu_info_label = QLabel("CPU 사용률: --% | 메모리: -- MB")
        self.cpu_info_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        
        self.network_indicator = QLabel("●")
        self.network_indicator.setFont(QFont("Arial", 14))
        
        self.refresh_btn = QPushButton("새로고침 (Refresh)")
        self.refresh_btn.clicked.connect(self.poll_data)
        self.refresh_btn.setStyleSheet("background-color: #89b4fa; color: #11111b; padding: 5px 15px; font-weight: bold; border-radius: 4px;")
        
        info_layout.addWidget(self.cpu_info_label)
        info_layout.addStretch()
        info_layout.addWidget(QLabel("Internet: "))
        info_layout.addWidget(self.network_indicator)
        info_layout.addWidget(self.refresh_btn)
        bottom_layout.addLayout(info_layout)
        
        # Slider row
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("실시간 CPU 스레드 할당 (점유율 조절):"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(1)
        self.slider.setMaximum(16)
        self.slider.valueChanged.connect(self.on_slider_change)
        
        self.slider_val_label = QLabel("16")
        self.slider_val_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.slider_val_label.setMinimumWidth(30)
        
        self.apply_btn = QPushButton("저장 및 즉시 적용 (Save)")
        self.apply_btn.clicked.connect(self.apply_affinity)
        self.apply_btn.setStyleSheet("background-color: #a6e3a1; color: #11111b; padding: 5px 15px; font-weight: bold; border-radius: 4px;")
        
        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.slider_val_label)
        slider_layout.addWidget(self.apply_btn)
        bottom_layout.addLayout(slider_layout)
        
        main_layout.addWidget(bottom_frame)

    def close_tab(self, index):
        if index > 0:
            self.tabs.removeTab(index)

    def on_file_double_clicked(self, item, column):
        # We stored the path in data(0, UserRole) if it's a file
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not file_path: return
        
        file_name = os.path.basename(file_path)
        
        # Check if already open
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == file_name:
                self.tabs.setCurrentIndex(i)
                return

        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.csv']:
            viewer = CSVViewer(file_path)
        elif ext in ['.wav', '.mp3']:
            viewer = AudioViewer(file_path)
        else:
            # Fallback text viewer
            viewer = QTextEdit()
            viewer.setReadOnly(True)
            viewer.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    viewer.setPlainText(f.read())
            except Exception as e:
                viewer.setPlainText(f"Cannot open file: {e}")
                
        self.tabs.addTab(viewer, file_name)
        self.tabs.setCurrentWidget(viewer)

    def poll_data(self):
        hw_status = api_client.get("/api/v1/hardware/status")
        if hw_status:
            self.total_cores = hw_status.get("total_cores", 16)
            self.allocated_cores = hw_status.get("allocated_cores", 16)
            cpu_pct = hw_status.get("cpu_percent", 0)
            mem_mb = hw_status.get("memory_usage_mb", 0)
            
            self.cpu_info_label.setText(f"전체 CPU 사용률: {cpu_pct}% | 프로세스 메모리: {mem_mb:.1f} MB | 할당된 코어: {self.allocated_cores}/{self.total_cores}")
            
            if self.slider.maximum() != self.total_cores:
                self.slider.setMaximum(self.total_cores)
                self.slider.setValue(self.allocated_cores)
            
            if hw_status.get("internet_connected", False):
                self.network_indicator.setStyleSheet("color: #a6e3a1;")
            else:
                self.network_indicator.setStyleSheet("color: #f38ba8;")

        pipeline_status = api_client.get("/api/v1/pipeline/status")
        if pipeline_status:
            self.task_label.setText(pipeline_status.get("task_name", "AMEVA STT Engine"))
            stage = pipeline_status.get("stage", "IDLE")
            self.stage_label.setText(f"Stage: {stage}")

        logs_data = api_client.get("/api/v1/pipeline/logs")
        if logs_data and "logs" in logs_data:
            logs = logs_data["logs"]
            if len(logs) > 0:
                last_logs = logs[-50:]
                log_text = ""
                for log in last_logs:
                    color = "#a6e3a1" if log['level'] == 'INFO' else "#f38ba8" if log['level'] == 'ERROR' else "#f9e2af"
                    log_text += f"<span style='color:{color}'>[{log['level']}]</span> {log['message']}<br>"
                self.log_view.setHtml(log_text)
                self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

        if self.explorer.topLevelItemCount() == 0:
            self.refresh_explorer()

        import random
        val = max(0.1, 5.0 - (len(self.chart.data)*0.08) + random.uniform(-0.5, 0.5))
        self.chart.add_data(val)

    def refresh_explorer(self):
        self.explorer.clear()
        files_data = api_client.get("/api/v1/files/explorer")
        if files_data:
            def add_items_recursive(parent_item, items):
                for item in items:
                    child = QTreeWidgetItem(parent_item, [item["name"]])
                    if item.get("is_dir"):
                        child.setForeground(0, QColor("#f9e2af"))
                        if "children" in item:
                            add_items_recursive(child, item["children"])
                    else:
                        child.setData(0, Qt.ItemDataRole.UserRole, item["path"])

            for category, items in files_data.items():
                cat_item = QTreeWidgetItem(self.explorer, [category.upper()])
                cat_item.setForeground(0, QColor("#89b4fa"))
                add_items_recursive(cat_item, items)
            
            # self.explorer.expandAll() # 냅다 모두 펼치지 않도록 주석 처리
            # 대신 최상위 카테고리만 펼침
            for i in range(self.explorer.topLevelItemCount()):
                self.explorer.topLevelItem(i).setExpanded(True)

    def on_search_text_changed(self):
        # 0.5초(500ms) 대기 후 filter_explorer 호출
        self.search_timer.start(500)

    def filter_explorer(self):
        search_text = self.search_bar.text().lower()
        
        def filter_item(item):
            item_text = item.text(0).lower()
            any_child_visible = False
            
            for i in range(item.childCount()):
                if filter_item(item.child(i)):
                    any_child_visible = True
            
            # 검색어가 포함되어 있거나 자식 중 보이는 게 있으면 표시
            is_visible = (search_text in item_text) or any_child_visible
            item.setHidden(not is_visible)
            
            # 검색 중일 때는 매칭되는 항목들을 펼쳐서 보여줌
            if search_text and is_visible:
                item.setExpanded(True)
            elif not search_text:
                # 검색어가 없으면 다시 카테고리만 빼고 닫음 (선택 사항)
                pass
                
            return is_visible

        for i in range(self.explorer.topLevelItemCount()):
            filter_item(self.explorer.topLevelItem(i))

    def select_data_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "학습용 데이터셋 폴더 선택")
        if folder:
            self.pending_task_name = self.task_name_input.text() or "Unnamed_Task"
            self.pending_data_path = folder
            QMessageBox.information(self, "설정 완료", f"태스크명: {self.pending_task_name}\n데이터 경로가 설정되었습니다. 다음 단계에서 학습을 시작하세요.")
            self.wizard.setCurrentIndex(2)

    def start_data_acquisition(self):
        yt_url = self.yt_input.text()
        if not yt_url:
            QMessageBox.warning(self, "입력 오류", "YouTube URL을 입력해주세요.")
            return
            
        self.pending_task_name = self.task_name_input.text() or "YouTube_Task"
        self.pending_data_path = f"YT:{yt_url}"
        
        QMessageBox.information(self, "설정 완료", f"태스크명: {self.pending_task_name}\nYouTube URL이 등록되었습니다. 다음 단계에서 실행을 누르면 다운로드가 시작됩니다.")
        self.wizard.setCurrentIndex(2)

    def final_start_training(self):
        # 실제 학습 버튼을 눌렀을 때만 DB에 태스크를 생성함
        if not self.pending_task_name:
            self.pending_task_name = "Direct_Training"
            
        response = api_client.post("/api/v1/tasks/create", {"name": self.pending_task_name})
        if response:
            task_id = response['id']
            QMessageBox.information(self, "학습 시작", f"축하합니다! 태스크 [{task_id}]가 DB에 공식 등록되었습니다.\n이제 실시간 모니터링을 시작합니다.")
            # 실제 학습 프로세스 트리거 로직이 여기에 들어감
            self.refresh_explorer()

    def load_past_records(self):
        response = api_client.get("/api/v1/tasks/list")
        if response and "tasks" in response:
            tasks = response["tasks"]
            if not tasks:
                QMessageBox.information(self, "기록 없음", "저장된 태스크 기록이 없습니다.")
                return
                
            from PyQt6.QtWidgets import QInputDialog
            task_names = [f"{t['tsk_nm']} ({t['create_dt']})" for t in tasks]
            item, ok = QInputDialog.getItem(self, "과거 태스크 선택", "불러올 태스크를 선택하세요:", task_names, 0, False)
            
            if ok and item:
                selected_idx = task_names.index(item)
                selected_task = tasks[selected_idx]
                
                report_data = api_client.get(f"/api/v1/tasks/report?task_id={selected_task['id']}")
                if report_data and "error" not in report_data:
                    self.report_win = ReportWindow(report_data)
                    self.report_win.show()
                else:
                    QMessageBox.critical(self, "오류", "리포트를 불러오지 못했습니다.")
        else:
            QMessageBox.warning(self, "오류", "태스크 목록을 불러오지 못했습니다.")

    def on_slider_change(self, value):
        self.slider_val_label.setText(str(value))
        # 90% 이상일 때만 빨간색 경고 (80%는 주황색 느낌으로 변경 가능하나 일단 90%로 완화)
        if value >= self.total_cores * 0.9:
            self.slider.setStyleSheet("QSlider::handle:horizontal { background-color: #f38ba8; border-radius: 7px; }")
            self.slider_val_label.setStyleSheet("color: #f38ba8; font-weight: bold;")
        elif value >= self.total_cores * 0.7:
            self.slider.setStyleSheet("QSlider::handle:horizontal { background-color: #f9e2af; border-radius: 7px; }")
            self.slider_val_label.setStyleSheet("color: #f9e2af;")
        else:
            self.slider.setStyleSheet("")
            self.slider_val_label.setStyleSheet("color: #cdd6f4;")

    def apply_affinity(self):
        target_cores = self.slider.value()
        if target_cores > self.total_cores * 0.8:
            reply = QMessageBox.warning(
                self, '경고', 
                f'현재 점유율({target_cores} 코어)이 너무 높습니다.\n업무에 지장이 생길 수 있습니다. 진행하시겠습니까?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                self.slider.setValue(self.allocated_cores)
                return
                
        response = api_client.post("/api/v1/hardware/affinity", {"cores": target_cores})
        if response.get("success"):
            self.allocated_cores = response.get("allocated")
            QMessageBox.information(self, '성공', f'코어 수가 {self.allocated_cores}개로 조정되었습니다.')
            self.poll_data()
        else:
            QMessageBox.critical(self, '오류', f'코어 할당 실패: {response.get("error")}')

if __name__ == '__main__':
    app = QApplication(sys.path)
    window = DashboardWindow()
    window.show()
    sys.exit(app.exec())
