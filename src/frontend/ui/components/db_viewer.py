import sqlite3
import os
from src.frontend.ui.core.qt import *

class DBViewerPanel(QWidget):
    """
    AMEVA MLOps Premium Database Inspector
    - Provides real-time view of SQLite internal tables
    - Full-text search filters across all table columns dynamically
    - Custom SELECT SQL executor for advanced database inspection
    """
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.db_path = r"c:\ameva\AMEVA-STT-Trainer\db\stt_trainer.db"
        self.init_ui()
        self.load_table_data()

    def init_ui(self):
        # Sleek glassmorphic dark theme matches the context palette
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {self.ctx.get_color('bg_main')};
                color: {self.ctx.get_color('text')};
            }}
            QComboBox, QLineEdit {{
                background-color: {self.ctx.get_color('bg_panel')};
                border: 1px solid {self.ctx.get_color('border')};
                border-radius: 6px;
                padding: 6px 10px;
                color: {self.ctx.get_color('text')};
                font-size: 11px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QPushButton {{
                background-color: {self.ctx.get_color('accent')};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #3b82f6;
            }}
            QTableWidget {{
                background-color: {self.ctx.get_color('bg_panel')};
                border: 1px solid {self.ctx.get_color('border')};
                gridline-color: {self.ctx.get_color('border')};
                color: {self.ctx.get_color('text')};
                border-radius: 6px;
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {self.ctx.get_color('bg_dark')};
                color: {self.ctx.get_color('text')};
                padding: 8px;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid {self.ctx.get_color('border')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # --- 1. Top Bar: Quick Table Selector & Keyword Filter ---
        top_bar = QHBoxLayout()
        
        lbl_table = QLabel("🗄️ 테이블:")
        lbl_table.setStyleSheet("font-weight: bold; font-size: 11px; color: #a3a3a3;")
        
        self.cb_table = QComboBox()
        self.cb_table.addItems(["tb_task", "tb_task_dtl", "tb_metric", "tb_metadata", "tb_log", "tb_chunk"])
        self.cb_table.setMinimumWidth(120)
        self.cb_table.currentIndexChanged.connect(self.load_table_data)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 테이블 내 글로벌 키워드 필터링... (Enter)")
        self.search_input.returnPressed.connect(self.load_table_data)
        
        btn_refresh = QPushButton("🔄 새로고침")
        btn_refresh.clicked.connect(self.load_table_data)
        
        top_bar.addWidget(lbl_table)
        top_bar.addWidget(self.cb_table)
        top_bar.addWidget(self.search_input, 2)
        top_bar.addWidget(btn_refresh)
        layout.addLayout(top_bar)

        # --- 2. Middle Bar: Custom SQL Query Runner ---
        sql_layout = QHBoxLayout()
        
        self.sql_input = QLineEdit()
        self.sql_input.setPlaceholderText("SELECT * FROM tb_task WHERE status = 'SUCCESS' (자유 SELECT SQL 입력 후 Enter)")
        self.sql_input.returnPressed.connect(self.execute_custom_sql)
        
        btn_sql = QPushButton("⚡ SQL 실행")
        btn_sql.setStyleSheet(f"background-color: {self.ctx.get_color('success')};")
        btn_sql.clicked.connect(self.execute_custom_sql)
        
        sql_layout.addWidget(self.sql_input, 4)
        sql_layout.addWidget(btn_sql)
        layout.addLayout(sql_layout)

        # --- 3. Premium Data Table View ---
        self.table_widget = QTableWidget()
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setStyleSheet(f"""
            QTableWidget {{
                alternate-background-color: {self.ctx.get_color('bg_dark')};
            }}
        """)
        layout.addWidget(self.table_widget, 1)

    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def load_table_data(self):
        """테이블 선택 및 검색어에 따라 실시간 쿼리 조립 및 로드"""
        table_name = self.cb_table.currentText()
        search_term = self.search_input.text().strip()
        
        query = f"SELECT * FROM {table_name}"
        params = []
        
        if search_term:
            # PRAGMA를 사용하여 테이블 컬럼 스키마를 실시간 동적으로 획득
            try:
                conn = self.get_db_connection()
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info({table_name})")
                cols = [row[1] for row in cursor.fetchall()]
                conn.close()
                
                # 모든 컬럼에 대해 검색어가 포함된 항목이 있는지 OR 연산 조립 (풀텍스트 스캔 모사)
                if cols:
                    where_clauses = [f"CAST({col} AS TEXT) LIKE ?" for col in cols]
                    query += " WHERE " + " OR ".join(where_clauses)
                    params = [f"%{search_term}%"] * len(cols)
            except Exception as e:
                print(f"[DB Schema Discover Error] {e}")
        
        self.run_select_query(query, params)

    def execute_custom_sql(self):
        """커스텀 SQL 구문 실행 및 예외 가드 장치"""
        sql = self.sql_input.text().strip()
        if not sql:
            return
        
        # 보안 경계선: 오직 SELECT문만 허용하여 파괴적인 변경 예방
        if not sql.lower().startswith("select"):
            QMessageBox.warning(self, "쿼리 제한 알림", "안전상의 이유로 오직 SELECT 조회 구문만 실행할 수 있습니다.")
            return
            
        self.run_select_query(sql)

    def run_select_query(self, query, params=None):
        """쿼리를 수행하여 테이블에 시각화 렌더링"""
        if params is None:
            params = []
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # 조회 데이터가 아예 없을 때 깔끔하게 비움
            if not rows:
                self.table_widget.setColumnCount(0)
                self.table_widget.setRowCount(0)
                conn.close()
                return
            
            # 1. 컬럼 헤더 셋팅
            columns = rows[0].keys()
            self.table_widget.setColumnCount(len(columns))
            self.table_widget.setHorizontalHeaderLabels(columns)
            
            # 2. 행 데이터 셋팅
            self.table_widget.setRowCount(len(rows))
            for r_idx, row in enumerate(rows):
                for c_idx, col in enumerate(columns):
                    val = row[col]
                    item = QTableWidgetItem(str(val) if val is not None else "")
                    
                    # 사용자가 대시보드 내에서 데이터 셀 값을 임의 편집하는 것 방지 (Read-Only)
                    item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                    self.table_widget.setItem(r_idx, c_idx, item)
                    
            # 3. 미려한 셀 크기 재정렬
            self.table_widget.resizeColumnsToContents()
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "SQL 실행 오류", f"조회 중 오류가 발생했습니다:\n{str(e)}")
