class BaseRepository:
    """
    [Repository Base] 모든 SQLite 데이터베이스 도메인 레포지토리의 공통 모체 클래스
    """
    def __init__(self, db):
        self.db = db

    def get_connection(self):
        """DatabaseManager로부터 안전한 SQLite Connection 세션을 가져옵니다."""
        return self.db.get_connection()
