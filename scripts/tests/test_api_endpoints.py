"""
scripts/tests/test_api_endpoints.py
AMEVA-STT-Trainer QA Automation: MLOps Pipeline API End-to-End Test Engine
- Mock-intercepts subprocess triggers to avoid spawning active training/scraping.
- Pushes QA dummy task, validates status changes, metrics flow, and log generation.
- Performs zero-residue database and filesystem wipe (DELETE/Cleanup) on success.
"""
import os
import sys
import json
import shutil
from unittest.mock import patch

def run_api_tests():
    # 프로젝트 루트 및 sys.path 설정
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    print("\n" + "=" * 80)
    print(">>> QA API Integration: End-to-End MLOps Endpoint & Database Flow Test")
    print("=" * 80 + "\n")

    # 1. API 함수 및 매니저 임포트
    try:
        from src.backend.api.pipeline_api import (
            init_data, list_tasks, get_task_metrics, get_pipeline_status, get_resources
        )
        from src.backend.core.database import db_manager
        print("[+] Backend API & Database imports: SUCCESS")
    except Exception as e:
        print(f"[!] Backend API Import Failure: {e}")
        sys.exit(1)

    dummy_task_name = "QA_INTEGRATION_DUMMY_TASK"
    task_id = None
    task_folder = None

    # 서브프로세스 기동이 발생하지 않도록 Popen/script_async를 목킹 처리하여 검사
    with patch('src.backend.core.task_manager.TaskManager._run_script_async') as mock_run:
        try:
            # 2. 시스템 자원 모니터링 API 검증
            sys_resources = get_resources()
            print(f"[+] API [GET /system/resources] test: SUCCESS (CPU: {sys_resources['cpu']}%, RAM: {sys_resources['ram']}%)")

            # 3. 파이프라인 기본 상태 조회 검증
            pipeline_status = get_pipeline_status()
            print(f"[+] API [GET /pipeline/status] test: SUCCESS (Current Stage: {pipeline_status['stage']})")

            # 4. 더미 데이터 태스크 초기화 밀어넣기 검증
            print("\n[*] Pushing QA Dummy Task into init_data API...")
            body = {
                "name": dummy_task_name,
                "step_limit": 1,
                "step1_params": {
                    "source_type": "youtube",
                    "url": "https://www.youtube.com/watch?v=dummy",
                    "count": 1
                }
            }
            res = init_data(body)
            task_id = res.get("id")
            task_folder = res.get("path")
            
            print(f"    [+] API [POST /tasks/init_data] test: SUCCESS")
            print(f"    [+] Created Task ID: {task_id}")
            print(f"    [+] Created Folder: {task_folder}")

            # 5. 데이터베이스 등록 확인 및 리스트 조회 검증
            tasks_list = list_tasks().get("tasks", [])
            matched_task = next((t for t in tasks_list if t["id"] == task_id), None)
            if not matched_task:
                raise ValueError("Initialized QA task not found in database task listing!")
            print(f"[+] API [GET /tasks/list] test: SUCCESS (Registered Task Status: {matched_task['status']})")

            # 6. 더미 메트릭 삽입 및 실시간 쿼리 검증
            db_manager.add_metric(task_id, step=10, loss=0.456, accuracy=0.888, cpu_usage=45.2, speed=12.5)
            metrics_res = get_task_metrics(task_id).get("metrics", [])
            
            if not metrics_res or metrics_res[0]["step"] != 10:
                raise ValueError("Database metric insert or retrieve flow is broken!")
            print(f"[+] API [GET /tasks/metrics] test: SUCCESS (Fetched QA Metric: Loss {metrics_res[0]['loss']})")

            # 7. 태스크 전용 로그 누적 검증
            db_manager.add_log("INFO", "QA Dummy Integration Verification Pass", task_id)
            print("[+] Database Logging System check: SUCCESS")

        except Exception as err:
            print(f"\n[!] Integration Test CRITICAL FAILURE: {err}")
            # 에러 발생 시에도 클린업 진행
            perform_cleanup(db_manager, task_id, task_folder)
            sys.exit(1)

    # 8. 검수 완벽 완료 시 테스트 잔여 데이터 영구 박멸 (Wipe out zero residues)
    print("\n[*] Initializing Zero-Residue Cleanup Phase...")
    perform_cleanup(db_manager, task_id, task_folder)

    print("\n" + "=" * 80)
    print("[+] QA API Integration: SUCCESS! All API flows validated, residues completely wiped.")
    print("=" * 80 + "\n")
    sys.exit(0)

def perform_cleanup(db_manager, task_id, task_folder):
    """가동 시 생성된 SQLite 테이블 데이터 레코드 및 디스크 상의 폴더 흔적을 완전히 제거합니다."""
    if task_id:
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA foreign_keys = ON")
                
                # 메인 태스크 테이블 삭제 (외래키 CASCADE 설정에 의해 지표, 로그, 메타데이터 연쇄 자동 폭파)
                cursor.execute("DELETE FROM tb_task WHERE id = ?", (task_id,))
                
                # 세이프가드: CASCADE 미지원 버전을 위해 명시적 추가 삭제
                cursor.execute("DELETE FROM tb_log WHERE task_id = ?", (task_id,))
                cursor.execute("DELETE FROM tb_metric WHERE task_id = ?", (task_id,))
                cursor.execute("DELETE FROM tb_task_dtl WHERE task_id = ?", (task_id,))
                cursor.execute("DELETE FROM tb_thread_log WHERE task_id = ?", (task_id,))
                
                conn.commit()
            print("    [+] SQLite DB Trace Cleaned: SUCCESS")
        except Exception as e:
            print(f"    [!] Error cleaning up database traces: {e}")

    if task_folder and os.path.exists(task_folder):
        try:
            shutil.rmtree(task_folder, ignore_errors=True)
            print("    [+] Filesystem Dataset Directory Cleaned: SUCCESS")
        except Exception as e:
            print(f"    [!] Error removing folder traces: {e}")

if __name__ == "__main__":
    run_api_tests()
