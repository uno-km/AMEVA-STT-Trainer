import sqlite3
import uuid
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="db/stt_trainer.db"):
        self.base_dir = r"c:\ameva\AMEVA-STT-Trainer"
        self.db_path = os.path.join(self.base_dir, db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.text_factory = str # SQLite에서 한글(Unicode)을 정확히 처리하도록 설정
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. tb_task: 메인 태스크 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tb_task (
                    id TEXT PRIMARY KEY,
                    tsk_nm TEXT NOT NULL,
                    create_dt TEXT NOT NULL,
                    level INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'RUNNING',
                    stts_dt TEXT,
                    model_path TEXT,
                    report_path TEXT,
                    log_id INTEGER,
                    checkpoint_path TEXT,
                    pipeline_config TEXT,
                    FOREIGN KEY (log_id) REFERENCES tb_log (log_id)
                )
            ''')
            
            # 마이그레이션: 기존 테이블에 신규 컬럼이 없다면 추가
            try:
                cursor.execute("ALTER TABLE tb_task ADD COLUMN checkpoint_path TEXT")
            except sqlite3.OperationalError:
                pass # 이미 존재함
            try:
                cursor.execute("ALTER TABLE tb_task ADD COLUMN pipeline_config TEXT")
            except sqlite3.OperationalError:
                pass # 이미 존재함
            
            # 1-1. tb_metric: 학습 메트릭(차트용 데이터) 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tb_metric (
                    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    step INTEGER,
                    loss REAL,
                    accuracy REAL,
                    cpu_usage REAL,
                    speed REAL,
                    create_dt TEXT,
                    FOREIGN KEY (task_id) REFERENCES tb_task (id) ON DELETE CASCADE
                )
            ''')
            
            # 2. tb_task_dtl: 상세 워크플로우 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tb_task_dtl (
                    dtl_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    step_seq INTEGER,
                    step_name TEXT,
                    parameters TEXT,
                    status TEXT DEFAULT 'PENDING',
                    next_step INTEGER,
                    FOREIGN KEY (task_id) REFERENCES tb_task (id) ON DELETE CASCADE
                )
            ''')
            
            # 3. tb_metadata: 데이터셋 매핑 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tb_metadata (
                    meta_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    folder_path TEXT NOT NULL,
                    create_dt TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tb_task (id) ON DELETE CASCADE
                )
            ''')
            
            # AUTOINCREMENT 초기값 설정
            cursor.execute("INSERT OR IGNORE INTO sqlite_sequence (name, seq) VALUES ('tb_metadata', 1000000)")
            
            # 4. tb_chunk: 오디오 조각 매핑 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tb_chunk (
                    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meta_id INTEGER NOT NULL,
                    chunk_name TEXT NOT NULL,
                    chunk_path TEXT NOT NULL,
                    script TEXT,
                    FOREIGN KEY (meta_id) REFERENCES tb_metadata (meta_id) ON DELETE CASCADE
                )
            ''')
            
            # 5. tb_log: 로그 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tb_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    create_dt TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tb_task (id) ON DELETE CASCADE
                )
            ''')
            
            conn.commit()

    # --- 로그 및 상태 관리 ---
    def add_log(self, level: str, message: str, task_id: str = None) -> int:
        create_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tb_log (task_id, level, message, create_dt) 
                VALUES (?, ?, ?, ?)
            ''', (task_id, level, message, create_dt))
            conn.commit()
            return cursor.lastrowid

    def get_logs(self, task_id: str = None, limit: int = 100):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if task_id:
                cursor.execute('SELECT * FROM tb_log WHERE task_id = ? ORDER BY create_dt ASC LIMIT ?', (task_id, limit))
            else:
                cursor.execute('SELECT * FROM tb_log ORDER BY create_dt ASC LIMIT ?', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def update_task_status(self, task_id: str, level: int, status: str, log_msg: str = None, model_path: str = None, report_path: str = None, checkpoint_path: str = None, pipeline_config: str = None):
        stts_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_id = None
        if log_msg:
            log_id = self.add_log("INFO" if status == "SUCCESS" else "ERROR" if status == "FAILED" else "INFO", log_msg, task_id)
            
        with self.get_connection() as conn:
            sql = "UPDATE tb_task SET level = ?, status = ?, stts_dt = ?"
            params = [level, status, stts_dt]
            if log_id:
                sql += ", log_id = ?"
                params.append(log_id)
            if model_path:
                sql += ", model_path = ?"
                params.append(model_path)
            if report_path:
                sql += ", report_path = ?"
                params.append(report_path)
            if checkpoint_path:
                sql += ", checkpoint_path = ?"
                params.append(checkpoint_path)
            if pipeline_config:
                sql += ", pipeline_config = ?"
                params.append(pipeline_config)
            sql += " WHERE id = ?"
            params.append(task_id)
            conn.cursor().execute(sql, params)
            conn.commit()

    def add_metric(self, task_id: str, step: int, loss: float, accuracy: float, cpu_usage: float, speed: float) -> int:
        create_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tb_metric (task_id, step, loss, accuracy, cpu_usage, speed, create_dt) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (task_id, step, loss, accuracy, cpu_usage, speed, create_dt))
            conn.commit()
            return cursor.lastrowid

    def get_metrics(self, task_id: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tb_metric WHERE task_id = ? ORDER BY step ASC', (task_id,))
            return [dict(row) for row in cursor.fetchall()]

    # --- 태스크 관리 ---
    def create_task(self, tsk_nm: str) -> str:
        task_id = str(uuid.uuid4())
        create_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            conn.execute('INSERT INTO tb_task (id, tsk_nm, create_dt, level, status) VALUES (?, ?, ?, 1, "RUNNING")', 
                         (task_id, tsk_nm, create_dt))
            conn.commit()
        return task_id

    def create_next_version_task(self, base_task_id: str) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT tsk_nm FROM tb_task WHERE id = ?', (base_task_id,))
            row = cursor.fetchone()
            if not row: return self.create_task("Unknown_Task")
            old_name = row['tsk_nm']
            if "_" in old_name and old_name.split("_")[0].isdigit():
                version = int(old_name.split("_")[0]) + 1
                new_name = f"{version}_{'_'.join(old_name.split('_')[1:])}"
            else:
                new_name = f"2_{old_name}"
            return self.create_task(new_name)

    def add_task_dtl(self, task_id: str, step_seq: int, step_name: str, parameters: str, next_step: int = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tb_task_dtl (task_id, step_seq, step_name, parameters, next_step) 
                VALUES (?, ?, ?, ?, ?)
            ''', (task_id, step_seq, step_name, parameters, next_step))
            conn.commit()
            return cursor.lastrowid

    # --- 데이터셋/청크 관리 (복구됨) ---
    def create_metadata(self, task_id: str, file_name: str, folder_path: str) -> int:
        create_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tb_metadata (task_id, file_name, folder_path, create_dt) 
                VALUES (?, ?, ?, ?)
            ''', (task_id, file_name, folder_path, create_dt))
            conn.commit()
            return cursor.lastrowid

    def create_chunk(self, meta_id: int, chunk_name: str, chunk_path: str, script: str) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tb_chunk (meta_id, chunk_name, chunk_path, script) 
                VALUES (?, ?, ?, ?)
            ''', (meta_id, chunk_name, chunk_path, script))
            conn.commit()
            return cursor.lastrowid

    # --- 조회 기능 ---
    def get_all_tasks(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tb_task ORDER BY create_dt DESC')
            return [dict(row) for row in cursor.fetchall()]

    def get_task_details(self, task_id: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tb_task WHERE id = ?', (task_id,))
            task = cursor.fetchone()
            if not task: return None
            task_dict = dict(task)
            # 상세 워크플로우 정보 추가
            cursor.execute('SELECT * FROM tb_task_dtl WHERE task_id = ? ORDER BY step_seq ASC', (task_id,))
            task_dict['details'] = [dict(row) for row in cursor.fetchall()]
            # 메타데이터 및 청크 정보 추가
            cursor.execute('SELECT * FROM tb_metadata WHERE task_id = ?', (task_id,))
            metadatas = [dict(row) for row in cursor.fetchall()]
            for meta in metadatas:
                cursor.execute('SELECT * FROM tb_chunk WHERE meta_id = ?', (meta['meta_id'],))
                meta['chunks'] = [dict(row) for row in cursor.fetchall()]
            task_dict['metadatas'] = metadatas
            return task_dict

db_manager = DatabaseManager()
