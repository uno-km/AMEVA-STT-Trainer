from src.frontend.ui.core.qt import *
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QLabel, QTextEdit, QWidget, QMainWindow

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
        
        import os
        
        info_str = (f"상태: {task_info.get('status', 'N/A')} | "
                    f"단계: Lv.{task_info.get('level', 'N/A')} | "
                    f"생성일: {task_info.get('create_dt', 'N/A')}")
        layout.addWidget(QLabel(info_str))
        
        # --- Files Section ---
        layout.addWidget(QLabel("\n📂 결과 파일 (더블 클릭하여 열기):", font=ctx.fonts['main']))
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(f"background-color: {ctx.get_color('bg_main')}; border: 1px solid {ctx.get_color('border')};")
        self.file_list.itemDoubleClicked.connect(self.open_file)
        
        # Add Word Report if exists
        word_path = report_data.get('word_report_path') or task_info.get('report_path')
        if word_path and os.path.exists(word_path):
            item = QListWidgetItem(f"📄 워드 리포트: {os.path.basename(word_path)}")
            item.setData(Qt.ItemDataRole.UserRole, word_path)
            self.file_list.addItem(item)
            
            btn_open_word = QPushButton("📄 워드 리포트 즉시 열기")
            btn_open_word.setStyleSheet("background-color: #2b5797; font-weight: bold; padding: 10px;")
            btn_open_word.clicked.connect(lambda: os.startfile(word_path))
            layout.addWidget(btn_open_word)
            
        # Add Model Path if exists
        model_path = task_info.get('model_path')
        if model_path and os.path.exists(model_path):
            item = QListWidgetItem(f"📦 생성된 모델: {os.path.basename(model_path)}")
            item.setData(Qt.ItemDataRole.UserRole, model_path)
            self.file_list.addItem(item)
            
        layout.addWidget(self.file_list)
        
        # --- Logs Section ---
        layout.addWidget(QLabel("\n📜 실행 로그 히스토리:", font=ctx.fonts['main']))
        log_box = QTextEdit()
        log_box.setReadOnly(True)
        log_box.setFont(ctx.fonts['log'])
        log_box.setStyleSheet(f"background-color: {ctx.get_color('bg_main')}; border: 1px solid {ctx.get_color('border')};")
        
        logs = report_data.get('logs', [])
        log_text = ""
        for log in logs:
            color = ctx.get_color('success') if log['level'] == 'INFO' else ctx.get_color('error') if log['level'] in ['ERROR', 'FAILED', 'CRITICAL'] else ctx.get_color('warning')
            log_text += f"<span style='color:{color}'>[{log['level']}]</span> {log['message']}<br>"
        log_box.setHtml(log_text)
        layout.addWidget(log_box)

    def open_file(self, item):
        import os
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            # 파일이 속한 폴더를 열어주거나 파일을 직접 실행
            os.startfile(path)
