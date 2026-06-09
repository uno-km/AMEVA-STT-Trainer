import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.backend.core.task_manager import task_manager
from src.backend.core.database import db_manager
from src.backend.api.routers.dependencies import verify_api_key

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])
pipeline_router = APIRouter(prefix="/api/v1/pipeline", tags=["Pipeline"])

class PipelineState:
    def __init__(self):
        self.current_task_name = "AMEVA STT Engine"
        self.current_stage = "IDLE"
        
    def add_log(self, level, message):
        tid = self.current_task_name if self.current_task_name != "AMEVA STT Engine" else None
        db_manager.add_log(level, message, tid)

pipeline_state = PipelineState()
pipeline_state.add_log("INFO", "Initializing AMEVA-STT-Trainer Pipeline with FastAPI...")

# --- Pipeline Routes ---
@pipeline_router.get("/status", dependencies=[Depends(verify_api_key)])
def get_pipeline_status():
    return {
        "task_name": pipeline_state.current_task_name,
        "stage": pipeline_state.current_stage
    }

@pipeline_router.get("/logs", dependencies=[Depends(verify_api_key)])
def get_pipeline_logs():
    return {"logs": db_manager.get_logs(limit=100)}

@pipeline_router.get("/records", dependencies=[Depends(verify_api_key)])
def get_past_records():
    from src.backend.api.routers.files import scan_directory
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    outputs_dir = os.path.join(base_dir, "outputs")
    return {"records": scan_directory(outputs_dir)}

# --- Task Routes ---
@router.get("/list", dependencies=[Depends(verify_api_key)])
def list_tasks():
    return {"tasks": db_manager.get_all_tasks()}

@router.get("/logs", dependencies=[Depends(verify_api_key)])
def get_logs(task_id: Optional[str] = None):
    if not task_id:
        return {"logs": "선택된 태스크가 없습니다."}
    try:
        db_logs = db_manager.get_logs(task_id, limit=1000)
        formatted_logs = []
        for log in db_logs:
            dt_str = log.get("create_dt", "")
            time_part = dt_str.split(" ")[-1] if " " in dt_str else dt_str
            formatted_logs.append({
                "id": log.get("log_id"),
                "timestamp": time_part,
                "level": log.get("level", "INFO"),
                "message": log.get("message", "")
            })
        return {"logs": formatted_logs}
    except Exception as e:
        return {"logs": f"로그 로드 실패: {str(e)}"}

class InitDataRequest(BaseModel):
    name: str = "New Task"
    step_limit: int = 1
    step1_params: Dict[str, Any] = {}
    step2_params: Dict[str, Any] = {}
    step3_params: Dict[str, Any] = {}

@router.post("/init_data", dependencies=[Depends(verify_api_key)])
def init_data(req: InitDataRequest):
    res = task_manager.init_data(req.name, req.step_limit, req.step1_params, req.step2_params, req.step3_params)
    pipeline_state.current_task_name = res["id"]
    return res

class StartTrainRequest(BaseModel):
    task_id: str
    step_limit: int = 2
    step2_params: Dict[str, Any] = {}
    step3_params: Dict[str, Any] = {}

@router.post("/start_train", dependencies=[Depends(verify_api_key)])
def start_train(req: StartTrainRequest):
    pipeline_state.current_task_name = req.task_id
    return task_manager.start_train(req.task_id, req.step_limit, req.step2_params, req.step3_params)

class StopTaskRequest(BaseModel):
    task_id: str

@router.post("/stop", dependencies=[Depends(verify_api_key)])
def stop_task(req: StopTaskRequest):
    if req.task_id:
        return task_manager.force_stop_task(req.task_id)
    raise HTTPException(status_code=400, detail="No task_id provided")

class RestartTaskRequest(BaseModel):
    task_id: str

@router.post("/restart", dependencies=[Depends(verify_api_key)])
def restart_task(req: RestartTaskRequest):
    if not req.task_id: raise HTTPException(status_code=400, detail="Missing task_id")
    new_task_id = db_manager.create_next_version_task(req.task_id)
    task_info = db_manager.get_task_details(new_task_id)
    db_manager.update_task_status(new_task_id, 1, "RUNNING", f"Restarted from {req.task_id}")
    pipeline_state.current_task_name = new_task_id
    return {"id": new_task_id, "name": task_info['tsk_nm']}

@router.get("/metrics", dependencies=[Depends(verify_api_key)])
def get_task_metrics(task_id: Optional[str] = None):
    if not task_id: return {"metrics": []}
    return {"metrics": db_manager.get_metrics(task_id)}

@router.get("/report", dependencies=[Depends(verify_api_key)])
def get_task_report(task_id: Optional[str] = None):
    from src.backend.core.reporter import report_generator
    tid = task_id or pipeline_state.current_task_name
    task_details = db_manager.get_task_details(tid)
    
    if not task_details: 
        raise HTTPException(status_code=404, detail="Task not found")
    
    report_path = None
    try:
        report_path = report_generator.generate_task_report(tid)
    except Exception as e:
        print(f"Failed to generate Word report: {e}")
    
    return {
        "task_info": task_details,
        "logs": db_manager.get_logs(task_id=tid, limit=1000),
        "word_report_path": report_path
    }
