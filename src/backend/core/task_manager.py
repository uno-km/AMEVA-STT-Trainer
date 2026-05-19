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
        # 현재 파일 위치(src/backend/core/task_manager.py) 기준 3단계 상위 폴더를 루트로 동적 계산
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.active_processes = {} # 실행 중인 프로세스 추적용

    def init_data(self, name, step_limit=1, step1_params=None, step2_params=None, step3_params=None):
        """[1단계] 태스크를 생성하고, 사용자의 체이닝 설계에 따라 1/2/3단계 파라미터를 분할 저장합니다."""
        step1_params = step1_params or {}
        
        task_id = db_manager.create_task(name)
        db_manager.update_task_status(task_id, 1, "RUNNING", "Step 1: Data Preparation starting...")
        
        # [쓰레드 설정 실시간 기록] 초기 할당된 쓰레드 정보 DB 저장
        try:
            from src.backend.hardware.resource_manager import hw_manager
            db_manager.add_thread_log(task_id, hw_manager.allocated_cores)
        except Exception as e:
            print(f"[Initial Thread Log Error] {e}")
        
        task_folder = os.path.join(self.base_dir, "dataset", f"{name}_{task_id[:8]}")
        os.makedirs(task_folder, exist_ok=True)
        
        # 1단계 설정 (2단계까지 원했다면 next_step=2)
        s1_params = step1_params.copy()
        s1_params["output_dir"] = task_folder
        s1_params["name"] = f"{name}_{task_id[:8]}"
        next_step1 = 2 if step_limit >= 2 else None
        db_manager.add_task_dtl(task_id, step_seq=1, step_name="Data Prep", parameters=json.dumps(s1_params), next_step=next_step1)
        
        # 2단계 체이닝 설정
        if step_limit >= 2 and step2_params:
            next_step2 = 3 if step_limit == 3 else None
            db_manager.add_task_dtl(task_id, step_seq=2, step_name="Training", parameters=json.dumps(step2_params), next_step=next_step2)
            
        # 3단계 체이닝 설정
        if step_limit == 3 and step3_params:
            db_manager.add_task_dtl(task_id, step_seq=3, step_name="Export", parameters=json.dumps(step3_params), next_step=None)
            
        import sys
        cmd = [sys.executable, "scripts/01_build_dataset.py"]
        source_type = s1_params.get("source_type", "youtube")
        if source_type == "youtube": 
            cmd.extend(["--source_type", "youtube", "--url", s1_params.get("url", ""), "--count", str(s1_params.get("count", 5))])
        else: 
            cmd.extend(["--source_type", "local", "--folder", s1_params.get("folder", "")])
        cmd.extend(["--name", f"{name}_{task_id[:8]}"])
        
        self._run_script_async(cmd, task_id, level=1)
        return {"id": task_id, "name": name, "path": task_folder}

    def start_train(self, task_id: str, step_limit=2, step2_params=None, step3_params=None):
        """[2단계] 이어하기 시작. 2단계 및 3단계 파라미터를 tb_task_dtl에 연쇄 저장합니다."""
        from src.backend.core.database import db_manager
        
        # [쓰레드 설정 실시간 기록] 초기 할당된 쓰레드 정보 DB 저장
        try:
            from src.backend.hardware.resource_manager import hw_manager
            db_manager.add_thread_log(task_id, hw_manager.allocated_cores)
        except Exception as e:
            print(f"[Initial Thread Log Error] {e}")
            
        # 2단계 정보 갱신
        if step2_params:
            next_step2 = 3 if step_limit == 3 else None
            db_manager.add_task_dtl(task_id, step_seq=2, step_name="Training", parameters=json.dumps(step2_params), next_step=next_step2)
            
        # 3단계 정보 갱신
        if step_limit == 3 and step3_params:
            db_manager.add_task_dtl(task_id, step_seq=3, step_name="Export", parameters=json.dumps(step3_params), next_step=None)
            
        # [해결] 이미 2단계 학습에 진입했었던 이력이 있고(level >= 2), 사용자가 3단계(내보내기) 실행을 지시한 경우 (성공/중단 여부 무관)
        task = db_manager.get_task_details(task_id)
        current_level = task.get('level', 1) if task else 1
        
        is_step2_attempted = (current_level >= 2)
        
        if is_step2_attempted and step_limit == 3:
            db_manager.update_task_status(task_id, 3, "RUNNING", "Step 3: Export/Quantization starting...")
            self._run_export_script(task_id, step3_params or {})
            return {"id": task_id, "status": "Export Started"}
            
        # 기본값: 2단계 학습 가동 (이어하기의 경우 최근 체크포인트 자동 반영됨)
        db_manager.update_task_status(task_id, 2, "RUNNING", "Step 2: Training starting...")
        self._run_training_script(task_id, step2_params or {})
        return {"id": task_id, "status": "Training Started"}

    def _run_script_async(self, cmd, task_id, level=2):
        """서브프로세스를 실행하고 로그를 수동으로 기록 (시동 실패 방어 로직 강화)"""
        log_dir = os.path.join(self.base_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, f"task_{task_id}.log")
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        env["CURRENT_TASK_ID"] = task_id
        # 태스크 관련 메타데이터나 특정 정보를 환경변수로 추가 전달 가능

        try:
            with open(log_file_path, "w", encoding="utf-8") as f:
                f.write(f"--- [AMEVA Engine] {cmd[1]} 초기화 중... ---\n")
                f.write(f"Command: {' '.join(cmd)}\n\n")
                f.flush()
        except Exception as e:
            logger.error(f"로그 파일 초기 생성 실패: {e}")

        def target():
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                    cwd=self.base_dir,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                self.active_processes[task_id] = process

                with open(log_file_path, "a", encoding="utf-8") as f:
                    f.write(f"--- [AMEVA Engine] 서브프로세스 PID: {process.pid} 가동 시작 ---\n")
                    f.flush()
                    
                    # DB에도 가동 시작 기록 강박적 보존
                    from src.backend.core.database import db_manager
                    db_manager.add_log("INFO", f"--- [AMEVA Engine] 서브프로세스 PID: {process.pid} 가동 시작 ---", task_id)
                    
                    for line in process.stdout:
                        f.write(line)
                        f.flush()
                        
                        # [로그발생 -> 로그출력 -> 저장] 철벽 실시간 파이프라인 주입!
                        stripped = line.strip()
                        if stripped:
                            # 내부 로거(_write_to_db)가 이미 직접 DB에 기록한 중복 로그(INFO, WARNING, ERROR, SUCCESS 시작)는 DB 삽입 제외
                            is_dup = any(stripped.startswith(prefix) for prefix in ["INFO ", "WARNING ", "ERROR ", "SUCCESS "])
                            if not is_dup:
                                db_manager.add_log("INFO", stripped, task_id)
                            
                    process.wait()
                    
                    # 종료 상태 DB 반영 및 순수 DB 기반 Auto-Chaining
                    from src.backend.core.database import db_manager
                    
                    if process.returncode == 0:
                        db_manager.update_task_status(task_id, level, "SUCCESS", f"Exit Code: 0")
                        
                        # DB의 tb_task_dtl(next_step)을 조회하여 연쇄 가동 실행
                        self.trigger_next_step(task_id)
                                    
                    else:
                        checkpoint = self._find_latest_checkpoint(task_id) if level == 2 else None
                        db_manager.update_task_status(task_id, level, "FAILED", f"Exit Code: {process.returncode}", checkpoint_path=checkpoint)
                        if checkpoint:
                            f.write(f"\n--- [AMEVA Engine] 치명적 오류. 최신 체크포인트 보존됨: {checkpoint} ---\n")
                        else:
                            f.write(f"\n--- [AMEVA Engine] 공정 실패 (Exit Code: {process.returncode}) ---\n")
                            
            except Exception as e:
                import traceback
                with open(log_file_path, "a", encoding="utf-8") as f:
                    f.write(f"\n[FATAL ERROR] 서브프로세스 기동 중 치명적 오류: {str(e)}\n")
                    f.write(f"상세 정보: {traceback.format_exc()}\n")
                from src.backend.core.database import db_manager
                checkpoint = self._find_latest_checkpoint(task_id) if level == 2 else None
                db_manager.update_task_status(task_id, level, "FAILED", f"Error: {str(e)}", checkpoint_path=checkpoint)
            finally:
                if task_id in self.active_processes:
                    del self.active_processes[task_id]
        
        import threading, sys
        thread = threading.Thread(target=target, daemon=True)
        thread.start()

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
            
            # DB 상태를 다음 단계로 격상
            db_manager.update_task_status(task_id, next_step_id, "RUNNING", f"Step {next_step_id}: {step_name} starting (Auto-Chained)")
            
            if next_step_id == 1:
                self._run_data_script(task_id, params)
            elif next_step_id == 2:
                self._run_training_script(task_id, params)
            elif next_step_id == 3:
                self._run_export_script(task_id, params)

    def _run_data_script(self, task_id, params):
        import sys
        cmd = [
            sys.executable, "scripts/01_build_dataset.py",
            "--task-id", task_id,
            "--source_type", params.get("source_type", "youtube"),
            "--url", params.get("url", ""),
            "--count", str(params.get("count", 5)),
            "--folder", params.get("folder", "")
        ]
        # [버그 방어] 1단계 가동 시 명확히 level=1 명시
        self._run_script_async(cmd, task_id, level=1)

    def _run_training_script(self, task_id, params):
        import sys
        from src.backend.core.database import db_manager
        
        cmd = [
            sys.executable, "scripts/02_start_training.py",
            "--task-id", task_id,
            "--skip" 
        ]
        
        # [핵심] 이어하기: DB에 체크포인트가 보존되어 있다면 인자로 넘겨서 이어서 학습!
        task = db_manager.get_task_details(task_id)
        if task and task.get('checkpoint_path'):
            ckpt_path = task['checkpoint_path']
            if os.path.exists(ckpt_path):
                cmd.extend(["--resume_from_checkpoint", ckpt_path])
                
        self._run_script_async(cmd, task_id, level=2)

    def _run_export_script(self, task_id, params):
        import sys
        cmd = [
            sys.executable, "scripts/03_export_model.py",
            "--method", params.get("method", "q4_0")
        ]
        if params.get("no_quantize"):
            cmd.append("--no-quantize")
        # [무한 루프 버그 완전 해결] 3단계 가동 시 명확히 level=3 명시!
        self._run_script_async(cmd, task_id, level=3)

    def force_stop_task(self, task_id: str):
        """실행 중인 프로세스를 강제 종료하고 상태를 업데이트합니다."""
        process = self.active_processes.get(task_id)
        if not process:
            return {"status": "Error", "message": "해당 태스크의 실행 중인 프로세스를 찾을 수 없습니다."}
            
        try:
            import psutil
            parent = psutil.Process(process.pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
            
            # 마지막 체크포인트 경로 찾아서 DB에 기록 (이어하기 용)
            task = db_manager.get_task_details(task_id)
            tsk_nm = task.get('tsk_nm', 'task')
            lora_dir = os.path.join(self.base_dir, "outputs", f"{tsk_nm}_{task_id[:8]}")
            
            latest_ckpt = None
            if os.path.exists(lora_dir):
                ckpts = [d for d in os.listdir(lora_dir) if d.startswith("checkpoint-")]
                if ckpts:
                    latest = sorted(ckpts, key=lambda x: int(x.split("-")[-1]))[-1]
                    latest_ckpt = os.path.join(lora_dir, latest)
            
            db_manager.update_task_status(task_id, task.get('level', 1), "FAILED", 
                                       log_msg="사용자에 의해 강제 종료되었습니다.",
                                       checkpoint_path=latest_ckpt)
            
            if task_id in self.active_processes:
                del self.active_processes[task_id]
                
            return {"status": "Killed", "task_id": task_id, "checkpoint": latest_ckpt}
        except Exception as e:
            return {"status": "Error", "message": str(e)}

    def get_task_logs(self, task_id: str) -> str:
        """특정 태스크의 로그 파일 내용을 읽어옵니다."""
        log_file_path = os.path.join(self.base_dir, "logs", f"task_{task_id}.log")
        if not os.path.exists(log_file_path):
            return f"로그 파일이 없습니다: {log_file_path}"
        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                # 마지막 200줄만 반환하여 과부하 방지
                lines = f.readlines()
                return "".join(lines[-200:])
        except Exception as e:
            return f"로그 읽기 오류: {str(e)}"

    def _find_latest_checkpoint(self, task_id: str) -> str:
        """태스크 폴더에서 가장 최근 생성된 LoRA 체크포인트 폴더 경로를 반환합니다."""
        if not task_id: return None
        try:
            task = db_manager.get_task_details(task_id)
            if not task: return None
            tsk_nm = task.get('tsk_nm', 'task')
            lora_dir = os.path.join(self.base_dir, "outputs", f"{tsk_nm}_{task_id[:8]}")
            if os.path.exists(lora_dir):
                ckpts = [d for d in os.listdir(lora_dir) if d.startswith("checkpoint-")]
                if ckpts:
                    latest = sorted(ckpts, key=lambda x: int(x.split("-")[-1]))[-1]
                    return os.path.join(lora_dir, latest)
        except Exception as e:
            logger.error(f"체크포인트 탐색 오류: {e}")
        return None

task_manager = TaskManager()
