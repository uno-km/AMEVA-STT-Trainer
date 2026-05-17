import csv
import os
import sqlite3
from src.frontend.ui.core.qt import *

class CSVViewer(QTableWidget):
    """CSV 데이터를 격자 형태로 보여주는 범용 컴포넌트"""
    def __init__(self, ctx, file_path=None):
        super().__init__()
        self.ctx = ctx
        self.setStyleSheet(f"background-color: {ctx.get_color('bg_main')}; color: {ctx.get_color('text')}; gridline-color: {ctx.get_color('border')};")
        self.horizontalHeader().setStyleSheet(f"background-color: {ctx.get_color('border')}; color: {ctx.get_color('text')};")
        
        if file_path:
            self.load_csv(file_path)

    def load_csv(self, file_path):
        try:
            with open(file_path, newline='', encoding='utf-8') as f:
                reader = list(csv.reader(f))
                if not reader: return
                
                self.setRowCount(len(reader))
                self.setColumnCount(len(reader[0]))
                self.setHorizontalHeaderLabels(reader[0])
                
                for row_idx, row_data in enumerate(reader[1:]):
                    for col_idx, cell_data in enumerate(row_data):
                        self.setItem(row_idx, col_idx, QTableWidgetItem(cell_data))
                
                self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        except Exception as e:
            print(f"CSV Load Error: {e}")


class LogViewer(QWidget):
    """
    AMEVA Premium Monospace Log Console Viewer
    - 자동으로 태스크 전용 .log 물리 파일 검색 시도
    - 물리 파일이 없거나 유실된 경우, SQLite tb_log의 관계 데이터를 역추적하여 완벽 복원해 냄
    - 새로고침 및 미려한 터미널 폰트 스킨셋 적용
    """
    def __init__(self, ctx, task_id, task_name):
        super().__init__()
        self.ctx = ctx
        self.task_id = task_id
        self.task_name = task_name
        self.db_path = r"c:\ameva\AMEVA-STT-Trainer\db\stt_trainer.db"
        self.init_ui()
        self.reload_logs()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 1. Top Bar Control panel
        top_bar = QHBoxLayout()
        lbl_icon = QLabel("📜")
        lbl_icon.setStyleSheet("font-size: 14px;")
        
        self.lbl_title = QLabel(f"[{self.task_name}] 누적 상태 상세 콘솔 (태스크 ID: {self.task_id[:8]})")
        self.lbl_title.setStyleSheet(f"font-weight: bold; font-size: 11px; color: {self.ctx.get_color('accent')};")
        
        btn_reload = QPushButton("🔄 로그 실시간 동기화")
        btn_reload.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.ctx.get_color('bg_dark')};
                color: white;
                border: 1px solid {self.ctx.get_color('border')};
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.ctx.get_color('border')};
                border-color: {self.ctx.get_color('accent')};
            }}
        """)
        btn_reload.clicked.connect(self.reload_logs)

        top_bar.addWidget(lbl_icon)
        top_bar.addWidget(self.lbl_title)
        top_bar.addStretch()
        top_bar.addWidget(btn_reload)
        layout.addLayout(top_bar)

        # 2. Terminal Emulation PlainTextEdit
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {self.ctx.get_color('bg_dark')};
                color: #eaeaea;
                border: 1px solid {self.ctx.get_color('border')};
                border-radius: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                line-height: 1.4;
                padding: 10px;
            }}
        """)
        layout.addWidget(self.console, 1)

    def reload_logs(self):
        log_content = ""
        log_file = f"logs/task_{self.task_id}.log"

        # 1차 시도: 물리 로그 파일 파싱 및 버퍼 로딩
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    log_content = f.read().strip()
            except Exception as e:
                print(f"[LogViewer File Read Error] {e}")

        # 2차 시도: 파일이 없거나 비어있는 경우, SQLite db의 tb_log를 정밀 쿼리하여 영구 로그 복원
        if not log_content:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT log_level, message, created_at FROM tb_log WHERE task_id = ? ORDER BY id ASC",
                    (self.task_id,)
                )
                rows = cursor.fetchall()
                conn.close()

                if rows:
                    lines = [f"--- [{self.task_name}] SQLite 백업 로그 복구 기동 완료 ---"]
                    for row in rows:
                        lines.append(f"[{row[2]}] [{row[0]}] {row[1]}")
                    log_content = "\n".join(lines)
                else:
                    log_content = "--- [알림] 본 태스크에 매핑되거나 적재된 누적 로그 기록이 디렉터리 및 데이터베이스 모두에 존재하지 않습니다. ---"
            except Exception as db_e:
                log_content = f"--- [에러] 로그 유실 복구 쿼리 실패: {str(db_e)} ---"

        self.console.setPlainText(log_content)
        # 콘솔을 즉각 가장 최신 로그가 기록된 최하단(Autoscroll)으로 스크롤 이동
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

