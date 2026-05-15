import os
import glob
from src.backend.core.pseudo_router import router
from src.backend.core.task_manager import task_manager

class PipelineState:
    def __init__(self):
        self.current_task_name = "AMEVA STT Engine"
        self.current_stage = "IDLE" # IDLE, PREPROCESSING, TRAINING, EVALUATION
        self.logs = []
        
    def add_log(self, level, message):
        self.logs.append({"level": level, "message": message})
        # Keep last 1000 logs
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]

pipeline_state = PipelineState()

# Mock initial logs
pipeline_state.add_log("INFO", "Initializing AMEVA-STT-Trainer Pipeline...")
pipeline_state.add_log("INFO", "Loaded LoRA config: r=8, lora_alpha=32")
pipeline_state.add_log("INFO", "Started training step 1...")

@router.get("/api/v1/pipeline/status")
def get_pipeline_status():
    return {
        "task_name": pipeline_state.current_task_name,
        "stage": pipeline_state.current_stage
    }

@router.get("/api/v1/pipeline/logs")
def get_pipeline_logs():
    return {"logs": pipeline_state.logs}

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
    return {"tasks": task_manager.list_tasks()}

@router.post("/api/v1/tasks/create")
def create_task(body: dict):
    name = body.get("name", "Unnamed Task")
    task = task_manager.create_task(name)
    pipeline_state.current_task_name = task["id"]
    return task

@router.get("/api/v1/tasks/report")
def get_task_report(task_id: str = None):
    # 만약 task_id가 없으면 현재 task 사용
    tid = task_id or pipeline_state.current_task_name
    task = task_manager.get_task(tid)
    if not task: return {"error": "Task not found"}
    
    # 보고서용 상세 정보 수집
    report = {
        "task_info": task,
        "logs": pipeline_state.logs, # 실무에선 파일로그를 읽어야 함
        "files": scan_directory(task["path"])
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
