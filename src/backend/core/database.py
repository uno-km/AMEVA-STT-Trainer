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
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Task 테이블 생성
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tb_task (
                    id TEXT PRIMARY KEY,
                    tsk_nm TEXT NOT NULL,
                    create_dt TEXT NOT NULL
                )
            ''')
            
            # Metadata 매핑 테이블 생성 (시퀀스는 1000001부터 시작)
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
            
            # AUTOINCREMENT 초기값 설정 (최초 1회만 적용됨)
            cursor.execute("INSERT OR IGNORE INTO sqlite_sequence (name, seq) VALUES ('tb_metadata', 1000000)")
            
            # Chunk 매핑 테이블 생성
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
            
            # Log 테이블 생성 (통합 로그 및 태스크 개별 로그 관리)
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
                # 통합 로그 (최신 순으로 가져와서 표시 시엔 정렬 고려)
                cursor.execute('SELECT * FROM tb_log ORDER BY create_dt ASC LIMIT ?', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def create_task(self, tsk_nm: str) -> str:
        task_id = str(uuid.uuid4())
        create_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            conn.execute('INSERT INTO tb_task (id, tsk_nm, create_dt) VALUES (?, ?, ?)', 
                         (task_id, tsk_nm, create_dt))
            conn.commit()
        return task_id

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
            
            cursor.execute('SELECT * FROM tb_metadata WHERE task_id = ?', (task_id,))
            metadatas = [dict(row) for row in cursor.fetchall()]
            
            for meta in metadatas:
                cursor.execute('SELECT * FROM tb_chunk WHERE meta_id = ?', (meta['meta_id'],))
                meta['chunks'] = [dict(row) for row in cursor.fetchall()]
                
            task_dict['metadatas'] = metadatas
            return task_dict

db_manager = DatabaseManager()
