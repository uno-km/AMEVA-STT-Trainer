from src.frontend.ui.core.qt import *

class ReportWindow(QMainWindow):
    """과거 태스크의 상세 리포트를 보여주는 독립 윈도우 컴포넌트"""
    def __init__(self, ctx, report_data):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(f"Task Report: {report_data.get('task_info', {}).get('tsk_nm', 'Unknown')}")
        self.resize(800, 600)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        central.setStyleSheet(f"background-color: {ctx.get_color('bg_dark')}; color: {ctx.get_color('text')};")
        
        # Header Info
        task_info = report_data.get('task_info', {})
        header = QLabel(f"태스크 리포트: {task_info.get('tsk_nm', 'N/A')}")
        header.setFont(ctx.fonts['title'])
        layout.addWidget(header)
        
        info_str = (f"상태: {task_info.get('step_stts', 'N/A')} | "
                    f"단계: Lv.{task_info.get('step_lv', 'N/A')} | "
                    f"생성일: {task_info.get('create_dt', 'N/A')}")
        layout.addWidget(QLabel(info_str))
        
        # Logs Section
        layout.addWidget(QLabel("\n실행 로그 히스토리:", font=ctx.fonts['main']))
        log_box = QTextEdit()
        log_box.setReadOnly(True)
        log_box.setFont(ctx.fonts['log'])
        log_box.setStyleSheet(f"background-color: {ctx.get_color('bg_main')}; border: 1px solid {ctx.get_color('border')};")
        
        logs = report_data.get('logs', [])
        log_text = ""
        for log in logs:
            color = ctx.get_color('success') if log['level'] == 'INFO' else ctx.get_color('error') if log['level'] == 'ERROR' else ctx.get_color('warning')
            log_text += f"<span style='color:{color}'>[{log['level']}]</span> {log['message']}<br>"
        log_box.setHtml(log_text)
        layout.addWidget(log_box)
