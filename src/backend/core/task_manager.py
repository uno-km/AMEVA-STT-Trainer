import os
import json
import subprocess
from src.backend.core.database import db_manager
from src.utils import logger

class TaskManager:
    """
    SQLite DB(db_manager)를 기반으로 태스크 생명주기와 
    시퀀셜 워크플로우(Next Step)를 관리하는 엔진.
    """
    def __init__(self):
        self.base_dir = r"c:\ameva\AMEVA-STT-Trainer"

    def init_data(self, name, source_type="youtube", url="", count=5, folder=""):
        """[1단계] 태스크를 생성하고 데이터 전처리 스크립트를 독립적으로 가동합니다."""
        task_id = db_manager.create_task(name)
        db_manager.update_task_status(task_id, 1, "RUNNING", "Step 1: Data Preparation starting...")
        
        task_folder = os.path.join(self.base_dir, "dataset", f"{name}_{task_id[:8]}")
        os.makedirs(task_folder, exist_ok=True)
        
        data_params = json.dumps({
            "action": "build_dataset", 
            "source_type": source_type, 
            "url": url, 
            "count": count, 
            "folder": folder
        })
        # 1단계 상세 정보 기록 (다음 단계는 유저가 버튼을 누를 때까지 보류)
        db_manager.add_task_dtl(task_id, step_seq=1, step_name="Data Prep", parameters=data_params, next_step=None)
        
        self._run_data_script(task_id, json.loads(data_params))
        return {"id": task_id, "name": name, "path": task_folder}

    def start_train(self, task_id, max_steps=100, auto_export=True, method="q4_0"):
        """[2단계] 1단계가 완료된 태스크에 대해 학습 파라미터를 입력받고 2-3단계 체인을 가동합니다."""
        train_params = json.dumps({"action": "start_training", "max_steps": max_steps})
        next_after_train = 3 if auto_export else None
        
        db_manager.add_task_dtl(task_id, step_seq=2, step_name="Training", parameters=train_params, next_step=next_after_train)
        
        if auto_export:
            export_params = json.dumps({"action": "export_model", "method": method})
            db_manager.add_task_dtl(task_id, step_seq=3, step_name="Export/Quantize", parameters=export_params, next_step=None)
            
        db_manager.update_task_status(task_id, 2, "RUNNING", "Step 2: Training starting...")
        self._run_training_script(task_id, json.loads(train_params))
        return {"id": task_id, "status": "Training Started"}

    def trigger_next_step(self, task_id):
        """현재 태스크의 다음 단계가 있는지 확인하고 실행합니다."""
        task_details = db_manager.get_task_details(task_id)
        if not task_details: return
        
        current_level = task_details['level']
        details = task_details.get('details', [])
        
        next_step_id = None
        for dtl in details:
            if dtl['step_seq'] == current_level:
                next_step_id = dtl['next_step']
                break
        
        if not next_step_id:
            logger.info(f"Task {task_id}: 다음 공정이 없습니다. 대기 또는 종료.")
            return

        next_dtl = next((d for d in details if d['step_seq'] == next_step_id), None)
        if next_dtl:
            step_name = next_dtl['step_name']
            params = json.loads(next_dtl['parameters'])
            logger.info(f"🚀 Task {task_id}: 다음 공정 [{step_name}] 자동 시작!")
            
            if params.get("action") == "start_training":
                self._run_training_script(task_id, params)
            elif params.get("action") == "export_model":
                self._run_export_script(task_id, params)

    def _run_data_script(self, task_id, params):
        """01_build_dataset.py를 서브프로세스로 실행"""
        cmd = [
            "python", "scripts/01_build_dataset.py",
            "--task-id", task_id,
            "--source_type", params.get("source_type", "youtube"),
            "--url", params.get("url", ""),
            "--count", str(params.get("count", 5)),
            "--folder", params.get("folder", "")
        ]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        subprocess.Popen(cmd, env=env, cwd=self.base_dir)

    def _run_training_script(self, task_id, params):
        """02_start_training.py를 서브프로세스로 실행"""
        cmd = [
            "python", "scripts/02_start_training.py",
            "--skip" 
        ]
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["TRAIN_MAX_STEPS"] = str(params.get("max_steps", 10))
        env["CURRENT_TASK_ID"] = task_id
        
        subprocess.Popen(cmd, env=env, cwd=self.base_dir)

    def _run_export_script(self, task_id, params):
        """03_export_model.py를 서브프로세스로 실행"""
        cmd = [
            "python", "scripts/03_export_model.py",
            "--method", params.get("method", "q4_0")
        ]
        if params.get("no_quantize"):
            cmd.append("--no-quantize")
            
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["CURRENT_TASK_ID"] = task_id
        
        subprocess.Popen(cmd, env=env, cwd=self.base_dir)

task_manager = TaskManager()
