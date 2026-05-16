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

@router.post("/api/v1/tasks/init_data")
def init_data(body: dict):
    name = body.get("name", "Unnamed Task")
    source_type = body.get("source_type", "youtube")
    url = body.get("url", "")
    count = body.get("count", 5)
    folder = body.get("folder", "")
    
    # 1단계 시작
    task_info = task_manager.init_data(name, source_type, url, count, folder)
    return task_info

@router.post("/api/v1/tasks/start_train")
def start_train(body: dict):
    task_id = body.get("task_id")
    if not task_id: return {"error": "Missing task_id"}
    
    max_steps = body.get("max_steps", 100)
    auto_export = body.get("auto_export", True)
    method = body.get("method", "q4_0")
    
    # 2-3단계 가동
    res = task_manager.start_train(task_id, max_steps, auto_export, method)
    return res

@router.post("/api/v1/tasks/restart")
def restart_task(body: dict):
    from src.backend.core.database import db_manager
    base_task_id = body.get("task_id")
    if not base_task_id: return {"error": "Missing base_task_id"}
    
    # 새 버전 태스크 생성 (예: 2_태스크명)
    new_task_id = db_manager.create_next_version_task(base_task_id)
    task_info = db_manager.get_task_details(new_task_id)
    
    db_manager.update_task_status(new_task_id, 1, "RUNNING", f"Restarted from {base_task_id}")
    pipeline_state.current_task_name = new_task_id
    return {"id": new_task_id, "name": task_info['tsk_nm']}

@router.get("/api/v1/tasks/report")
def get_task_report(task_id: str = None):
    from src.backend.core.database import db_manager
    from src.backend.core.reporter import report_generator
    
    tid = task_id or pipeline_state.current_task_name
    task_details = db_manager.get_task_details(tid)
    
    if not task_details: 
        return {"error": "Task not found"}
    
    # 워드 리포트 생성
    report_path = None
    try:
        report_path = report_generator.generate_task_report(tid)
    except Exception as e:
        print(f"Failed to generate Word report: {e}")
    
    # 보고서 구조 생성
    report = {
        "task_info": task_details,
        "logs": db_manager.get_logs(task_id=tid, limit=1000),
        "word_report_path": report_path
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
