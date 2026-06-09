import os
import glob
import json
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import sqlite3

from src.backend.core.task_manager import task_manager

router = APIRouter()

# 보안 설정 기반 (API Key)
# 향후 환경 변수 AMEVA_API_KEY 설정 시, X-API-Key 헤더로 인증 수행
AMEVA_API_KEY = os.environ.get("AMEVA_API_KEY", "")

def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if AMEVA_API_KEY and x_api_key != AMEVA_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True

class PipelineState:
    def __init__(self):
        self.current_task_name = "AMEVA STT Engine"
        self.current_stage = "IDLE" # IDLE, PREPROCESSING, TRAINING, EVALUATION
        
    def add_log(self, level, message):
        from src.backend.core.database import db_manager
        tid = self.current_task_name if self.current_task_name != "AMEVA STT Engine" else None
        db_manager.add_log(level, message, tid)

pipeline_state = PipelineState()
pipeline_state.add_log("INFO", "Initializing AMEVA-STT-Trainer Pipeline with FastAPI...")


@router.get("/api/v1/pipeline/status", dependencies=[Depends(verify_api_key)])
def get_pipeline_status():
    return {
        "task_name": pipeline_state.current_task_name,
        "stage": pipeline_state.current_stage
    }

@router.get("/api/v1/pipeline/logs", dependencies=[Depends(verify_api_key)])
def get_pipeline_logs():
    from src.backend.core.database import db_manager
    return {"logs": db_manager.get_logs(limit=100)}

def scan_directory(base_path):
    if not os.path.exists(base_path):
        return []
    
    def get_recursive_items(path, depth=0):
        if depth > 10: return []
        items = []
        try:
            for entry in os.scandir(path):
                if entry.name == "chunks" and entry.is_dir():
                    items.append({
                        "name": entry.name, "is_dir": True, "path": entry.path, "size": 0, "children": []
                    })
                    continue
                item = {
                    "name": entry.name, "is_dir": entry.is_dir(), "path": entry.path, "size": entry.stat().st_size if entry.is_file() else 0
                }
                if entry.is_dir():
                    item["children"] = get_recursive_items(entry.path, depth + 1)
                items.append(item)
        except Exception:
            pass
        return items
    return get_recursive_items(base_path)

@router.get("/api/v1/pipeline/records", dependencies=[Depends(verify_api_key)])
def get_past_records():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    outputs_dir = os.path.join(base_dir, "outputs")
    return {"records": scan_directory(outputs_dir)}

@router.get("/api/v1/tasks/logs", dependencies=[Depends(verify_api_key)])
def get_logs(task_id: Optional[str] = None):
    if not task_id:
        return {"logs": "선택된 태스크가 없습니다."}
    try:
        from src.backend.core.database import db_manager
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

@router.get("/api/v1/tasks/list", dependencies=[Depends(verify_api_key)])
def list_tasks():
    from src.backend.core.database import db_manager
    return {"tasks": db_manager.get_all_tasks()}

class InitDataRequest(BaseModel):
    name: str = "New Task"
    step_limit: int = 1
    step1_params: Dict[str, Any] = {}
    step2_params: Dict[str, Any] = {}
    step3_params: Dict[str, Any] = {}

@router.post("/api/v1/tasks/init_data", dependencies=[Depends(verify_api_key)])
def init_data(req: InitDataRequest):
    res = task_manager.init_data(req.name, req.step_limit, req.step1_params, req.step2_params, req.step3_params)
    pipeline_state.current_task_name = res["id"]
    return res

class StartTrainRequest(BaseModel):
    task_id: str
    step_limit: int = 2
    step2_params: Dict[str, Any] = {}
    step3_params: Dict[str, Any] = {}

@router.post("/api/v1/tasks/start_train", dependencies=[Depends(verify_api_key)])
def start_train(req: StartTrainRequest):
    pipeline_state.current_task_name = req.task_id
    return task_manager.start_train(req.task_id, req.step_limit, req.step2_params, req.step3_params)

class StopTaskRequest(BaseModel):
    task_id: str

@router.post("/api/v1/tasks/stop", dependencies=[Depends(verify_api_key)])
def stop_task(req: StopTaskRequest):
    if req.task_id:
        return task_manager.force_stop_task(req.task_id)
    raise HTTPException(status_code=400, detail="No task_id provided")

class RestartTaskRequest(BaseModel):
    task_id: str

@router.post("/api/v1/tasks/restart", dependencies=[Depends(verify_api_key)])
def restart_task(req: RestartTaskRequest):
    from src.backend.core.database import db_manager
    if not req.task_id: raise HTTPException(status_code=400, detail="Missing task_id")
    
    new_task_id = db_manager.create_next_version_task(req.task_id)
    task_info = db_manager.get_task_details(new_task_id)
    db_manager.update_task_status(new_task_id, 1, "RUNNING", f"Restarted from {req.task_id}")
    pipeline_state.current_task_name = new_task_id
    return {"id": new_task_id, "name": task_info['tsk_nm']}

@router.get("/api/v1/tasks/metrics", dependencies=[Depends(verify_api_key)])
def get_task_metrics(task_id: Optional[str] = None):
    from src.backend.core.database import db_manager
    if not task_id: return {"metrics": []}
    return {"metrics": db_manager.get_metrics(task_id)}

@router.get("/api/v1/tasks/report", dependencies=[Depends(verify_api_key)])
def get_task_report(task_id: Optional[str] = None):
    from src.backend.core.database import db_manager
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
    
    report = {
        "task_info": task_details,
        "logs": db_manager.get_logs(task_id=tid, limit=1000),
        "word_report_path": report_path
    }
    return report

@router.get("/api/v1/files/explorer", dependencies=[Depends(verify_api_key)])
def get_files_explorer():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    return {
        "dataset": scan_directory(os.path.join(base_dir, "dataset")),
        "logs": scan_directory(os.path.join(base_dir, "logs")),
        "outputs": scan_directory(os.path.join(base_dir, "outputs")),
        "configs": scan_directory(os.path.join(base_dir, "configs"))
    }

@router.get("/api/v1/system/resources", dependencies=[Depends(verify_api_key)])
def get_resources():
    import psutil
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        ram_used = psutil.virtual_memory().used / (1024 ** 3)
        ram_total = psutil.virtual_memory().total / (1024 ** 3)
        gpu = 0
        gpu_mem = "N/A"
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus: 
                gpu = gpus[0].load * 100
                gpu_mem = f"{gpus[0].memoryUsed:.0f}/{gpus[0].memoryTotal:.0f} MB"
        except: pass
        
        # Windows 환경 대응: 프로젝트 루트 기준으로 디스크 체크
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        disk = psutil.disk_usage(project_root)
        disk_pct = disk.percent
        disk_used = disk.used / (1024**3)
        disk_total = disk.total / (1024**3)
        
        procs = []
        for p in sorted([p.info for p in psutil.process_iter(['pid','name','cpu_percent','memory_info'])], key=lambda p: p.get('cpu_percent') or 0, reverse=True)[:5]:
            mem_mb = (p.get('memory_info').rss / (1024**2)) if p.get('memory_info') else 0
            procs.append({
                "pid": p.get('pid', ''),
                "name": p.get('name', '')[:25],
                "cpu": f"{p.get('cpu_percent', 0):.1f}",
                "mem": f"{mem_mb:.1f} MB"
            })
            
        return {
            "cpu": cpu, "ram": ram, "gpu": gpu, "gpu_mem": gpu_mem,
            "ram_used": ram_used, "ram_total": ram_total,
            "disk_pct": disk_pct, "disk_used": disk_used, "disk_total": disk_total,
            "processes": procs
        }
    except Exception as e:
        return {"error": str(e), "cpu": 0, "ram": 0, "gpu": 0}

class SqlQueryRequest(BaseModel):
    sql: str
    params: List[Any] = []

@router.post("/api/v1/db/query", dependencies=[Depends(verify_api_key)])
def run_db_query(req: SqlQueryRequest):
    if not req.sql.strip().lower().startswith("select") and not req.sql.strip().lower().startswith("pragma"):
        return {"error": "Only SELECT or PRAGMA queries are allowed."}
    try:
        from src.backend.core.database import db_manager
        with db_manager.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(req.sql, req.params)
            rows = cur.fetchall()
            if not rows: return {"columns": [], "rows": []}
            cols = list(rows[0].keys())
            return {"columns": cols, "rows": [list(r) for r in rows]}
    except Exception as e:
        return {"error": str(e)}

@router.get("/api/v1/files/read", dependencies=[Depends(verify_api_key)])
def read_file_content(path: str):
    import os
    if not os.path.exists(path):
        return {"error": "File not found"}
    try:
        if path.endswith(".csv"):
            import csv
            with open(path, newline='', encoding='utf-8', errors='replace') as f:
                return {"type": "csv", "content": list(csv.reader(f))}
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return {"type": "text", "content": f.readlines()}
    except Exception as e:
        return {"error": str(e)}

@router.get("/api/v1/files/search", dependencies=[Depends(verify_api_key)])
def search_files(keyword: str, exts: Optional[str] = None):
    import os
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    search_dirs = [os.path.join(base_dir, d) for d in ("dataset","outputs","logs","configs","scripts") if os.path.isdir(os.path.join(base_dir, d))]
    
    ext_list = None
    if exts:
        ext_list = [e.strip() if e.strip().startswith(".") else f".{e.strip()}" for e in exts.split(",") if e.strip()]
        
    results = []
    skip = {"chunks", "__pycache__", ".git", "venv"}
    
    for d in search_dirs:
        for root, dirs, files in os.walk(d):
            dirs[:] = [dir_name for dir_name in dirs if dir_name not in skip]
            for f in files:
                if ext_list and os.path.splitext(f)[1].lower() not in ext_list:
                    continue
                if keyword.lower() in f.lower():
                    filepath = os.path.join(root, f)
                    try:
                        size = os.path.getsize(filepath)
                        results.append({"name": f, "path": filepath, "size": size, "dir": root})
                    except: pass
                    
    return {"results": results[:100]} # 최대 100개 제한
