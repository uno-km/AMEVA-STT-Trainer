import sqlite3
import os
from datetime import datetime

# 신규 리포지토리 도메인 모듈들 임포트
from src.backend.core.repositories import (
    TaskRepository, LogRepository, MetricRepository, MetadataRepository
)

class DatabaseManager:
    """
    [DatabaseManager - Facade Shell] 
    - STT 트레이너 SQLite 데이터베이스 세션 및 커넥션 풀을 관리합니다.
    - SQL 쿼리 비즈니스 로직은 도메인별 Repository(tasks, logs, metrics, metadata)로 위임합니다.
    - 기존 API 및 백엔드 스크립트와의 100% 하위 호환성을 위한 파사드(Facade) 인터페이스 제공.
    """
    def __init__(self, db_path="db/stt_trainer.db"):
        self.base_dir = r"c:\ameva\AMEVA-STT-Trainer"
        self.db_path = os.path.join(self.base_dir, db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        
        # --- [도메인별 레포지토리 객체 생성 및 DI 주입] ---
        self.tasks = TaskRepository(self)
        self.logs = LogRepository(self)
        self.metrics = MetricRepository(self)
        self.metadata = MetadataRepository(self)

    def get_connection(self):
        """SQLite 데이터베이스와의 스레드 안전 커넥션 객체를 생성하여 반환합니다."""
        conn = sqlite3.connect(self.db_path)
        conn.text_factory = str # 한글 유니코드 크래시 방지 세팅
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """데이터베이스 기동 시 필요한 프리미엄 테이블 규격 및 스키마 일괄 구축 (기존 마이그레이션 호환)"""
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
            
            # 마이그레이션 가드
            try:
                cursor.execute("ALTER TABLE tb_task ADD COLUMN checkpoint_path TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE tb_task ADD COLUMN pipeline_config TEXT")
            except sqlite3.OperationalError:
                pass
            
            # 2. tb_metric: 성능 지표 테이블
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
            
            # 3. tb_task_dtl: 상세 SOP 단계 제어 테이블
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
            
            # 4. tb_metadata: 수집 오디오 데이터셋 매핑 테이블
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
            
            cursor.execute("INSERT OR IGNORE INTO sqlite_sequence (name, seq) VALUES ('tb_metadata', 1000000)")
            
            # 5. tb_chunk: 슬라이싱 발화 청크 정보 및 대본 매핑 테이블
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
            
            # 6. tb_log: 전체 로그 저장소 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tb_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    create_dt TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tb_task (id) ON DELETE CASCADE
                )
            
            # 7. tb_thread_log: 쓰레드 개수 조절 기록 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tb_thread_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    threads INTEGER NOT NULL,
                    create_dt TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tb_task (id) ON DELETE CASCADE
                )
            ''')
            
            conn.commit()

    # ==========================================================
    # --- [하위 호환성 레이어: 기존 메소드 호출을 레포지토리로 투명 포워딩] ---
    # ==========================================================
    
    def add_log(self, level: str, message: str, task_id: str = None) -> int:
        return self.logs.add(level, message, task_id)

    def get_logs(self, task_id: str = None, limit: int = 100):
        return self.logs.get_all(task_id, limit)

    def update_task_status(self, task_id: str, level: int, status: str, log_msg: str = None, 
                           model_path: str = None, report_path: str = None, 
                           checkpoint_path: str = None, pipeline_config: str = None):
        self.tasks.update_status(task_id, level, status, log_msg, model_path, report_path, checkpoint_path, pipeline_config)

    def add_metric(self, task_id: str, step: int, loss: float, accuracy: float, cpu_usage: float, speed: float) -> int:
        return self.metrics.add(task_id, step, loss, accuracy, cpu_usage, speed)

    def get_metrics(self, task_id: str):
        return self.metrics.get_all(task_id)

    def create_task(self, tsk_nm: str) -> str:
        return self.tasks.create(tsk_nm)

    def create_next_version_task(self, base_task_id: str) -> str:
        return self.tasks.create_next_version(base_task_id)

    def add_task_dtl(self, task_id: str, step_seq: int, step_name: str, parameters: str, next_step: int = None) -> int:
        return self.tasks.add_detail(task_id, step_seq, step_name, parameters, next_step)

    def create_metadata(self, task_id: str, file_name: str, folder_path: str) -> int:
        return self.metadata.create(task_id, file_name, folder_path)

    def create_chunk(self, meta_id: int, chunk_name: str, chunk_path: str, script: str) -> int:
        return self.metadata.create_chunk(meta_id, chunk_name, chunk_path, script)

    def get_all_tasks(self):
        return self.tasks.get_all()

    def get_task_details(self, task_id: str):
        return self.tasks.get_details(task_id)

    def add_thread_log(self, task_id: str, threads: int) -> int:
        if not task_id: return -1
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tb_thread_log (task_id, threads, create_dt)
                VALUES (?, ?, ?)
            ''', (task_id, threads, now_str))
            conn.commit()
            return cursor.lastrowid
            
    def get_thread_logs(self, task_id: str) -> list:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT threads, create_dt FROM tb_thread_log
                WHERE task_id = ?
                ORDER BY create_dt ASC
            ''', (task_id,))
            rows = cursor.fetchall()
            return [{"threads": r["threads"], "time": r["create_dt"]} for r in rows]

# 글로벌 단일 인스턴스 기동 및 외부 바인딩
db_manager = DatabaseManager()
