import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QSplitter, QTabWidget, QMessageBox,
                             QStackedWidget, QGridLayout, QListWidgetItem, QDialog, QFrame, QTabBar)
from PyQt6.QtCore import Qt, QTimer

# Core Binding
from src.frontend.ui.core.context import UIContext

# Modular Components
from src.frontend.ui.components.chart import ChartWidget
from src.frontend.ui.components.resource import ResourcePanel
from src.frontend.ui.components.log_panel import LogPanel
from src.frontend.ui.components.explorer_panel import ExplorerPanel
from src.frontend.ui.components.wizard_panel import WizardPanel
from src.frontend.ui.components.report import ReportWindow
from src.frontend.ui.components.viewers import CSVViewer
from src.frontend.ui.components.task_action_dialog import TaskActionDialog
from src.frontend.ui.components.db_viewer import DBViewerPanel

# MVP Presenter 임포트
from src.frontend.presenter.dashboard_presenter import DashboardPresenter

class DashboardWindow(QMainWindow):
    """
    AMEVA STT 관제 대시보드 - Pure View (GUI View Layer)
    - 화면의 구조 조립, 슬라이더/인풋의 시각 스타일링, 포커스/확대 모드 전환만을 전담합니다.
    - 모든 비즈니스 액션과 서버 폴링 제어는 Presenter(DashboardPresenter)로 전권 위임합니다.
    """
    def __init__(self):
        super().__init__()
        self.ctx = UIContext()
        self.setWindowTitle("AMEVA STT Trainer - Relational MLOps Dashboard")
        
        # 윈도우 지오메트리 경고 방지를 위한 고해상도 규격 설정
        self.setMinimumSize(1000, 700)
        self.resize(1280, 800)
        
        # UI 레이아웃 로드
        self.init_ui()
        
        # MVP Presenter 생성 및 밀착 조립
        self.presenter = DashboardPresenter(self)
        
        # --- [UI 시그널 ➡️ Presenter 액션 라우팅 바인딩] ---
        self.wizard.btn_create_sop.clicked.connect(lambda: self.presenter.start_pipeline_from_sop(step=3))
        self.wizard.btn_mon_back.clicked.connect(lambda: self.toggle_ui_lock(False))
        self.wizard.btn_force_stop.clicked.connect(self.presenter.force_stop_active_task)
        
        self.wizard.btn_load.clicked.connect(self.presenter.sync_task_list)
        self.wizard.btn_manual.clicked.connect(self.presenter.sync_task_list)
        
        self.wizard.btn_s1_start.clicked.connect(lambda: self.presenter.start_pipeline_from_sop(step=1))
        self.wizard.btn_s2_start.clicked.connect(lambda: self.presenter.start_pipeline_from_sop(step=2))
        self.wizard.btn_s3_start.clicked.connect(lambda: self.presenter.start_pipeline_from_sop(step=3))
        
        self.wizard.btn_load_confirm.clicked.connect(self.presenter.load_selected_report)
        self.wizard.task_list_widget.itemDoubleClicked.connect(self.presenter.load_selected_report)
        self.wizard.btn_export_run.clicked.connect(self.presenter.run_export_pipeline)
        
        self.wizard.btn_new.clicked.connect(self.presenter.clear_resume_context)
        self.wizard.btn_s1_back.clicked.connect(self.presenter.clear_resume_context)
        self.wizard.btn_load_back.clicked.connect(self.presenter.clear_resume_context)
        self.wizard.btn_mon_back.clicked.connect(self.presenter.clear_resume_context)

        # 데이터 폴링 타이머 가동 (Presenter 바인딩)
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.presenter.poll_data)
        self.poll_timer.start(500)
        
        # 최초 1회 즉시 과거 리스트 최신화
        self.presenter.sync_task_list()

    def toggle_ui_lock(self, is_locked: bool):
        """파이프라인 실행 중일 때 다른 페이지로의 탈출 이동을 하드웨어 락온 제어합니다."""
        self.wizard.btn_mon_back.setVisible(not is_locked)
        self.wizard.btn_force_stop.setVisible(is_locked)
        if is_locked:
            self.wizard.stack.setCurrentIndex(6)

    def init_ui(self):
        """대시보드 메인 레이블, 좌측 컨트롤판, 우측 관제 탭 영역 조립"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet(f"background-color: {self.ctx.get_color('bg_main')}; color: {self.ctx.get_color('text')};")
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 1. Top Bar
        top_bar_widget = QWidget()
        top_bar_widget.setFixedHeight(50)
        top_bar = QHBoxLayout(top_bar_widget)
        top_bar.setContentsMargins(10, 0, 10, 0)
        
        self.task_label = QLabel("AMEVA STT Engine")
        self.task_label.setFont(self.ctx.fonts['title'])
        self.task_label.setStyleSheet(f"color: {self.ctx.get_color('accent')}; border: none;")
        
        self.stage_label = QLabel("Stage: IDLE")
        self.stage_label.setFont(self.ctx.fonts['main'])
        self.stage_label.setStyleSheet(f"color: {self.ctx.get_color('success')}; background-color: {self.ctx.get_color('bg_panel')}; padding: 5px 12px; border-radius: 6px;")
        
        top_bar.addWidget(self.task_label)
        top_bar.addStretch()
        top_bar.addWidget(self.stage_label)
        main_layout.addWidget(top_bar_widget, 0)
        
        # 2. Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- Left Side (SOP Wizard Control Deck) ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 2, 0)
        left_layout.setSpacing(5)
        
        self.wizard = WizardPanel(self.ctx)
        left_layout.addWidget(self.wizard, 0)
        
        self.explorer = ExplorerPanel(self.ctx)
        self.explorer.tree.itemDoubleClicked.connect(self.on_file_double_clicked)
        left_layout.addWidget(self.explorer, 1)
        
        self.resource = ResourcePanel(self.ctx)
        left_layout.addWidget(self.resource, 0)
        
        splitter.addWidget(left_widget)
        
        # --- Right Side (Telemetry Visualization Tabs) ---
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab_safe)
        self.tabs.setStyleSheet(f"""
            QTabBar::tab {{ background: {self.ctx.get_color('bg_panel')}; color: {self.ctx.get_color('text')}; padding: 8px 18px; font-size: 11px; }}
            QTabBar::tab:selected {{ background: {self.ctx.get_color('bg_main')}; border-bottom: 2px solid {self.ctx.get_color('accent')}; }}
            QTabWidget::pane {{ border: 1px solid {self.ctx.get_color('border')}; }}
        """)
        
        # 실시간 관제 및 메트릭 패널 조립
        dash_widget = QWidget()
        dash_layout = QVBoxLayout(dash_widget)
        dash_layout.setContentsMargins(5, 5, 5, 5)
        dash_layout.setSpacing(8)
        
        self.log_panel = LogPanel(self.ctx)
        self.log_panel.max_btn.clicked.connect(self.toggle_log_maximize)
        dash_layout.addWidget(self.log_panel, 2)
        
        self.chart_stack = QStackedWidget()
        self.grid_view = QWidget()
        self.chart_grid = QGridLayout(self.grid_view)
        self.chart_grid.setContentsMargins(0, 0, 0, 0)
        self.chart_grid.setSpacing(5)
        
        self.chart_loss = ChartWidget("LOSS TREND", self.ctx.get_color('error'))
        self.chart_hw = ChartWidget("CPU USAGE", self.ctx.get_color('accent'))
        self.chart_hw.chart.y_min = 0.0
        self.chart_hw.chart.y_max = 100.0
        self.chart_hw.chart.y_suffix = "%"
        
        self.chart_speed = ChartWidget("SPEED (T/s)", self.ctx.get_color('warning'))
        self.chart_metric = ChartWidget("ACCURACY", self.ctx.get_color('success'))
        self.chart_metric.chart.y_min = 0.0
        self.chart_metric.chart.y_max = 1.0
        
        self.charts = [self.chart_loss, self.chart_hw, self.chart_speed, self.chart_metric]
        for i, c in enumerate(self.charts):
            self.chart_grid.addWidget(c, i // 2, i % 2)
            c.maximized.connect(self.toggle_chart_maximize)
            
        self.chart_stack.addWidget(self.grid_view)
        dash_layout.addWidget(self.chart_stack, 3)
        
        self.tabs.addTab(dash_widget, "📊 실시간 관제")
        
        self.db_viewer = DBViewerPanel(self.ctx)
        self.tabs.addTab(self.db_viewer, "🗄️ DB Inspector")
        
        # 필수 제어 탭 2개는 물리적으로 닫기 아이콘 영구 탈거 보호 조치
        self.tabs.tabBar().setTabButton(0, QTabBar.ButtonPosition.RightSide, None)
        self.tabs.tabBar().setTabButton(1, QTabBar.ButtonPosition.RightSide, None)
        
        splitter.addWidget(self.tabs)
        splitter.setSizes([320, 1080])
        main_layout.addWidget(splitter, 1)

    def toggle_log_maximize(self):
        """로그 모니터 포커스 가동 전환"""
        if self.chart_stack.isVisible():
            self.chart_stack.hide()
            self.log_panel.max_btn.setText("🔙")
        else:
            self.chart_stack.show()
            self.log_panel.max_btn.setText("🔲")

    def toggle_chart_maximize(self, chart_widget):
        """특정 모델 성능 실시간 차트 집중 관찰 극대화 전환 (C++ 객체 소멸 크래시 방지 세팅)"""
        if self.chart_stack.currentIndex() == 0:
            max_page = QWidget()
            max_layout = QVBoxLayout(max_page)
            max_layout.setContentsMargins(0,0,0,0)
            chart_widget.max_btn.setText("🔙")
            self.chart_grid.removeWidget(chart_widget)
            chart_widget.setParent(max_page)  # 부모 객체를 max_page로 명시적 이관하여 소멸 방지
            max_layout.addWidget(chart_widget)
            idx = self.chart_stack.addWidget(max_page)
            self.chart_stack.setCurrentIndex(idx)
        else:
            current_page = self.chart_stack.currentWidget()
            chart_widget = current_page.layout().itemAt(0).widget()
            chart_widget.max_btn.setText("🔍")
            self.chart_stack.setCurrentIndex(0)
            idx = self.charts.index(chart_widget)
            chart_widget.setParent(self.grid_view)  # 원래의 grid_view로 안전하게 재이관
            self.chart_grid.addWidget(chart_widget, idx // 2, idx % 2)
            self.chart_stack.removeWidget(current_page)
            current_page.deleteLater()

    def on_file_double_clicked(self, item, col):
        """CSV 및 일반 텍스트 데이터셋의 즉각적인 탭 뷰어 열기 기능 (중복 오픈 방지 가드 장착)"""
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or not os.path.isfile(path): 
            return
            
        # 중복 오픈 방지: 이미 열린 파일 탭이 있으면 해당 탭을 즉시 포커스
        for idx in range(self.tabs.count()):
            tab_widget = self.tabs.widget(idx)
            if hasattr(tab_widget, 'file_path') and tab_widget.file_path == path:
                self.tabs.setCurrentIndex(idx)
                return

        if path.endswith(".csv"):
            viewer = CSVViewer(self.ctx, path)
            viewer.file_path = path  # 중복 추적 속성 바인딩
            self.tabs.addTab(viewer, f"📊 {os.path.basename(path)}")
            self.tabs.setCurrentWidget(viewer)
        elif path.endswith((".log", ".md", ".txt", ".yaml", ".json", ".ini", ".py", ".pyw")):
            from src.frontend.ui.components.viewers import TextFileViewer
            viewer = TextFileViewer(self.ctx, path)
            viewer.file_path = path  # 중복 추적 속성 바인딩
            self.tabs.addTab(viewer, f"📄 {os.path.basename(path)}")
            self.tabs.setCurrentWidget(viewer)

    def close_tab_safe(self, idx):
        """보호 조치: 실시간 관제 및 DB 뷰어 외의 탭에 한정하여 종료 허용"""
        if idx >= 2:
            self.tabs.removeTab(idx)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # 윈도우 OS 시스템 폰트 고유 호환 에러 방지
    from PyQt6.QtGui import QFont
    app.setFont(QFont("Malgun Gothic", 10))
    
    window = DashboardWindow()
    window.show()
    sys.exit(app.exec())
