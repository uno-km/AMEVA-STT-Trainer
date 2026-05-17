from src.frontend.ui.core.qt import *
from PyQt6.QtWidgets import QMessageBox

# 새로 분할 찢기한 각 독립 모듈 페이지들 임포트
from src.frontend.ui.components.pages import (
    MainMenuPage, Step1Page, Step2Page, Step3Page, LoadPage, ManualExportPage, MonitorPage
)

class WizardPanel(QWidget):
    """
    AMEVA Premium SOP Wizard Panel (Refactored Container Version)
    - 3단계 선형 선결 조건 SOP 플로우를 완전히 독립된 화면 컴포넌트로 찢은 슬림 컨테이너.
    - 투명 프록시(Transparent Proxy) 어트리뷰트 연결을 통해 외부 연동 파괴 제로 달성.
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
        
        # --- [독립된 개별 컴포넌트 페이지 인스턴스 기동] ---
        self.page0 = MainMenuPage(self)
        self.page1 = Step1Page(self)
        self.page2 = Step2Page(self)
        self.page3 = Step3Page(self)
        self.page4 = LoadPage(self)
        self.page5 = ManualExportPage(self)
        self.page6 = MonitorPage(self)
        
        # --- 스택 위젯에 순차 적재 ---
        self.stack.addWidget(self.page0) # Index 0
        self.stack.addWidget(self.page1) # Index 1
        self.stack.addWidget(self.page2) # Index 2
        self.stack.addWidget(self.page3) # Index 3
        self.stack.addWidget(self.page4) # Index 4
        self.stack.addWidget(self.page5) # Index 5
        self.stack.addWidget(self.page6) # Index 6
        
        # --- [투명 프록시 프론트 레이어] ---
        # dashboard.py 등 외부 호출 컨트롤러가 기존 필드명을 그대로 쓸 수 있게 인스턴스 맵핑
        # Page 0 (메인 메뉴)
        self.btn_new          = self.page0.btn_new
        self.btn_load         = self.page0.btn_load
        self.btn_manual       = self.page0.btn_manual

        # Page 1 (데이터 구축)
        self.task_name_edit   = self.page1.task_name_edit
        self.radio_youtube    = self.page1.radio_youtube
        self.radio_local      = self.page1.radio_local
        self.youtube_widget   = self.page1.youtube_widget
        self.task_url_edit    = self.page1.task_url_edit
        self.task_count_spin  = self.page1.task_count_spin
        self.local_widget     = self.page1.local_widget
        self.task_folder_edit = self.page1.task_folder_edit
        self.btn_browse       = self.page1.btn_browse
        self.btn_s1_back      = self.page1.btn_s1_back
        self.btn_s1_start     = self.page1.btn_s1_start
        self.btn_s1_next      = self.page1.btn_s1_next

        # Page 2 (모델 학습)
        self.model_cb        = self.page2.model_cb
        self.model_desc_lbl  = self.page2.model_desc_lbl
        self.max_steps_spin  = self.page2.max_steps_spin
        self.lr_edit         = self.page2.lr_edit
        self.batch_spin      = self.page2.batch_spin
        self.grad_acc_spin   = self.page2.grad_acc_spin
        self.btn_s2_start    = self.page2.btn_s2_start
        self.btn_s2_next     = self.page2.btn_s2_next

        # Page 3 (내보내기)
        self.auto_export_cb  = self.page3.auto_export_cb
        self.auto_method_cb  = self.page3.auto_method_cb
        self.btn_create_sop  = self.page3.btn_create_sop
        self.btn_s3_start    = self.page3.btn_s3_start

        # Page 4 (과거 로드)
        self.task_list_widget = self.page4.task_list_widget
        self.btn_load_confirm = self.page4.btn_load_confirm
        self.btn_load_back    = self.page4.btn_load_back

        # Page 5 (수동 내보내기)
        self.export_task_cb   = self.page5.export_task_cb
        self.manual_method_cb = self.page5.manual_method_cb
        self.btn_export_run   = self.page5.btn_export_run

        # Page 6 (실시간 관제)
        self.mon_title        = self.page6.mon_title
        self.mon_status       = self.page6.mon_status
        self.mon_task_name    = self.page6.mon_task_name
        self.mon_steps        = self.page6.mon_steps
        self.btn_force_stop   = self.page6.btn_force_stop
        self.btn_mon_back     = self.page6.btn_mon_back

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

    def on_step_row_clicked(self, step_idx):
        """
        [인터랙티브 상태 제어기] 관제 단계 카드 클릭 시, 선결 공정 조건 충족 여부를 판단하여 
        즉각 최적의 설정 페이지로 점프 스위칭시키는 하이엔드 인터랙션 가드.
        """
        if step_idx == 0:
            return
            
        task_name = self.mon_task_name.text().replace("🏃 ", "").strip()
        if not task_name or task_name == "실시간 모니터링":
            return
            
        # 2단계(모델 학습) 클릭 시
        if step_idx == 1:
            s1_text = self.mon_steps[0].text()
            if "완료" not in s1_text:
                QMessageBox.warning(
                    self, "조건 미충족 ⏳", 
                    "앞선 1단계 [데이터 구축] 공정이 성공적으로 완료되어야\n"
                    "2단계 모델 학습(Fine-Tuning) 설정을 기동할 수 있습니다! 🛠️"
                )
                return
            
            if "진행 중" in self.mon_steps[1].text() or "완료" in self.mon_steps[1].text():
                return
                
            self.task_name_edit.setText(task_name)
            self.task_name_edit.setEnabled(False)
            self.stack.setCurrentIndex(2)
            
        # 3단계(최적화/내보내기) 클릭 시
        elif step_idx == 2:
            s2_text = self.mon_steps[1].text()
            if "완료" not in s2_text:
                QMessageBox.warning(
                    self, "조건 미충족 ⏳", 
                    "앞선 2단계 [모델 학습] 공정이 성공적으로 완료되어야\n"
                    "3단계 모델 최적화 및 양자화(GGUF) 설정을 기동할 수 있습니다! 📦"
                )
                return
            
            if "진행 중" in self.mon_steps[2].text() or "완료" in self.mon_steps[2].text():
                return
                
            self.stack.setCurrentIndex(3)
            
            task_id = None
            try:
                import sqlite3
                conn = sqlite3.connect(r"c:\ameva\AMEVA-STT-Trainer\db\stt_trainer.db")
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM tb_task WHERE tsk_nm = ? ORDER BY created_at DESC LIMIT 1", (task_name,))
                row = cursor.fetchone()
                if row:
                    task_id = row[0]
                conn.close()
            except Exception as e:
                print(f"[Wizard Error fetching ID by Name] {e}")

            if task_id:
                idx = self.export_task_cb.findData(task_id)
                if idx >= 0:
                    self.export_task_cb.setCurrentIndex(idx)
