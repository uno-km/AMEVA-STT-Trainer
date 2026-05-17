from src.frontend.ui.core.qt import *

class LogPanel(QWidget):
    """실시간 로그 출력 및 검색/제어를 담당하는 컴포넌트"""
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Controls
        controls = QHBoxLayout()
        self.auto_scroll_cb = QCheckBox("자동 스크롤")
        self.auto_scroll_cb.setChecked(True)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 로그 검색...")
        self.search_input.setStyleSheet(f"background-color: {ctx.get_color('bg_panel')}; padding: 3px;")
        self.search_input.textChanged.connect(self.filter_logs)
        
        self.max_btn = QPushButton("🔲 전체화면")
        self.max_btn.setStyleSheet(f"background-color: {ctx.get_color('border')}; font-size: 11px;")
        
        controls.addWidget(self.auto_scroll_cb)
        controls.addWidget(self.search_input)
        controls.addStretch()
        controls.addWidget(self.max_btn)
        layout.addLayout(controls)
        
        # Log View
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        self.view.setFont(ctx.fonts['log'])
        self.view.setStyleSheet(f"background-color: {ctx.get_color('bg_dark')}; color: {ctx.get_color('text')}; border: 1px solid {ctx.get_color('border')};")
        layout.addWidget(self.view)

    def update_logs(self, logs):
        # 1. 문자열(Raw Text)이 들어온 경우 처리
        if isinstance(logs, str):
            self.view.setPlainText(logs)
            if self.auto_scroll_cb.isChecked():
                self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())
            return

        # 2. 구조화된 로그(List of Dicts) 처리
        log_text = ""
        for i, log in enumerate(logs):
            ts = log.get('timestamp', '00:00:00.000')
            log_id = log.get('id', i + 1)
            level = log.get('level', 'INFO')
            message = log.get('message', '')
            
            level_color = self.ctx.get_color('success') if level == 'INFO' else self.ctx.get_color('error') if level == 'ERROR' else self.ctx.get_color('warning')
            dim_color = self.ctx.get_color('text_dim')
            
            meta = f"<span style='color:{dim_color}'>#{log_id:04d} [{ts}]</span>"
            level_html = f"<span style='color:{level_color}; font-weight: bold;'> [{level}]</span>"
            msg_html = f"<span style='color:{self.ctx.get_color('text')}'> {message}</span>"
            log_text += f"{meta}{level_html}{msg_html}<br>"
        
        self.view.setHtml(log_text)
        if self.auto_scroll_cb.isChecked():
            self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def filter_logs(self, text):
        if not text: return
        self.view.find(text)
