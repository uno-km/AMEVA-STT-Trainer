from src.frontend.ui.core.qt import *

class MonitorPage(QWidget):
    """
    [독립 컴포넌트] 실시간 파이프라인 관제 및 단계별 조건 점프 카드 컨트롤러 화면
    """
    def __init__(self, parent_wizard):
        super().__init__()
        self.w = parent_wizard
        self.ctx = parent_wizard.ctx
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Title
        self.mon_title = QLabel("파이프라인 관제 중...")
        self.mon_title.setFont(self.ctx.fonts['title'])
        layout.addWidget(self.mon_title)
        
        # Status Box
        status_box = QFrame()
        status_box.setStyleSheet(f"background-color: {self.ctx.get_color('bg_dark')}; border-radius: 8px; padding: 15px;")
        sb_layout = QVBoxLayout(status_box)
        
        self.mon_status = QLabel("현재 상태: IDLE")
        self.mon_status.setFont(self.ctx.fonts['main'])
        sb_layout.addWidget(self.mon_status)
        
        layout.addWidget(status_box)
        
        self.mon_task_name = QLabel("실시간 모니터링", font=self.ctx.fonts['title'])
        self.mon_task_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mon_task_name.setStyleSheet(f"color: {self.ctx.get_color('accent')}; margin-bottom: 20px;")
        layout.addWidget(self.mon_task_name)
        
        self.mon_steps = []
        for i, name in enumerate(["데이터 구축", "모델 학습", "최적화/내보내기"]):
            row_widget = QFrame()
            # [호버 광채 발광 효과 & 핑거 커서 완벽 이식]
            row_widget.setStyleSheet(f"""
                QFrame {{
                    background-color: {self.ctx.get_color('bg_dark')};
                    border-radius: 10px;
                    border: 1px solid {self.ctx.get_color('border')};
                }}
                QFrame:hover {{
                    border-color: {self.ctx.get_color('accent')};
                    background-color: #1e1e30;
                }}
            """)
            row_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(15, 12, 15, 12)
            
            lbl_n = QLabel(name)
            lbl_n.setStyleSheet("font-weight: bold; border: none; font-size: 12px; color: #e2e8f0;")
            
            lbl_s = QLabel("대기 중")
            lbl_s.setStyleSheet(f"color: {self.ctx.get_color('text_dim')}; border: none; font-size: 11px;")
            
            row.addWidget(lbl_n)
            row.addStretch()
            row.addWidget(lbl_s)
            
            # 동적 람다 클릭 제어 바인딩
            row_widget.mousePressEvent = lambda event, step_idx=i: self.w.on_step_row_clicked(step_idx)
            
            self.mon_steps.append(lbl_s)
            layout.addWidget(row_widget)
            
        layout.addStretch()
        
        # 강제 종료 버튼
        self.btn_force_stop = QPushButton("🛑 작업 강제 종료 (체크포인트 저장)")
        self.btn_force_stop.setFixedHeight(40)
        self.btn_force_stop.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.btn_force_stop.palette().button().color().name() if hasattr(self, 'btn_force_stop') else self.ctx.get_color('error')};
                background-color: {self.ctx.get_color('error')};
                color: #11111b;
                font-weight: bold;
                border-radius: 6px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #f5a6bd;
            }}
        """)
        layout.addWidget(self.btn_force_stop)
        
        # 메인으로 돌아가기 버튼
        self.btn_mon_back = QPushButton("🔙 메인으로 돌아가기")
        self.btn_mon_back.setFixedHeight(40)
        self.btn_mon_back.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.ctx.get_color('bg_dark')};
                color: white;
                border: 1px solid {self.ctx.get_color('border')};
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.ctx.get_color('border')};
                border-color: {self.ctx.get_color('accent')};
            }}
        """)
        self.btn_mon_back.clicked.connect(lambda: self.w.stack.setCurrentIndex(0))
        layout.addWidget(self.btn_mon_back)
