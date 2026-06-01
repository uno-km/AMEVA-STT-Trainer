"""
scripts/run_syuka_300_pipeline_sync.py
[구글 코랩 / CLI 동기식 실행 전용] 
300개 슈카월드 유튜브 비디오를 수집하여 데이터셋 구축부터 GPU 학습까지 
포그라운드(실시간 로그 출력)에서 순차 실행하는 마스터 스크립트.
"""
import os
import sys
import json
import subprocess

# 프로젝트 루트를 Python 경로에 등록
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.backend.core.database import db_manager
from src.utils import logger

def run_command_sync(cmd, task_id, step_seq, step_name):
    """지정한 명령어를 동기식으로 실행하며 모든 출력을 화면에 실시간 노출하고 DB 상태를 갱신합니다."""
    logger.info(f"\n==================================================")
    logger.info(f"▶ [{step_seq}단계: {step_name}] 실행 시작")
    logger.info(f"Command: {' '.join(cmd)}")
    logger.info(f"==================================================\n")
    
    # DB 상태를 RUNNING으로 세팅
    db_manager.update_task_status(task_id, step_seq, "RUNNING", f"{step_name} 실행 중...")
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["CURRENT_TASK_ID"] = task_id
    
    try:
        # 실시간 로그 출력을 위해 subprocess.run 이용 (stdout, stderr를 터미널로 다이렉트 통과)
        result = subprocess.run(
            cmd,
            env=env,
            check=True
        )
        
        # 완료 시 DB 상태 갱신
        db_manager.update_task_status(task_id, step_seq, "SUCCESS", f"{step_name} 완료")
        logger.info(f"\n✅ [{step_seq}단계: {step_name}] 무사히 완료되었습니다!\n")
        return True
    except subprocess.CalledProcessError as e:
        db_manager.update_task_status(task_id, step_seq, "FAILED", f"{step_name} 실패 (Exit Code {e.returncode})")
        logger.error(f"\n❌ [{step_seq}단계: {step_name}] 실행 중 에러가 발생했습니다. (Exit Code {e.returncode})\n")
        return False

def main():
    # 1. 고정 학습 설정값 정의 (슈카월드 300개 영상 특화)
    task_name = "syuka_300_project"
    step_limit = 3  # 1단계(수집/전처리) -> 2단계(GPU 학습) -> 3단계(모델 양자화 내보내기)
    
    step1_params = {
        "source_type": "youtube",
        "url": "https://www.youtube.com/@syukaworld/videos",
        "count": 300
    }
    
    step2_params = {
        "action": "start_training",
        "model_id": "openai/whisper-small",  # 베이스 모델 지정
        "max_steps": 2000,
        "learning_rate": "1e-05",            # 학습률 (0.00001)
        "batch_size": 2,                     # 배치 사이즈
        "gradient_accumulation": 8           # 그래디언트 누적 수
    }
    
    step3_params = {
        "action": "export_model",
        "auto_export": True,
        "method": "q4_0"                     # q4_0 양자화 모델로 내보내기
    }
    
    # 2. SQLite 데이터베이스에 태스크 등록
    logger.info("📡 데이터베이스에 슈카월드 300개 프로젝트 태스크 등록 중...")
    task_id = db_manager.create_task(task_name)
    
    # 데이터셋 폴더 생성 규칙 적용
    task_folder = os.path.abspath(os.path.join("dataset", f"{task_name}_{task_id[:8]}"))
    os.makedirs(task_folder, exist_ok=True)
    step1_params["output_dir"] = task_folder
    step1_params["name"] = f"{task_name}_{task_id[:8]}"
    
    # 세부 단계(dtl) DB 등록
    db_manager.add_task_dtl(task_id, step_seq=1, step_name="Data Prep", parameters=json.dumps(step1_params), next_step=2)
    db_manager.add_task_dtl(task_id, step_seq=2, step_name="Training", parameters=json.dumps(step2_params), next_step=3)
    db_manager.add_task_dtl(task_id, step_seq=3, step_name="Export", parameters=json.dumps(step3_params), next_step=None)
    
    logger.info(f"✅ 태스크 등록 완료! Task ID: {task_id}")
    logger.info(f"📁 데이터 폴더 생성: {task_folder}\n")
    
    # 3. [1단계] 데이터셋 구축 실행 (동기식)
    cmd_step1 = [
        sys.executable, "scripts/01_build_dataset.py",
        "--source_type", "youtube",
        "--url", step1_params["url"],
        "--count", str(step1_params["count"]),
        "--name", step1_params["name"]
    ]
    if not run_command_sync(cmd_step1, task_id, 1, "Data Prep"):
        sys.exit(1)
        
    # 4. [2단계] Whisper LoRA GPU 학습 실행 (동기식)
    cmd_step2 = [
        sys.executable, "scripts/02_start_training.py",
        "--task-id", task_id,
        "--skip"
    ]
    if not run_command_sync(cmd_step2, task_id, 2, "Training"):
        sys.exit(1)
        
    # 5. [3단계] 최종 모델 병합 및 GGUF 변환 실행 (동기식, 만약 스크립트가 있다면)
    # (참고: 프로젝트의 3단계 모델 배포 파일이 존재하면 실행합니다)
    export_script = "scripts/03_export_model.py"
    if os.path.exists(export_script):
        cmd_step3 = [
            sys.executable, export_script,
            "--task-id", task_id
        ]
        run_command_sync(cmd_step3, task_id, 3, "Export")
    else:
        logger.info("[INFO] scripts/03_export_model.py 파일이 없어 3단계를 생략하고 완료합니다.")

    # 메인 태스크 상태 성공 갱신
    with db_manager.get_connection() as conn:
        conn.execute("UPDATE tb_task SET status='SUCCESS' WHERE id=?", (task_id,))
    logger.info(f"🎉 모든 파이프라인 학습 과정이 끝났습니다! Task ID: {task_id}")

if __name__ == "__main__":
    main()
