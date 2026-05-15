import os
import glob
from src.backend.core.pseudo_router import router
from src.backend.core.task_manager import task_manager

class PipelineState:
    def __init__(self):
        self.current_task_name = "AMEVA STT Engine"
        self.current_stage = "IDLE" # IDLE, PREPROCESSING, TRAINING, EVALUATION
        
    def add_log(self, level, message):
        from src.backend.core.database import db_manager
        # task_id가 현재 잡혀있으면 태스크 종속 로그로, 아니면 통합 로그로 저장
        tid = self.current_task_name if self.current_task_name != "AMEVA STT Engine" else None
        db_manager.add_log(level, message, tid)

pipeline_state = PipelineState()

# Mock initial logs (now inserts into DB if not exists)
pipeline_state.add_log("INFO", "Initializing AMEVA-STT-Trainer Pipeline with SQLite DB...")

@router.get("/api/v1/pipeline/status")
def get_pipeline_status():
    return {
        "task_name": pipeline_state.current_task_name,
        "stage": pipeline_state.current_stage
    }

@router.get("/api/v1/pipeline/logs")
def get_pipeline_logs():
    from src.backend.core.database import db_manager
    # 현재 상태에 상관없이 통합 로그 전체를 가져옵니다. 
    # (원한다면 현재 task_id로만 가져올 수도 있습니다)
    return {"logs": db_manager.get_logs(limit=100)}

def scan_directory(base_path):
    """지정된 경로의 모든 하위 파일 목록을 재귀적으로 반환합니다."""
    if not os.path.exists(base_path):
        return []
    
    def get_recursive_items(path):
        items = []
        try:
            for entry in os.scandir(path):
                item = {
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "path": entry.path,
                    "size": entry.stat().st_size if entry.is_file() else 0
                }
                if entry.is_dir():
                    item["children"] = get_recursive_items(entry.path)
                items.append(item)
        except Exception:
            pass
        return items

    return get_recursive_items(base_path)

@router.get("/api/v1/pipeline/records")
def get_past_records():
    """과거 학습 결과(outputs) 목록을 반환합니다."""
    outputs_dir = r"c:\ameva\AMEVA-STT-Trainer\outputs"
    return {"records": scan_directory(outputs_dir)}

@router.get("/api/v1/tasks/list")
def list_tasks():
    from src.backend.core.database import db_manager
    return {"tasks": db_manager.get_all_tasks()}

@router.post("/api/v1/tasks/create")
def create_task(body: dict):
    from src.backend.core.database import db_manager
    name = body.get("name", "Unnamed Task")
    
    # 1. DB에 태스크 생성
    task_id = db_manager.create_task(name)
    
    # 2. 물리적 폴더 생성 (UUID 기반)
    base_dir = r"c:\ameva\AMEVA-STT-Trainer"
    task_folder = os.path.join(base_dir, "dataset", f"{name}_{task_id}")
    os.makedirs(task_folder, exist_ok=True)
    
    pipeline_state.current_task_name = task_id
    return {"id": task_id, "name": name, "path": task_folder}

@router.get("/api/v1/tasks/report")
def get_task_report(task_id: str = None):
    from src.backend.core.database import db_manager
    tid = task_id or pipeline_state.current_task_name
    task_details = db_manager.get_task_details(tid)
    
    if not task_details: 
        return {"error": "Task not found"}
    
    # 보고서 구조 생성
    report = {
        "task_info": task_details,
        "logs": db_manager.get_logs(task_id=tid, limit=1000),
        "files": [] # DB 기반 리포팅으로 변경됨
    }
    return report

@router.get("/api/v1/files/explorer")
def get_files_explorer():
    """학습 결과물, 로그 파일, 전처리 대상 파일 등을 재귀적으로 반환합니다."""
    base_dir = r"c:\ameva\AMEVA-STT-Trainer"
    
    return {
        "dataset": scan_directory(os.path.join(base_dir, "dataset")),
        "logs": scan_directory(os.path.join(base_dir, "logs")),
        "outputs": scan_directory(os.path.join(base_dir, "outputs")),
        "configs": scan_directory(os.path.join(base_dir, "configs"))
    }
