from datetime import datetime
from .base import BaseRepository

class LogRepository(BaseRepository):
    """
    [LogRepository] tb_log 테이블에 대한 로그 메시지 인서트 및 상세 필터링 로딩 레이어
    """
    def add(self, level: str, message: str, task_id: str = None) -> int:
        """훈련 엔진 로그 한 라인을 데이터베이스에 타임스탬프와 함께 삽입합니다."""
        create_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tb_log (task_id, level, message, create_dt) 
                VALUES (?, ?, ?, ?)
            ''', (task_id, level, message, create_dt))
            conn.commit()
            return cursor.lastrowid

    def get_all(self, task_id: str = None, limit: int = 100):
        """특정 태스크 ID 기준 혹은 전체 시스템 로그 목록을 최신순으로 가져옵니다."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if task_id:
                cursor.execute(
                    'SELECT * FROM tb_log WHERE task_id = ? ORDER BY log_id DESC LIMIT ?', 
                    (task_id, limit)
                )
            else:
                cursor.execute(
                    'SELECT * FROM tb_log ORDER BY log_id DESC LIMIT ?', 
                    (limit,)
                )
            rows = [dict(row) for row in cursor.fetchall()]
            rows.reverse()
            return rows
