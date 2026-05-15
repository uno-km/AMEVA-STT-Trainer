import os
import json
import uuid
from datetime import datetime

class TaskManager:
    """
    학습 태스크의 생명주기를 관리하는 모듈.
    JSON 파일을 DB처럼 사용하여 태스크 정보를 영구 저장합니다.
    """
    def __init__(self, db_path="db/tasks.json"):
        self.db_path = db_path
        self.base_dir = r"c:\ameva\AMEVA-STT-Trainer"
        self._ensure_db()

    def _ensure_db(self):
        full_path = os.path.join(self.base_dir, self.db_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        if not os.path.exists(full_path):
            with open(full_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _load_tasks(self):
        full_path = os.path.join(self.base_dir, self.db_path)
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_tasks(self, tasks):
        full_path = os.path.join(self.base_dir, self.db_path)
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=4, ensure_ascii=False)

    def create_task(self, name):
        """새로운 태스크를 생성하고 폴더 구조를 만듭니다."""
        task_uuid = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        task_id = f"{name}-{task_uuid}-{timestamp}"
        
        # 태스크별 저장 경로 생성
        task_dir = os.path.join(self.base_dir, "dataset", task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        new_task = {
            "id": task_id,
            "name": name,
            "uuid": task_uuid,
            "timestamp": timestamp,
            "status": "CREATED",
            "path": task_dir,
            "metrics": {"loss": [], "accuracy": 0.0},
            "created_at": datetime.now().isoformat()
        }
        
        tasks = self._load_tasks()
        tasks.append(new_task)
        self._save_tasks(tasks)
        return new_task

    def list_tasks(self):
        return self._load_tasks()

    def get_task(self, task_id):
        tasks = self._load_tasks()
        for t in tasks:
            if t["id"] == task_id:
                return t
        return None

task_manager = TaskManager()
