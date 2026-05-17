from datetime import datetime
from .base import BaseRepository

class MetricRepository(BaseRepository):
    """
    [MetricRepository] tb_metric 테이블에 대한 학습 곡선용 지표 적재 및 필터링 리스트 조회 레이어
    """
    def add(self, task_id: str, step: int, loss: float, accuracy: float, cpu_usage: float, speed: float) -> int:
        """훈련 스텝별 손실값(Loss), 정확도(Accuracy), 하드웨어 점유(CPU), 초당 연산속도(Speed) 지표를 시계열 적재합니다."""
        create_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tb_metric (task_id, step, loss, accuracy, cpu_usage, speed, create_dt) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (task_id, step, loss, accuracy, cpu_usage, speed, create_dt))
            conn.commit()
            return cursor.lastrowid

    def get_all(self, task_id: str):
        """실시간 차트 드로잉을 위해 특정 태스크의 시계열 메트릭 기록을 학습 순번 오름차순으로 일괄 로딩합니다."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tb_metric WHERE task_id = ? ORDER BY step ASC', (task_id,))
            return [dict(row) for row in cursor.fetchall()]
