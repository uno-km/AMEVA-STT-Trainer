"""
scripts/03_export_model.py
[단계 3] LoRA 어댑터 병합 + GGUF 변환 가이드 출력 엔트리 포인트.

실행 순서:
  1. LoRA 어댑터를 베이스 모델에 병합 -> outputs/merged_model/ 저장
  2. GGUF 변환 절차 출력 (whisper.cpp 빌드 환경 필요)
  3. 변환된 GGUF를 C:\ameva\models\stt\created 에 복사하는 명령 안내
"""
import sys
import os
import io

# 윈도우 터미널 한글 깨짐 방지
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import shutil
import subprocess

# 프로젝트 루트 디렉터리를 Python 경로에 등록하여 src 모듈을 불러올 수 있도록 설정
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.whisper_lora import merge_and_save
from src.core.config         import MERGED_DIR, GGUF_DIR, LORA_DIR
from src.utils               import logger
from rich.panel              import Panel
from rich.table              import Table
from rich.console            import Group


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Whisper LoRA Merge & Quantization Tool")
    parser.add_argument("--no-quantize", action="store_true", help="양자화 단계를 건너뛰고 원본 FP 모델만 생성합니다.")
    parser.add_argument("--only-quantize", action="store_true", help="병합 단계를 건너뛰고 기존 바이너리에 대한 양자화만 수행합니다.")
    parser.add_argument("--method", type=str, default="q4_0", help="양자화 방식 (기본값: q4_0)")
    parser.add_argument("--task-id", type=str, help="태스크 ID (DB 연동용)")
    args = parser.parse_args()

    if args.task_id:
        os.environ["CURRENT_TASK_ID"] = args.task_id

    try:
        print("\n" + "=" * 50)
        print("[3단계] 모델 내보내기 및 최적화 공정 시작")
        print("=" * 50)

        from src.models.quantizer import WhisperQuantizer
        whisper_cpp_dir = os.path.join(os.path.dirname(__file__), "..", "third_party", "whisper.cpp")
        quantizer = WhisperQuantizer(whisper_cpp_dir=whisper_cpp_dir)
        
        model_name_prefix = "shuka-tiny"
        task_id = os.environ.get("CURRENT_TASK_ID")
        if task_id:
            try:
                from src.backend.core.database import db_manager
                import json
                task_details = db_manager.get_task_details(task_id)
                if task_details and 'details' in task_details:
                    for dtl in task_details['details']:
                        if dtl.get('step_seq') == 2:  # Training step
                            params = json.loads(dtl.get('parameters', '{}'))
                            model_id = params.get('model_id', '')
                            if model_id:
                                base_name = model_id.split('/')[-1]
                                model_name_prefix = f"shuka-{base_name}"
                                break
            except Exception as ex:
                print(f"[*] 태스크 정보에서 모델명을 가져오지 못해 기본값(shuka-tiny)을 적용합니다: {ex}")
        
        final_model_name = f"ggml-{model_name_prefix}-{args.method}.bin"
        merged_path = MERGED_DIR

        # ---- 단독 양자화(후처리) 모드 ----
        if args.only_quantize:
            print("[*] 단독 후처리 모드: 기존 GGML 바이너리를 양자화합니다.")
            source_bin = "ggml-model.bin" # 기본 생성 이름
            final_bin = quantizer.quantize_existing_bin(source_bin, final_model_name, method=args.method)
        
        else:
            # ---- 1단계: LoRA 가중치 병합 ----
            print("[*] 모델 병합 중: LoRA 어댑터와 베이스 모델을 합치는 중...")
            if not os.path.exists(LORA_DIR):
                print(f"❌ [Error] LoRA 어댑터 없음: {LORA_DIR}")
                return
            
            merged_path = merge_and_save()
            print(f"✅ 병합 완료: {merged_path}")

            # ---- 2단계: 후처리 (GGUF 변환 및 선택적 양자화) ----
            print(f"[*] 후처리 시작: GGUF 변환 및 {'양자화' if not args.no_quantize else '원본 배포'}...")
            output_path = quantizer.run_post_process(merged_path, final_model_name, skip_quantize=args.no_quantize)
        
        # ---- 3단계: 최종 모델 배포 ----
        print("[*] 배포 중: 에이전트 모델 폴더로 이동 중...")
        
        if output_path and os.path.exists(output_path):
            os.makedirs(GGUF_DIR, exist_ok=True)
            final_dest = os.path.join(GGUF_DIR, os.path.basename(output_path))
            
            if os.path.exists(final_dest):
                os.remove(final_dest)
            shutil.move(output_path, final_dest)
            
            print("\n" + "="*50)
            print("🎉 [SUCCESS] 도메인 특화 STT 모델 탄생!")
            print(f"📍 위치: {final_dest}")
            print("🚀 AMEVA-STT-Agent에서 '기타 모델 선택'으로 불러오세요.")
            print("="*50 + "\n")
            
            # DB 업데이트 (Level 3: 최적화 및 배포 완료)
            task_id = os.environ.get("CURRENT_TASK_ID")
            if task_id:
                from src.backend.core.database import db_manager
                db_manager.update_task_status(task_id, level=3, status="SUCCESS", 
                                            log_msg=f"Step 3 (Export) completed. Model saved at {final_dest}",
                                            model_path=final_dest)
                print(f"Task {task_id} status updated to Level 3 SUCCESS.")
        else:
            print("❌ [Error] 최종 모델 파일이 생성되지 않았습니다.")
            task_id = os.environ.get("CURRENT_TASK_ID")
            if task_id:
                from src.backend.core.database import db_manager
                db_manager.update_task_status(task_id, level=3, status="FAILED", log_msg="Step 3 (Export) failed: Output file missing.")
            return

    except Exception as e:
        print("\n" + "!"*60)
        print(f"❌ [CRITICAL ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        print("!"*60 + "\n")

    except Exception as e:
        # 대시보드가 켜져있다면 끄고 에러 출력
        logger.stop_dashboard()
        print("\n" + "!"*60)
        print(f"❌ [CRITICAL ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        print("!"*60 + "\n")


if __name__ == "__main__":
    # 메인 실행부 호출
    main()
