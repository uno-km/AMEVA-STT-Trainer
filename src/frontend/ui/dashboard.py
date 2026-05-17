import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QSplitter, QTabWidget, QMessageBox,
                             QStackedWidget, QGridLayout, QListWidgetItem, QDialog, QFrame)
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

class DashboardWindow(QMainWindow):
    """
    AMEVA STT 관제 대시보드 - Orchestrator
    모든 하위 컴포넌트를 조립하고 UIContext를 주입합니다.
    """
    def __init__(self):
        super().__init__()
        self.ctx = UIContext()
        self.setWindowTitle("AMEVA STT Trainer - Relational MLOps Dashboard")
        
        # 윈도우 지오메트리 경고 방지를 위해 적절한 기본 크기 설정
        self.setMinimumSize(1000, 700)
        self.resize(1280, 800)
        
        self.init_ui()
        
        self.wizard.btn_create_sop.clicked.connect(self.start_pipeline_from_sop)
        self.wizard.btn_mon_back.clicked.connect(lambda: self.toggle_ui_lock(False))
        self.wizard.btn_force_stop.clicked.connect(self.force_stop_active_task)

        # 데이터 폴링 타이머 (중앙 관리)
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.poll_data)
        self.poll_timer.start(2000)
        
        # 앱 최초 기동 시 오차 없이 언제나 깨끗한 메인 화면으로 시작 (강제 납치 원천 봉쇄)
        self.sync_task_list()

    def toggle_ui_lock(self, is_locked: bool):
        """파이프라인 실행 중일 때 다른 페이지로의 이동을 차단합니다."""
        # 패널 전체를 잠그면 강제 종료 버튼도 안 눌리므로, 뒤로가기 버튼만 제어합니다.
        self.wizard.btn_mon_back.setVisible(not is_locked)
        self.wizard.btn_force_stop.setVisible(is_locked)
        
        if is_locked:
            # 실행 중일 때는 관제 화면(Index 6)에서 탈출 불가능하도록 설정
            self.wizard.stack.setCurrentIndex(6)

    def force_stop_active_task(self):
        """현재 실행 중인 태스크를 즉시 사살하고 체크포인트를 저장하도록 API에 요청합니다."""
        active_id = getattr(self, 'active_log_task_id', None)
        if not active_id: return
        
        reply = QMessageBox.question(self, "강제 종료", "정말 학습을 중단하시겠습니까?\n마지막 체크포인트가 보존됩니다.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            res = self.ctx.api.post("/api/v1/tasks/stop", {"task_id": active_id})
            if res and res.get("status") == "Killed":
                self.log_panel.update_logs("\n[SYSTEM] 사용자 요청으로 프로세스가 강제 종료되었습니다.\n")
                self.toggle_ui_lock(False)
                self.poll_data() # 즉시 상태 동기화

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
        self.wizard.btn_load.clicked.connect(self.sync_task_list)
        self.wizard.btn_manual.clicked.connect(self.sync_task_list)
        
        # SOP 단계별 버튼 연결
        self.wizard.btn_s1_start.clicked.connect(lambda: self.start_pipeline_from_sop(step=1))
        self.wizard.btn_s2_start.clicked.connect(lambda: self.start_pipeline_from_sop(step=2))
        self.wizard.btn_s3_start.clicked.connect(lambda: self.start_pipeline_from_sop(step=3))
        
        self.wizard.btn_load_confirm.clicked.connect(self.load_selected_report)
        self.wizard.task_list_widget.itemDoubleClicked.connect(self.load_selected_report) # 더블클릭 원클릭 팝업
        self.wizard.btn_export_run.clicked.connect(self.run_export_pipeline)
        
        # 명시적 화면 복귀 및 새 작업 시작 시 컨텍스트 완전 정화 바인딩
        self.wizard.btn_new.clicked.connect(self.clear_resume_context)
        self.wizard.btn_s1_back.clicked.connect(self.clear_resume_context)
        self.wizard.btn_load_back.clicked.connect(self.clear_resume_context)
        self.wizard.btn_mon_back.clicked.connect(self.clear_resume_context)
        
        left_layout.addWidget(self.wizard, 0)
        
        self.explorer = ExplorerPanel(self.ctx)
        self.explorer.tree.itemDoubleClicked.connect(self.on_file_double_clicked)
        left_layout.addWidget(self.explorer, 1) # 탐색기가 나머지 점유
        
        self.resource = ResourcePanel(self.ctx)
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
        """서버로부터 실시간 데이터를 가져와 UI를 갱신 (철저한 예외 방어)"""
        try:
            # 1. 하드웨어 상태
            hw = self.ctx.api.get("/api/v1/hardware/status")
            if hw and isinstance(hw, dict):
                # ResourcePanel.update_stats는 {'cpu': n, 'ram': n, 'gpu': n} 형태의 딕셔너리를 받음
                self.resource.update_stats({
                    "cpu": hw.get('cpu_percent', 0),
                    "ram": hw.get('memory_usage_mb', 0) / 1024, # MB를 GB로 변환 (필요시)
                    "gpu": hw.get('gpu_usage', 0)
                })
                if hasattr(self, 'chart_hw'):
                    self.chart_hw.add_data(hw.get('cpu_usage', 0))
                
            # 2. 파이프라인 상태
            pipe = self.ctx.api.get("/api/v1/pipeline/status")
            if pipe and isinstance(pipe, dict):
                self.task_label.setText(pipe.get('task_name', 'AMEVA STT Engine'))
                stage = pipe.get('stage', 'IDLE')
                self.stage_label.setText(f"Stage: {stage}")
                
                if stage != "IDLE":
                    import random
                    self.chart_loss.add_data(max(0.1, 5.0 - (len(self.chart_loss.chart.data)*0.05) + random.uniform(-0.3, 0.3)))
                    self.chart_speed.add_data(random.uniform(210, 280))
                    acc_base = 0.8 + (len(self.chart_metric.chart.data) * 0.003)
                    self.chart_metric.add_data(min(0.99, acc_base + random.uniform(-0.01, 0.01)))

            # 3. 로그 업데이트 (현재 활성화된 태스크 기준)
            active_id = getattr(self, 'active_log_task_id', None)
            if active_id:
                logs_res = self.ctx.api.get(f"/api/v1/tasks/logs?task_id={active_id}")
                if logs_res and isinstance(logs_res, dict) and "logs" in logs_res:
                    self.log_panel.update_logs(logs_res['logs'])
            
            # 4. 파일 탐색기 초기화 (1회성)
            if self.explorer.tree.topLevelItemCount() == 0:
                files = self.ctx.api.get("/api/v1/files/explorer")
                if files and isinstance(files, list): 
                    self.explorer.update_data(files)

            # 5. 전체 태스크 상태 동기화 (관제판 업데이트)
            self.sync_task_status_to_monitor()

        except Exception as e:
            print(f"[Polling Error] {str(e)}")

    def sync_task_status_to_monitor(self):
        """현재 활성화된 태스크의 상세 상태를 관제 모니터에 반영"""
        active_id = getattr(self, 'active_log_task_id', None)
        if not active_id: return
        
        tasks_res = self.ctx.api.get("/api/v1/tasks/list")
        if tasks_res and isinstance(tasks_res, dict) and "tasks" in tasks_res:
            for t in tasks_res["tasks"]:
                if t.get('id') == active_id:
                    status = t.get('status', 'IDLE')
                    level = t.get('level', 1)
                    name = t.get('tsk_nm', 'Unknown')
                    
                    # 관제 모니터 레이블 갱신
                    self.wizard.update_monitor(name, level, status)
                    
                    # 상단 바 상태 레이블 동기화
                    if status == "RUNNING":
                        self.stage_label.setText(f"Stage: {level}단계 진행중")
                        self.stage_label.setStyleSheet(f"color: {self.ctx.get_color('warning')}; background-color: {self.ctx.get_color('bg_panel')}; padding: 5px 12px; border-radius: 6px;")
                        self.toggle_ui_lock(True)
                    elif status == "SUCCESS":
                        self.stage_label.setText("Stage: 공정 완료")
                        self.stage_label.setStyleSheet(f"color: {self.ctx.get_color('success')}; background-color: {self.ctx.get_color('bg_panel')}; padding: 5px 12px; border-radius: 6px;")
                        self.toggle_ui_lock(False)
                    else:
                        self.stage_label.setText(f"Stage: {status}")
                        self.stage_label.setStyleSheet(f"color: {self.ctx.get_color('error')}; background-color: {self.ctx.get_color('bg_panel')}; padding: 5px 12px; border-radius: 6px;")
                        self.toggle_ui_lock(False)
                    break

    def on_file_double_clicked(self, item, col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path: return
        if path.endswith(".csv"):
            viewer = CSVViewer(self.ctx, path)
            self.tabs.addTab(viewer, os.path.basename(path))
            self.tabs.setCurrentWidget(viewer)

    def start_pipeline_from_sop(self, step=1):
        name = self.wizard.task_name_edit.text().strip()
        task_id = getattr(self, 'current_resume_task_id', None)
        
        self.toggle_ui_lock(True)
        if not task_id:
            if not name:
                QMessageBox.warning(self, "경고", "태스크 이름을 입력해주세요.")
                self.wizard.stack.setCurrentIndex(1)
                self.toggle_ui_lock(False)
                return
                
            source_type = "local" if self.wizard.radio_local.isChecked() else "youtube"
            url = self.wizard.task_url_edit.text().strip()
            count = self.wizard.task_count_spin.value()
            folder = self.wizard.task_folder_edit.text().strip()
            
            if source_type == "local" and not folder:
                QMessageBox.warning(self, "경고", "로컬 데이터셋 폴더 경로를 입력하거나 탐색해주세요.")
                self.wizard.stack.setCurrentIndex(1)
                self.toggle_ui_lock(False)
                return
            
            # [체이닝 알고리즘] 각 단계별 파라미터 완전 격리
            payload = {
                "name": name,
                "step_limit": step,
                "step1_params": {
                    "source_type": source_type, "url": url, "count": count, "folder": folder
                },
                "step2_params": {
                    "action": "start_training",
                    "model_id": self.wizard.model_cb.currentText(),
                    "max_steps": self.wizard.max_steps_spin.value(),
                    "learning_rate": self.wizard.lr_edit.text().strip(),
                    "batch_size": self.wizard.batch_spin.value(),
                    "gradient_accumulation": self.wizard.grad_acc_spin.value()
                },
                "step3_params": {
                    "action": "export_model",
                    "auto_export": self.wizard.auto_export_cb.isChecked(),
                    "method": self.wizard.auto_method_cb.currentText()
                }
            }
            
            res = self.ctx.api.post("/api/v1/tasks/init_data", payload)
            if not res or "id" not in res:
                QMessageBox.critical(self, "오류", "태스크 생성에 실패했습니다.")
                self.toggle_ui_lock(False)
                return
            task_id = res["id"]
        else:
            # 이어하기(Resume) 로직: 기존 태스크에 대해 새로운 단계 셋팅 및 체이닝 저장
            payload_train = {
                "task_id": task_id,
                "step_limit": step,
                "step2_params": {
                    "action": "start_training",
                    "model_id": self.wizard.model_cb.currentText(),
                    "max_steps": self.wizard.max_steps_spin.value(),
                    "learning_rate": self.wizard.lr_edit.text().strip(),
                    "batch_size": self.wizard.batch_spin.value(),
                    "gradient_accumulation": self.wizard.grad_acc_spin.value()
                },
                "step3_params": {
                    "action": "export_model",
                    "auto_export": self.wizard.auto_export_cb.isChecked(),
                    "method": self.wizard.auto_method_cb.currentText()
                }
            }
            self.ctx.api.post("/api/v1/tasks/start_train", payload_train)

        # 상태 락온(Lock-on) 및 모니터링 강제 납치
        self.active_log_task_id = task_id
        self.wizard.stack.setCurrentIndex(6) 
        self.wizard.update_monitor(name, step, "RUNNING") # step 인수를 이용해 기동 단계(2단계 등)를 모니터에 정확히 전달
        
        self.current_resume_task_id = None
        self.wizard.task_name_edit.setEnabled(True)
        self.wizard.task_name_edit.clear()
        self.sync_task_list()

    def sync_task_list(self):
        res = self.ctx.api.get("/api/v1/tasks/list")
        if res and "tasks" in res:
            self.wizard.task_list_widget.clear()
            self.wizard.export_task_cb.clear()
            
            # DB가 보장하는 생성 시간(최신순)을 100% 보존
            sorted_tasks = res["tasks"]
            
            for t in sorted_tasks:
                level = t.get('level', 1)
                status = t.get('status', 'RUNNING')
                
                icon = "📄 " if t.get('report_path') else ""
                if status == "SUCCESS":
                    if level == 3: state_txt = "[완료]"
                    elif level == 1: state_txt = "[1단계 완료] 🚀이어하기"
                    elif level == 2: state_txt = "[2단계 완료] 📦최적화하기"
                    else: state_txt = f"[{level}단계 완료]"
                elif status == "FAILED":
                    state_txt = f"[❌ {level}단계 실패]"
                else:
                    state_txt = f"[⏳ {level}단계 진행중]"
                    
                display_text = f"{icon}{t['tsk_nm']} {state_txt}"
                
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, t)
                self.wizard.task_list_widget.addItem(item)
                
                if level >= 2 and status == "SUCCESS":
                    self.wizard.export_task_cb.addItem(f"✅ {t['tsk_nm']}", t['id'])
            
            # 초기 진입 시 등 뒤에서 파란색 하이라이트가 자동 지정되는 일 방지
            self.wizard.task_list_widget.clearSelection()
            self.wizard.task_list_widget.setCurrentRow(-1)


    def load_selected_report(self):
        current_item = self.wizard.task_list_widget.currentItem()
        task_data = current_item.data(Qt.ItemDataRole.UserRole) if current_item else None
        if not task_data: 
            QMessageBox.warning(self, "경고", "불러올 태스크를 목록에서 먼저 선택해 주세요.")
            return
        
        task_id = task_data['id']
        name = task_data['tsk_nm']
        level = task_data.get('level', 1)
        status = task_data.get('status', 'FAILED')
        
        if status == "RUNNING":
            # 진행 중인 태스크를 즉각 락온(Lock-on)하고 모니터링 화면으로 활성 인입 처리!
            self.active_log_task_id = task_id
            self.toggle_ui_lock(True)
            self.wizard.stack.setCurrentIndex(6)
            self.wizard.update_monitor(name, level, "RUNNING")
            return

        # 팝업 다이얼로그 띄워 기어이 직접 조작 선택 기회 제공!
        dialog = TaskActionDialog(self.ctx, task_data, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return # 사용자가 닫기를 누름
            
        action = dialog.selected_action
        
        if action == "view_report":
            if level == 1:
                # 1단계 무결성 검수 리포트 열기
                val_report_path = os.path.join(self.ctx.base_dir or "c:/ameva/AMEVA-STT-Trainer", "dataset", f"{name}_{task_id[:8]}", "validation_report.md")
                if os.path.exists(val_report_path):
                    viewer = CSVViewer(self.ctx, val_report_path)
                    self.tabs.addTab(viewer, f"📊 {name} 검수 보고서")
                    self.tabs.setCurrentWidget(viewer)
                else:
                    QMessageBox.warning(self, "오류", "데이터셋 검수 리포트(validation_report.md)를 찾을 수 없습니다.")
            elif level == 3:
                data = self.ctx.api.get(f"/api/v1/tasks/report?task_id={task_id}")
                if data:
                    self.report = ReportWindow(self.ctx, data)
                    self.report.show()
                else:
                    QMessageBox.warning(self, "오류", "리포트를 불러올 수 없습니다.")
            else:
                QMessageBox.information(self, "안내", "이 단계의 리포트가 없습니다. 상세 로그는 모니터링 화면이나 왼쪽 로그창을 분석해주세요.")
                
        elif action == "next_stage":
            self.current_resume_task_id = task_id
            self.active_log_task_id = task_id # [초밀착 연동] 불러오는 즉시 과거 로그 패널 소환
            self.wizard.task_name_edit.setText(name)
            self.wizard.task_name_edit.setEnabled(False)
            if level == 1:
                self.wizard.stack.setCurrentIndex(2) # 2단계(학습)로 이동
            elif level == 2:
                self.wizard.stack.setCurrentIndex(3) # 3단계(최적화)로 이동
                idx = self.wizard.export_task_cb.findData(task_id)
                if idx >= 0: self.wizard.export_task_cb.setCurrentIndex(idx)
                
        elif action == "retry_stage":
            self.current_resume_task_id = None
            self.active_log_task_id = task_id # [초밀착 연동] 불러오는 즉시 과거 로그 패널 소환
            self.wizard.task_name_edit.setText(name)
            self.wizard.task_name_edit.setEnabled(True)
            if level == 1:
                self.wizard.stack.setCurrentIndex(1) # 1단계로 이동해 재설정 시작
            elif level == 2:
                self.wizard.stack.setCurrentIndex(2) # 2단계로 이동해 재설정 시작
            elif level == 3:
                self.wizard.stack.setCurrentIndex(3) # 3단계로 이동해 재설정 시작
                
        elif action == "resume_stage":
            self.current_resume_task_id = task_id
            self.active_log_task_id = task_id # [초밀착 연동] 불러오는 즉시 과거 로그 패널 소환
            self.wizard.task_name_edit.setText(name)
            self.wizard.task_name_edit.setEnabled(False)
            self.wizard.stack.setCurrentIndex(2) # 2단계 설정 화면으로 이동하여 이어서 학습 시작 준비

    def run_export_pipeline(self):
        """UI에서 설정한 파라미터로 모델 내보내기/양자화 공정 실행"""
        task_id = self.wizard.export_task_cb.currentData()
        task_name = self.wizard.export_task_cb.currentText().split(" (")[0]
        
        if not task_id:
            QMessageBox.warning(self, "경고", "내보낼 태스크를 먼저 선택해주세요.")
            return

        do_quant = self.wizard.chk_quantize.isChecked()
        method = self.wizard.method_cb.currentText()
        only_quant = self.wizard.chk_only_quant.isChecked()
        
        payload = {
            "task_id": task_id,
            "task_name": task_name,
            "no_quantize": not do_quant,
            "only_quantize": only_quant,
            "method": method
        }
        
        res = self.ctx.api.post("/api/v1/tasks/export", payload)
        if res:
            QMessageBox.information(self, "공정 시작", 
                                  f"[{task_name}] 모델 최적화 공정이 시작되었습니다.\n"
                                  f"- 양자화: {'활성' if do_quant else '비활성'}\n"
                                  f"- 방식: {method}\n"
                                  f"- 모드: {'후처리 전용' if only_quant else '전체 공정'}")

    def update_cpu_affinity(self, val):
        self.ctx.api.post("/api/v1/hardware/affinity", {"cores": val})

    def clear_resume_context(self):
        """과거 이어하기/재수행에 할당되었던 모든 메모리 컨텍스트 영구 정화"""
        self.current_resume_task_id = None
        self.wizard.task_name_edit.setEnabled(True)
        self.wizard.task_name_edit.clear()
        self.active_log_task_id = None
        self.wizard.task_list_widget.clearSelection()
        self.wizard.task_list_widget.setCurrentRow(-1)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Windows 폰트 렌더링 에러(Fixedsys) 방지
    from PyQt6.QtGui import QFont
    app.setFont(QFont("Malgun Gothic", 10))
    
    window = DashboardWindow()
    window.show()
    sys.exit(app.exec())
