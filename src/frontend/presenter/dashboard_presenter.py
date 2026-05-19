import os
import sqlite3
from PyQt6.QtWidgets import QMessageBox, QDialog, QListWidgetItem
from PyQt6.QtCore import Qt

from src.frontend.ui.components.report import ReportWindow
from src.frontend.ui.components.viewers import CSVViewer, LogViewer
from src.frontend.ui.components.task_action_dialog import TaskActionDialog

class DashboardPresenter:
    """
    [MVP 아키텍처 Presenter] AMEVA MLOps 관제 대시보드 비즈니스 로직 전담 조정자
    - View(DashboardWindow)와 Model(db_manager/API) 사이의 데이터를 중계 조율합니다.
    - 백엔드 상태 폴링, 프로세스 강제 종료, 학습 이어하기 체이닝, 리포트 연동 로직 총괄.
    """
    def __init__(self, view):
        self.view = view
        self.ctx = view.ctx
        
        # 활성 상태 변수 격리 보관
        self.active_log_task_id = None
        self.last_active_log_task_id = None
        self.plotted_metrics_count = 0
        self.report_shown_for_active_task = False
        self.current_resume_task_id = None
        self.pipeline_mode = "NEW" # "NEW" or "RESUME"
        self.last_explorer_task_id = -1 # 파일 탐색기 필터링 갱신용 센티널 변수

    def poll_data(self):
        """서버로부터 실시간 데이터를 폴링하여 View를 동적으로 갱신 (예외 완전 방어)"""
        try:
            # 1. 하드웨어 상태 폴링 및 차트 Push
            hw = self.ctx.api.get("/api/v1/hardware/status")
            if hw and isinstance(hw, dict):
                self.view.resource.update_stats({
                    "cpu": hw.get('cpu_percent', 0),
                    "allocated_cores": hw.get('allocated_cores', 0)
                })
                self.view.chart_hw.add_data(hw.get('cpu_percent', 0))
                
            # 2. 실시간 파이프라인 태스크 상태 갱신
            pipe = self.ctx.api.get("/api/v1/pipeline/status")
            if pipe and isinstance(pipe, dict):
                self.view.task_label.setText(pipe.get('task_name', 'AMEVA STT Engine'))
                
            # 3. 모델 성능 지표 매핑 및 실시간 차트 업데이트
            if self.active_log_task_id:
                # 활성 태스크 ID가 변경되었으면 차트 초기화 및 카운트 리셋
                if self.last_active_log_task_id != self.active_log_task_id:
                    self.last_active_log_task_id = self.active_log_task_id
                    self.plotted_metrics_count = 0
                    self.view.chart_loss.chart.prefill_data(0.0)
                    self.view.chart_speed.chart.prefill_data(0.0)
                    self.view.chart_metric.chart.prefill_data(0.0)
                    
                metrics_res = self.ctx.api.get(f"/api/v1/tasks/metrics?task_id={self.active_log_task_id}")
                if metrics_res and "metrics" in metrics_res:
                    metrics = metrics_res["metrics"]
                    current_count = self.plotted_metrics_count
                    for m in metrics[current_count:]:
                        loss_val = m.get('loss', 0)
                        speed_val = m.get('speed', 0)
                        dt_str = m.get('create_dt', '')
                        time_part = dt_str.split(" ")[-1] if " " in dt_str else dt_str
                        
                        self.view.chart_loss.add_data({"value": float(loss_val), "time": time_part})
                        self.view.chart_speed.add_data({"value": float(speed_val), "time": time_part})
                        # Loss에 역비례하는 직관적 정확도 실시간 계산
                        acc_val = max(0.0, 1.0 - (loss_val * 0.1))
                        self.view.chart_metric.add_data({"value": float(acc_val), "time": time_part})
                        self.plotted_metrics_count += 1

            # 4. 실시간 학습 로그 콘솔 Push
            if self.active_log_task_id:
                logs_res = self.ctx.api.get(f"/api/v1/tasks/logs?task_id={self.active_log_task_id}")
                if logs_res and isinstance(logs_res, dict) and "logs" in logs_res:
                    self.view.log_panel.update_logs(logs_res['logs'])
            
            # 5. 파일 탐색기 동적 동기화 (최초 1회 혹은 활성 태스크 전환 시점 자동 리빌드)
            current_active_id = self.active_log_task_id
            if self.view.explorer.tree.topLevelItemCount() == 0 or current_active_id != getattr(self, 'last_explorer_task_id', -1):
                self.last_explorer_task_id = current_active_id
                
                # 활성 태스크의 고유 명칭(tsk_nm) DB 역조회
                active_name = None
                if current_active_id:
                    try:
                        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
                        db_path = os.path.join(getattr(self.ctx, 'base_dir', None) or project_root, "db/stt_trainer.db")
                        conn = sqlite3.connect(db_path)
                        cursor = conn.cursor()
                        cursor.execute("SELECT tsk_nm FROM tb_task WHERE id = ?", (current_active_id,))
                        row = cursor.fetchone()
                        if row:
                            active_name = row[0]
                        conn.close()
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        print(f"[Presenter Explorer Name Resolve Error] {e}")
                
                files = self.ctx.api.get("/api/v1/files/explorer")
                if files and isinstance(files, dict): 
                    self.view.explorer.update_data(files, active_task_id=current_active_id, active_task_name=active_name)

            # 6. 관제 대시보드 상태 레이블 최종 동기화
            self.sync_task_status_to_monitor()

        except Exception as e:
            print(f"[Presenter Polling Error] {str(e)}")

    def sync_task_status_to_monitor(self):
        """현재 활성화된 태스크의 정밀 가동 공정을 감시 대시보드에 다이렉트 동기화"""
        if not self.active_log_task_id:
            return
        
        tasks_res = self.ctx.api.get("/api/v1/tasks/list")
        if tasks_res and isinstance(tasks_res, dict) and "tasks" in tasks_res:
            for t in tasks_res["tasks"]:
                if t.get('id') == self.active_log_task_id:
                    status = t.get('status', 'IDLE')
                    level = t.get('level', 1)
                    name = t.get('tsk_nm', 'Unknown')
                    
                    # 관제 모니터 단계별 상태값 즉시 갱신
                    self.view.wizard.update_monitor(name, level, status)
                    
                    # 상단 바 프리미엄 상태 레이블 디자인 적용
                    if status == "RUNNING":
                        self.view.stage_label.setText(f"Stage: {level}단계 진행중")
                        self.view.stage_label.setStyleSheet(
                            f"color: {self.ctx.get_color('warning')}; background-color: {self.ctx.get_color('bg_panel')}; padding: 5px 12px; border-radius: 6px;"
                        )
                        self.view.toggle_ui_lock(True)
                    elif status == "SUCCESS":
                        self.view.stage_label.setText("Stage: 공정 완료")
                        self.view.stage_label.setStyleSheet(
                            f"color: {self.ctx.get_color('success')}; background-color: {self.ctx.get_color('bg_panel')}; padding: 5px 12px; border-radius: 6px;"
                        )
                        self.view.toggle_ui_lock(False)
                        
                        # 자동 완료 리포트 표출 (1회성 차단 센티널 작동)
                        if not self.report_shown_for_active_task:
                            self.report_shown_for_active_task = True
                            if level == 1:
                                self.show_validation_report(self.active_log_task_id, name)
                            elif level == 3:
                                data = self.ctx.api.get(f"/api/v1/tasks/report?task_id={self.active_log_task_id}")
                                if data:
                                    self.view.report = ReportWindow(self.ctx, data)
                                    self.view.report.show()
                    else:
                        display_status = "중단됨" if status == "CANCELED" else "실패"
                        self.view.stage_label.setText(f"Stage: {display_status}")
                        self.view.stage_label.setStyleSheet(
                            f"color: {self.ctx.get_color('error')}; background-color: {self.ctx.get_color('bg_panel')}; padding: 5px 12px; border-radius: 6px;"
                        )
                        self.view.toggle_ui_lock(False)
                    break

    def start_pipeline_from_sop(self, step=1):
        """SOP 마법사 설정값에 기반하여 비동기 STT 학습 파이프라인 가동 통제"""
        name = self.view.wizard.task_name_edit.text().strip()
        task_id = self.current_resume_task_id
        
        self.view.toggle_ui_lock(True)
        
        # 만약 RESUME 모드인데 task_id가 휘발되었다면 이름 기반으로 복구
        if self.pipeline_mode == "RESUME" and not task_id:
            if name:
                try:
                    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
                    db_path = os.path.join(getattr(self.ctx, 'base_dir', None) or project_root, "db/stt_trainer.db")
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM tb_task WHERE tsk_nm = ? ORDER BY create_dt DESC LIMIT 1", (name,))
                    row = cursor.fetchone()
                    if row:
                        task_id = row[0]
                        self.current_resume_task_id = task_id
                    conn.close()
                except Exception as e:
                    print(f"[Presenter Self-healing Error] {e}")
        
        if self.pipeline_mode == "NEW":
            # 1. 완전 신규 태스크 생성 제어
            if not name:
                QMessageBox.warning(self.view, "경고", "태스크 이름을 입력해주세요.")
                self.view.wizard.stack.setCurrentIndex(1)
                self.view.toggle_ui_lock(False)
                return
                
            source_type = "local" if self.view.wizard.radio_local.isChecked() else "youtube"
            url = self.view.wizard.task_url_edit.text().strip()
            count = self.view.wizard.task_count_spin.value()
            folder = self.view.wizard.task_folder_edit.text().strip()
            
            if source_type == "local" and not folder:
                QMessageBox.warning(self.view, "경고", "로컬 데이터셋 폴더 경로를 입력하거나 탐색해주세요.")
                self.view.wizard.stack.setCurrentIndex(1)
                self.view.toggle_ui_lock(False)
                return
            
            # 단계별 파라미터 완전 격리 및 바인딩
            payload = {
                "name": name,
                "step_limit": step,
                "step1_params": {
                    "source_type": source_type, "url": url, "count": count, "folder": folder
                },
                "step2_params": {
                    "action": "start_training",
                    "model_id": self.view.wizard.model_cb.currentText(),
                    "max_steps": self.view.wizard.max_steps_spin.value(),
                    "learning_rate": self.view.wizard.lr_edit.text().strip(),
                    "batch_size": self.view.wizard.batch_spin.value(),
                    "gradient_accumulation": self.view.wizard.grad_acc_spin.value()
                },
                "step3_params": {
                    "action": "export_model",
                    "auto_export": self.view.wizard.auto_export_cb.isChecked(),
                    "method": self.view.wizard.auto_method_cb.currentText()
                }
            }
            
            res = self.ctx.api.post("/api/v1/tasks/init_data", payload)
            if not res or "id" not in res:
                QMessageBox.critical(self.view, "오류", "태스크 생성에 실패했습니다.")
                self.view.toggle_ui_lock(False)
                return
            task_id = res["id"]
            self.current_resume_task_id = task_id
        else:
            # 2. 기존 중단 태스크 이어하기(RESUME) 데이터 빌딩 및 업데이트
            if not name and task_id:
                try:
                    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
                    db_path = os.path.join(getattr(self.ctx, 'base_dir', None) or project_root, "db/stt_trainer.db")
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT tsk_nm FROM tb_task WHERE id = ?", (task_id,))
                    row = cursor.fetchone()
                    if row:
                        name = row[0]
                    conn.close()
                except Exception as e:
                    name = "Resumed Task"
                    
            payload_train = {
                "task_id": task_id,
                "step_limit": step,
                "step2_params": {
                    "action": "start_training",
                    "model_id": self.view.wizard.model_cb.currentText(),
                    "max_steps": self.view.wizard.max_steps_spin.value(),
                    "learning_rate": self.view.wizard.lr_edit.text().strip(),
                    "batch_size": self.view.wizard.batch_spin.value(),
                    "gradient_accumulation": self.view.wizard.grad_acc_spin.value()
                },
                "step3_params": {
                    "action": "export_model",
                    "auto_export": self.view.wizard.auto_export_cb.isChecked(),
                    "method": self.view.wizard.auto_method_cb.currentText()
                }
            }
            self.ctx.api.post("/api/v1/tasks/start_train", payload_train)

        # 상태 락온 및 실시간 감시 화면으로 인입
        self.active_log_task_id = task_id
        self.report_shown_for_active_task = False
        self.view.wizard.stack.setCurrentIndex(6) 
        self.view.wizard.update_monitor(name, step, "RUNNING")
        
        # [해결] 세션 가동 도중에는 ID와 텍스트를 강제 초기화하지 않아, 파이프라인 정지 후 바로 다음 단계로 이어갈 수 있도록 조치!
        self.view.wizard.task_name_edit.setEnabled(False)
        self.sync_task_list()

    def sync_task_list(self):
        """데이터베이스 이력을 호출하여 과거 학습 기록 뷰 동기화"""
        res = self.ctx.api.get("/api/v1/tasks/list")
        if res and "tasks" in res:
            self.view.wizard.task_list_widget.clear()
            self.view.wizard.export_task_cb.clear()
            
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
                elif status == "CANCELED":
                    state_txt = f"[🛑 {level}단계 중단]"
                else:
                    state_txt = f"[⏳ {level}단계 진행중]"
                    
                display_text = f"{icon}{t['tsk_nm']} {state_txt}"
                
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, t)
                self.view.wizard.task_list_widget.addItem(item)
                
                if level >= 2 and status == "SUCCESS":
                    self.view.wizard.export_task_cb.addItem(f"✅ {t['tsk_nm']}", t['id'])
            
            # 파란색 강제 하이라이팅 현상 차단
            self.view.wizard.task_list_widget.clearSelection()
            self.view.wizard.task_list_widget.setCurrentRow(-1)

    def load_selected_report(self):
        """선택한 과거 태스크의 무결성 검수 데이터 복원 및 동적 조작 인터랙션 분기"""
        current_item = self.view.wizard.task_list_widget.currentItem()
        task_data = current_item.data(Qt.ItemDataRole.UserRole) if current_item else None
        if not task_data: 
            QMessageBox.warning(self.view, "경고", "불러올 태스크를 목록에서 먼저 선택해 주세요.")
            return
        
        task_id = task_data['id']
        name = task_data['tsk_nm']
        level = task_data.get('level', 1)
        status = task_data.get('status', 'FAILED')
        
        if status == "RUNNING":
            # 1. 진행 중인 태스크 선택 시 관제 모니터로 기습 동승(Lock-on)
            self.active_log_task_id = task_id
            self.view.toggle_ui_lock(True)
            self.view.wizard.stack.setCurrentIndex(6)
            self.view.wizard.update_monitor(name, level, "RUNNING")
            return
 
        # 2. 완료/실패 태스크 선택 시 옵션 팝업 호출
        dialog = TaskActionDialog(self.ctx, task_data, self.view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
            
        action = dialog.selected_action
        
        if action == "view_report":
            if level == 1:
                self.show_validation_report(task_id, name)
            elif level == 3:
                data = self.ctx.api.get(f"/api/v1/tasks/report?task_id={task_id}")
                if data:
                    self.view.report = ReportWindow(self.ctx, data)
                    self.view.report.show()
                else:
                    QMessageBox.warning(self.view, "오류", "리포트를 불러올 수 없습니다.")
            else:
                # 2단계 학습의 경우, 데이터베이스와 로컬 파일 복합 수집 방식의 최고급 상세 콘솔 창 생성
                viewer = LogViewer(self.ctx, task_id, name)
                self.view.tabs.addTab(viewer, f"📜 {name} 상세 로그")
                self.view.tabs.setCurrentWidget(viewer)
                
        elif action == "next_stage":
            self.current_resume_task_id = task_id
            self.active_log_task_id = task_id
            self.pipeline_mode = "RESUME"
            self.view.wizard.task_name_edit.setText(name)
            self.view.wizard.task_name_edit.setEnabled(False)
            if level == 1:
                self.load_parameters_to_ui(task_id, 2)
                self.view.wizard.stack.setCurrentIndex(2)
            elif level == 2:
                self.load_parameters_to_ui(task_id, 3)
                self.view.wizard.stack.setCurrentIndex(3)
                idx = self.view.wizard.export_task_cb.findData(task_id)
                if idx >= 0: 
                    self.view.wizard.export_task_cb.setCurrentIndex(idx)
                
        elif action == "retry_stage":
            self.active_log_task_id = task_id
            if level == 1:
                # 1단계 재시도는 신규 태스크 생성과 거의 동일하므로 기존처럼 NEW로 동작
                self.current_resume_task_id = None
                self.pipeline_mode = "NEW"
                self.view.wizard.task_name_edit.setText(name)
                self.view.wizard.task_name_edit.setEnabled(True)
                self.view.wizard.stack.setCurrentIndex(1)
            else:
                # 2단계/3단계 재시도는 기존 태스크의 해당 스테이지를 재가동하는 것이므로 RESUME(태스크ID 보존)으로 전환!
                self.current_resume_task_id = task_id
                self.pipeline_mode = "RESUME"
                self.view.wizard.task_name_edit.setText(name)
                self.view.wizard.task_name_edit.setEnabled(False)
                if level == 2:
                    self.load_parameters_to_ui(task_id, 2)
                    self.view.wizard.stack.setCurrentIndex(2)
                elif level == 3:
                    self.load_parameters_to_ui(task_id, 3)
                    self.view.wizard.stack.setCurrentIndex(3)
                
        elif action == "resume_stage":
            # [핵심 수정] 체크포인트 이어하기는 설정 화면을 거치지 않고 즉시 학습 재개
            self.current_resume_task_id = task_id
            self.active_log_task_id = task_id
            self.pipeline_mode = "RESUME"
            self.view.wizard.task_name_edit.setText(name)
            self.view.wizard.task_name_edit.setEnabled(False)
            self.load_parameters_to_ui(task_id, 2)
            # 설정 화면(stack index 2) 대신 바로 학습 파이프라인 가동
            self.start_pipeline_from_sop(step=2)

    def run_export_pipeline(self):
        """[크래시 버그 철저 방어] 수동 최적화 GGUF 모델 추출 공정 최종 실행"""
        task_id = self.view.wizard.export_task_cb.currentData()
        task_name = self.view.wizard.export_task_cb.currentText().split(" (")[0]
        
        if not task_id:
            QMessageBox.warning(self.view, "경고", "내보낼 태스크를 먼저 선택해주세요.")
            return

        # [버그 완전 해결] 수동 최적화 뷰에 알맞은 고정 값 및 방식 매핑
        do_quant = True
        only_quant = True
        method = self.view.wizard.manual_method_cb.currentText()
        
        payload = {
            "task_id": task_id,
            "task_name": task_name,
            "no_quantize": not do_quant,
            "only_quantize": only_quant,
            "method": method
        }
        
        res = self.ctx.api.post("/api/v1/tasks/export", payload)
        if res:
            QMessageBox.information(
                self.view, "공정 시작", 
                f"[{task_name}] 모델 최적화 공정이 시작되었습니다.\n"
                f"- 양자화: 활성\n"
                f"- 방식: {method}\n"
                f"- 모드: 후처리 전용"
            )

    def force_stop_active_task(self):
        """현재 가동 중인 백엔드 서브프로세스를 즉각 안전하게 사살(Killed) 요청"""
        active_id = self.active_log_task_id
        if not active_id: 
            return
        
        reply = QMessageBox.question(
            self.view, "강제 종료", 
            "정말 학습을 중단하시겠습니까?\n마지막 체크포인트가 보존됩니다.", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            res = self.ctx.api.post("/api/v1/tasks/stop", {"task_id": active_id})
            if res and res.get("status") == "Killed":
                self.view.log_panel.update_logs("\n[SYSTEM] 사용자 요청으로 프로세스가 강제 종료되었습니다.\n")
                self.view.toggle_ui_lock(False)
                self.poll_data() # 즉각적 상태 최신화

    def clear_resume_context(self):
        """이어하기 복구 등에 할당되었던 메모리 컨텍스트 영구 가비지 컬렉션"""
        self.current_resume_task_id = None
        self.pipeline_mode = "NEW"
        self.view.wizard.task_name_edit.setEnabled(True)
        self.view.wizard.task_name_edit.clear()
        self.active_log_task_id = None
        self.view.wizard.task_list_widget.clearSelection()
        self.view.wizard.task_list_widget.setCurrentRow(-1)

    def update_cpu_affinity(self, val):
        self.ctx.api.post("/api/v1/hardware/affinity", {"cores": val})

    def show_validation_report(self, task_id, name):
        """1단계 무결성 검수 리포트(validation_report.md)를 탭 뷰어로 로드합니다."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        val_report_path = os.path.join(
            getattr(self.ctx, 'base_dir', None) or project_root, 
            "dataset", f"{name}_{task_id[:8]}", "validation_report.md"
        )
        if os.path.exists(val_report_path):
            # 중복 탭 생성을 감지하여 기존 탭 포커싱
            tab_title = f"📊 {name} 검수 보고서"
            for i in range(self.view.tabs.count()):
                if self.view.tabs.tabText(i) == tab_title:
                    self.view.tabs.setCurrentIndex(i)
                    return
            viewer = CSVViewer(self.ctx, val_report_path)
            self.view.tabs.addTab(viewer, tab_title)
            self.view.tabs.setCurrentWidget(viewer)
        else:
            QMessageBox.warning(self.view, "오류", f"데이터셋 검수 리포트(validation_report.md)를 찾을 수 없습니다.\n경로: {val_report_path}")

    def load_parameters_to_ui(self, task_id, step_seq):
        """데이터베이스에서 특정 태스크의 단계별 파라미터를 로드하여 UI 위젯에 동기화"""
        try:
            import json
            import sqlite3
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            db_path = os.path.join(getattr(self.ctx, 'base_dir', None) or project_root, "db/stt_trainer.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT parameters FROM tb_task_dtl WHERE task_id = ? AND step_seq = ?",
                (task_id, step_seq)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0]:
                params = json.loads(row[0])
                
                if step_seq == 2:
                    model_id = params.get("model_id")
                    max_steps = params.get("max_steps")
                    learning_rate = params.get("learning_rate")
                    batch_size = params.get("batch_size")
                    grad_acc = params.get("gradient_accumulation")
                    
                    self.view.wizard.model_cb.blockSignals(True)
                    idx = self.view.wizard.model_cb.findText(str(model_id))
                    if idx >= 0:
                        self.view.wizard.model_cb.setCurrentIndex(idx)
                    self.view.wizard.model_cb.blockSignals(False)
                    
                    from src.core.config import MODEL_DEFAULTS
                    defaults = MODEL_DEFAULTS.get(model_id, MODEL_DEFAULTS.get("openai/whisper-tiny", {}))
                    if defaults:
                        self.view.wizard.model_desc_lbl.setText(defaults.get("description", ""))
                        
                    if max_steps is not None:
                        self.view.wizard.max_steps_spin.setValue(int(max_steps))
                    if learning_rate is not None:
                        self.view.wizard.lr_edit.setText(str(learning_rate))
                    if batch_size is not None:
                        self.view.wizard.batch_spin.setValue(int(batch_size))
                    if grad_acc is not None:
                        self.view.wizard.grad_acc_spin.setValue(int(grad_acc))
                        
                elif step_seq == 3:
                    auto_export = params.get("auto_export", False)
                    method = params.get("method")
                    
                    self.view.wizard.auto_export_cb.setChecked(bool(auto_export))
                    if method:
                        idx = self.view.wizard.auto_method_cb.findText(str(method))
                        if idx >= 0:
                            self.view.wizard.auto_method_cb.setCurrentIndex(idx)
        except Exception as e:
            print(f"[Presenter Error loading step {step_seq} parameters] {e}")
