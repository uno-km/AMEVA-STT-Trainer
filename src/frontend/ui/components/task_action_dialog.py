import os
from src.frontend.ui.core.qt import *

class TaskActionDialog(QDialog):
    """
    태스크의 현 상태를 인지하여 사용자가 원하는 액션(리포트 보기, 다음 단계 진행, 재시도, 이어하기)을 
    명확히 골라잡을 수 있도록 지원하는 최고급 프리미엄 다이얼로그.
    """
    def __init__(self, ctx, task_data, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.task_data = task_data
        self.selected_action = None
        
        self.setWindowTitle("태스크 액션 선택 🎯")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {ctx.get_color('bg_panel')};
                border: 1px solid {ctx.get_color('border')};
                border-radius: 12px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(14)
        
        # Title
        name = task_data['tsk_nm']
        level = task_data.get('level', 1)
        status = task_data.get('status', 'FAILED')
        
        title = QLabel(f"📦 {name}")
        title.setFont(ctx.fonts.get('title'))
        title.setStyleSheet(f"color: {ctx.get_color('accent')}; margin-bottom: 2px;")
        layout.addWidget(title)
        
        state_desc = f"현재 상태: {level}단계 "
        if status == "SUCCESS":
            state_desc += "성공 완료 ✅"
            color = ctx.get_color("success")
        elif status == "CANCELED":
            state_desc += "사용자 중단 🛑"
            color = ctx.get_color("error")
        elif status == "FAILED":
            state_desc += "실패 완료 ❌"
            color = ctx.get_color("error")
        else:
            state_desc += "진행 중 ⏳"
            color = ctx.get_color("warning")
            
        state_lbl = QLabel(state_desc)
        state_lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px; margin-bottom: 10px;")
        layout.addWidget(state_lbl)
        
        if status in ("FAILED", "CANCELED", "STOPPED"):
            try:
                from src.backend.core.database import db_manager
                logs = db_manager.get_logs(task_data['id'], limit=20)
                trace_msg = ""
                for log in reversed(logs):
                    msg = log.get('message', '')
                    if any(err in msg for err in ["Error:", "Exception:", "Traceback", "AttributeError", "OutOfMemoryError"]):
                        trace_msg = msg.strip()[:200]
                        break
                if trace_msg:
                    trace_lbl = QLabel(f"❌ 실패 원인: {trace_msg}")
                    trace_lbl.setWordWrap(True)
                    trace_lbl.setStyleSheet(f"color: {ctx.get_color('error')}; margin-bottom: 10px; font-weight: bold;")
                    layout.addWidget(trace_lbl)
            except:
                pass

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {ctx.get_color('border')}; max-height: 1px;")
        layout.addWidget(sep)
        
        # 버튼 분기 렌더링
        if level == 1:
            if status == "SUCCESS":
                self.add_btn("➡️ 2단계 모델 학습(Fine-Tuning) 설정으로 이동", "next_stage", ctx.get_color('accent'))
                self.add_btn("🔍 1단계 데이터 구축/검수 리포트 열기", "view_report")
                self.add_btn("🔄 1단계 데이터 구축 처음부터 재수행", "retry_stage")
            else:
                import os
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
                meta_path = os.path.join(project_root, "dataset", f"{name}_{task_data['id'][:8]}", "metadata.csv")
                has_meta = os.path.exists(meta_path)
                
                self.add_btn("🛠️ 1단계 이어서 수집 재개 (Resume)", "resume_stage", ctx.get_color('warning'))
                if has_meta:
                    self.add_btn("➡️ 2단계 모델 학습 설정으로 이동 (중단 시점의 데이터로)", "next_stage", ctx.get_color('success'))
                self.add_btn("🔄 1단계 데이터 구축 처음부터 재수행", "retry_stage")
        elif level == 2:
            self.add_btn("➡️ 3단계 모델 최적화/내보내기 설정으로 이동", "next_stage", ctx.get_color('accent'))
            if status in ["FAILED", "CANCELED", "STOPPED"]:
                self.add_btn("🛠️ 직전 체크포인트부터 이어서 학습 재개 (Resume)", "resume_stage", ctx.get_color('warning'))
            self.add_btn("🔄 2단계 모델 학습 처음부터 재수행", "retry_stage")
            self.add_btn("🔍 지금까지 적재된 로그/보고서 확인", "view_report")
        elif level == 3:
            self.add_btn("🔍 최종 배포 및 양자화 리포트 열기", "view_report", ctx.get_color('success'))
            self.add_btn("🔄 3단계 최적화/내보내기 재수행", "retry_stage")
            
        # 닫기 버튼
        cancel_btn = QPushButton("닫기")
        cancel_btn.setFixedHeight(38)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ctx.get_color('bg_dark')};
                color: white;
                border: 1px solid {ctx.get_color('border')};
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ctx.get_color('border')};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        
    def add_btn(self, text, action_code, highlight_color=None):
        btn = QPushButton(text)
        btn.setFixedHeight(45)
        if highlight_color:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {highlight_color};
                    color: #11111b;
                    font-weight: bold;
                    border-radius: 8px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    opacity: 0.9;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.ctx.get_color('bg_dark')};
                    color: white;
                    border: 1px solid {self.ctx.get_color('border')};
                    border-radius: 8px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {self.ctx.get_color('border')};
                    border-color: {self.ctx.get_color('accent')};
                }}
            """)
        btn.clicked.connect(lambda: self.select_action(action_code))
        self.layout().insertWidget(self.layout().count() - 1, btn)
        
    def select_action(self, action_code):
        self.selected_action = action_code
        self.accept()
