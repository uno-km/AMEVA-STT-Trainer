from datetime import datetime
from .base import BaseRepository

class MetadataRepository(BaseRepository):
    """
    [MetadataRepository] tb_metadata 및 tb_chunk에 대한 오디오 청크 및 대본 스크립트 적재 레이어
    """
    def create(self, task_id: str, file_name: str, folder_path: str) -> int:
        """데이터셋 검수를 완료한 원본 오디오 파일 단위의 최상위 메타데이터 레코드를 기록합니다."""
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
        """스마트 오디오 슬라이싱 기법에 의해 분해된 발화 단위의 청크 정보와 Vosk STT 매핑 대본을 저장합니다."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tb_chunk (meta_id, chunk_name, chunk_path, script) 
                VALUES (?, ?, ?, ?)
            ''', (meta_id, chunk_name, chunk_path, script))
            conn.commit()
            return cursor.lastrowid
