import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QSplitter, QTabWidget, QMessageBox,
                             QStackedWidget, QGridLayout)
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

class DashboardWindow(QMainWindow):
    """
    AMEVA STT 관제 대시보드 - Orchestrator
    모든 하위 컴포넌트를 조립하고 UIContext를 주입합니다.
    """
    def __init__(self):
        super().__init__()
        self.ctx = UIContext()
        self.setWindowTitle("AMEVA STT Trainer - Relational MLOps Dashboard")
        self.resize(1400, 900)
        
        self.init_ui()
        
        # 데이터 폴링 타이머 (중앙 관리)
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.poll_data)
        self.poll_timer.start(2000)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet(f"background-color: {self.ctx.get_color('bg_main')}; color: {self.ctx.get_color('text')};")
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5) # 여백 최소화
        main_layout.setSpacing(5)
        
        # 1. Top Bar (Slim)
        top_bar_widget = QWidget()
        top_bar_widget.setFixedHeight(50) # 높이 고정
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
        main_layout.addWidget(top_bar_widget, 0) # 0: 최소 크기만 점유
        
        # 2. Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- Left Side ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 2, 0)
        left_layout.setSpacing(5)
        
        self.wizard = WizardPanel(self.ctx)
        self.wizard.btn_goto_load.clicked.connect(self.sync_task_list)
        self.wizard.btn_start.clicked.connect(self.start_training)
        self.wizard.btn_load_confirm.clicked.connect(self.load_selected_report)
        left_layout.addWidget(self.wizard, 0)
        
        self.explorer = ExplorerPanel(self.ctx)
        self.explorer.tree.itemDoubleClicked.connect(self.on_file_double_clicked)
        left_layout.addWidget(self.explorer, 1) # 탐색기가 나머지 점유
        
        self.resource = ResourcePanel()
        self.resource.slider.valueChanged.connect(self.update_cpu_affinity)
        left_layout.addWidget(self.resource, 0)
        
        splitter.addWidget(left_widget)
        
        # --- Right Side (Tabs) ---
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(lambda idx: self.tabs.removeTab(idx))
        self.tabs.setStyleSheet(f"""
            QTabBar::tab {{ background: {self.ctx.get_color('bg_panel')}; color: {self.ctx.get_color('text')}; padding: 8px 18px; font-size: 11px; }}
            QTabBar::tab:selected {{ background: {self.ctx.get_color('bg_main')}; border-bottom: 2px solid {self.ctx.get_color('accent')}; }}
            QTabWidget::pane {{ border: 1px solid {self.ctx.get_color('border')}; }}
        """)
        
        # Main Dashboard Tab
        dash_widget = QWidget()
        dash_layout = QVBoxLayout(dash_widget)
        dash_layout.setContentsMargins(5, 5, 5, 5)
        dash_layout.setSpacing(8)
        
        self.log_panel = LogPanel(self.ctx)
        self.log_panel.max_btn.clicked.connect(self.toggle_log_maximize)
        dash_layout.addWidget(self.log_panel, 2) # 로그 40%
        
        # Chart Area (Stack for Focus Mode)
        self.chart_stack = QStackedWidget()
        
        # 4-Quadrant Grid View
        self.grid_view = QWidget()
        self.chart_grid = QGridLayout(self.grid_view)
        self.chart_grid.setContentsMargins(0, 0, 0, 0)
        self.chart_grid.setSpacing(5)
        
        self.chart_loss = ChartWidget("LOSS TREND", self.ctx.get_color('error'))
        self.chart_hw = ChartWidget("CPU USAGE", self.ctx.get_color('accent'))
        self.chart_speed = ChartWidget("SPEED (T/s)", self.ctx.get_color('warning'))
        self.chart_metric = ChartWidget("ACCURACY", self.ctx.get_color('success'))
        
        self.charts = [self.chart_loss, self.chart_hw, self.chart_speed, self.chart_metric]
        for i, c in enumerate(self.charts):
            self.chart_grid.addWidget(c, i // 2, i % 2)
            c.maximized.connect(self.toggle_chart_maximize)
            
        self.chart_stack.addWidget(self.grid_view)
        dash_layout.addWidget(self.chart_stack, 3) # 차트 60%
        
        self.tabs.addTab(dash_widget, "📊 실시간 관제")
        splitter.addWidget(self.tabs)
        
        splitter.setSizes([320, 1080]) # 왼쪽을 더 슬림하게
        main_layout.addWidget(splitter, 1) # 스플리터가 나머지 공간 100% 점유

    # --- Focus Mode Logic ---
    def toggle_log_maximize(self):
        if self.chart_stack.isVisible():
            self.chart_stack.hide()
            self.log_panel.max_btn.setText("🔙")
        else:
            self.chart_stack.show()
            self.log_panel.max_btn.setText("🔲")

    def toggle_chart_maximize(self, chart_widget):
        if self.chart_stack.currentIndex() == 0:
            max_page = QWidget()
            max_layout = QVBoxLayout(max_page)
            max_layout.setContentsMargins(0,0,0,0)
            chart_widget.max_btn.setText("🔙")
            self.chart_grid.removeWidget(chart_widget)
            max_layout.addWidget(chart_widget)
            idx = self.chart_stack.addWidget(max_page)
            self.chart_stack.setCurrentIndex(idx)
        else:
            current_page = self.chart_stack.currentWidget()
            chart_widget = current_page.layout().itemAt(0).widget()
            chart_widget.max_btn.setText("🔍")
            self.chart_stack.setCurrentIndex(0)
            idx = self.charts.index(chart_widget)
            self.chart_grid.addWidget(chart_widget, idx // 2, idx % 2)
            self.chart_stack.removeWidget(current_page)
            current_page.deleteLater()

    def poll_data(self):
        hw = self.ctx.api.get("/api/v1/hardware/status")
        if hw:
            self.resource.update_status(hw.get('cpu_percent', 0), hw.get('memory_usage_mb', 0), hw.get('allocated_cores', 1), hw.get('total_cores', 16))
            self.chart_hw.add_data(hw.get('cpu_usage', 0))
            
        pipe = self.ctx.api.get("/api/v1/pipeline/status")
        if pipe:
            self.task_label.setText(pipe.get('task_name', 'AMEVA STT Engine'))
            stage = pipe.get('stage', 'IDLE')
            self.stage_label.setText(f"Stage: {stage}")
            
            if stage != "IDLE":
                import random
                self.chart_loss.add_data(max(0.1, 5.0 - (len(self.chart_loss.chart.data)*0.05) + random.uniform(-0.3, 0.3)))
                self.chart_speed.add_data(random.uniform(210, 280))
                acc_base = 0.8 + (len(self.chart_metric.chart.data) * 0.003)
                self.chart_metric.add_data(min(0.99, acc_base + random.uniform(-0.01, 0.01)))
            
        logs = self.ctx.api.get("/api/v1/pipeline/logs")
        if logs and "logs" in logs:
            self.log_panel.update_logs(logs['logs'])
            
        if self.explorer.tree.topLevelItemCount() == 0:
            files = self.ctx.api.get("/api/v1/files/explorer")
            self.explorer.update_data(files)

    def on_file_double_clicked(self, item, col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path: return
        if path.endswith(".csv"):
            viewer = CSVViewer(self.ctx, path)
            self.tabs.addTab(viewer, os.path.basename(path))
            self.tabs.setCurrentWidget(viewer)

    def start_training(self):
        name = self.wizard.get_task_name()
        res = self.ctx.api.post("/api/v1/tasks/create", {"name": name})
        if res:
            QMessageBox.information(self, "성공", f"태스크 [{name}] 생성 완료!")

    def sync_task_list(self):
        res = self.ctx.api.get("/api/v1/tasks/list")
        if res and "tasks" in res:
            self.wizard.task_list_cb.clear()
            for t in res["tasks"]:
                # 콤보박스에 이름 표시, 실제 ID는 데이터로 저장
                self.wizard.task_list_cb.addItem(f"{t['tsk_nm']} ({t['create_dt']})", t['id'])

    def load_selected_report(self):
        task_id = self.wizard.task_list_cb.currentData()
        if not task_id: return
        
        data = self.ctx.api.get(f"/api/v1/tasks/report?task_id={task_id}")
        if data:
            self.report = ReportWindow(self.ctx, data)
            self.report.show()

    def update_cpu_affinity(self, val):
        self.ctx.api.post("/api/v1/hardware/affinity", {"cores": val})

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DashboardWindow()
    window.show()
    sys.exit(app.exec())
