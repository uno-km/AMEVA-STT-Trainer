import sys
import os
import random
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.backend.core.database import db_manager
from src.backend.core.reporter import report_generator

def run_syuka_test():
    print("[TEST] Syuka World Test Data (10 Steps) Injection and Report Generation Started...")
    
    # 1. 태스크 생성
    task_id = db_manager.create_task("Syuka_Speed_Test_Result")
    print(f"[+] Task Created: {task_id}")
    
    # 폴더 구조 생성
    base_dir = r"c:\ameva\AMEVA-STT-Trainer"
    task_folder = os.path.join(base_dir, "dataset", f"Syuka_Speed_Test_Result_{task_id[:8]}")
    os.makedirs(task_folder, exist_ok=True)
    
    # 메타데이터 및 청크 모의 데이터 추가
    meta_id = db_manager.create_metadata(task_id, "슈카월드_경제동향_2026.mp4", task_folder)
    db_manager.create_chunk(meta_id, "chunk_001.wav", os.path.join(task_folder, "chunk_001.wav"), "미국 금리가 인상되면서...")
    db_manager.create_chunk(meta_id, "chunk_002.wav", os.path.join(task_folder, "chunk_002.wav"), "환율 변동폭이 커지고 있습니다.")
    
    # 2. 워크플로우 내역 생성
    db_manager.add_task_dtl(task_id, 2, "Training", '{"action": "start_training", "max_steps": 10}', next_step=3)
    db_manager.add_task_dtl(task_id, 3, "Export/Quantize", '{"action": "export_model", "method": "q4_0"}', next_step=None)
    
    # 3. 10스텝 메트릭 데이터 삽입 (차트용)
    print("[+] Generating 10-step metrics (Loss, Accuracy, CPU)...")
    loss = 2.5
    acc = 0.4
    for step in range(1, 11):
        loss = max(0.2, loss - random.uniform(0.1, 0.3))
        acc = min(0.95, acc + random.uniform(0.02, 0.08))
        cpu = random.uniform(30.0, 85.0)
        speed = random.uniform(15.0, 22.0)
        db_manager.add_metric(task_id, step, loss, acc, cpu, speed)
        
    # 4. 로그 추가
    db_manager.add_log("INFO", "학습 파이프라인 초기화 완료 (10 Steps)", task_id)
    db_manager.add_log("INFO", "데이터셋 로드 완료: 슈카월드_경제동향_2026.mp4", task_id)
    db_manager.add_log("WARNING", "일부 오디오 구간에 노이즈가 감지되어 건너뜁니다.", task_id)
    db_manager.add_log("INFO", "Step 10/10 완료 (Loss: 0.25, Acc: 0.92)", task_id)
    db_manager.add_log("INFO", "GGUF 변환 및 q4_0 양자화 완료", task_id)
    
    # 5. 상태 업데이트 (Level 3 SUCCESS) 및 가상 모델 경로 설정
    model_path = r"c:\ameva\AI_Models\ggml\ggml-syuka-tiny-q4_0.bin"
    db_manager.update_task_status(task_id, level=3, status="SUCCESS", log_msg="All steps completed.", model_path=model_path)
    
    # 6. 대망의 워드 리포트 생성
    print("[+] Generating Final Word Report with Charts...")
    report_path = report_generator.generate_task_report(task_id)
    
    print(f"[+] All tasks completed! Report Path: {report_path}")
    print("[+] Please restart the dashboard and check the 'Load Past Records' section.")

if __name__ == "__main__":
    run_syuka_test()
