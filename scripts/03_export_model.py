"""
scripts/03_export_model.py
[단계 3] LoRA 어댑터 병합 + GGUF 변환 가이드 출력 엔트리 포인트.

실행 순서:
  1. LoRA 어댑터를 베이스 모델에 병합 -> outputs/merged_model/ 저장
  2. GGUF 변환 절차 출력 (whisper.cpp 빌드 환경 필요)
  3. 변환된 GGUF를 C:\\ameva\\AI_Models\\ggml\\ 에 복사하는 명령 안내
"""
import sys
import os
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
    try:
        print("\n" + "=" * 50)
        print("[3단계] 모델 내보내기 및 병합 시작")
        print("=" * 50)

        # ---- 1단계: LoRA 가중치 병합 ----
        print("[*] 모델 병합 중: LoRA 어댑터와 베이스 모델을 합치는 중...")
        
        if not os.path.exists(LORA_DIR):
            print(f"❌ [Error] LoRA 어댑터 없음: {LORA_DIR}")
            return

        # 실제 병합 로직 실행
        merged_path = merge_and_save()
        print(f"✅ 병합 완료: {merged_path}")

        # ---- 2단계: 변환 도구(whisper.cpp) 자가 진단 및 준비 ----
        print("[*] 변환 도구 확인 중...")
        
        ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        third_party_dir = os.path.join(ROOT_DIR, "third_party")
        whisper_cpp_dir = os.path.join(third_party_dir, "whisper.cpp")
        converter_script = os.path.join(whisper_cpp_dir, "models", "convert-h5-to-ggml.py")

        # 도구가 없으면 깃 클론 시도
        if not os.path.exists(whisper_cpp_dir):
            print("[!] whisper.cpp 도구가 없습니다. 자동으로 클론을 시작합니다...")
            os.makedirs(third_party_dir, exist_ok=True)
            subprocess.run([
                "git", "clone", "--depth", "1", 
                "https://github.com/ggerganov/whisper.cpp.git", 
                whisper_cpp_dir
            ], check=True)
            print("✅ 도구 클론 완료!")

        # ---- 3단계: GGUF(GGML) 변환 실행 ----
        print("[*] GGUF 변환 중: 모델 포맷을 GGML로 변환하는 중... (수 분 소요)")
        
        if not os.path.exists(converter_script):
            print(f"❌ [Error] 변환 스크립트를 찾을 수 없습니다: {converter_script}")
            return

        # 변환 실행 (실시간 로그를 위해 capture_output 제거)
        process = subprocess.run([
            sys.executable, converter_script, 
            merged_path, 
            "." 
        ])
        
        if process.returncode != 0:
            print(f"❌ [Error] 변환 실패 (Exit Code: {process.returncode})")
            return
        
        print("✅ GGUF 변환 완료!")

        # ---- 4단계: 최종 모델 배포 ----
        print("[*] 배포 중: 에이전트 모델 폴더로 이동 중...")
        
        source_bin = "ggml-model.bin"
        target_name = "ggml-shuka-tiny.bin"
        final_dest = os.path.join(GGUF_DIR, target_name)
        
        os.makedirs(GGUF_DIR, exist_ok=True)
        
        if os.path.exists(source_bin):
            if os.path.exists(final_dest):
                os.remove(final_dest)
            shutil.move(source_bin, final_dest)
            print(f"✅ 최종 모델 배포 완료: {final_dest}")
        else:
            print("❌ [Error] 변환된 .bin 파일을 찾을 수 없습니다.")
            return

        # ---- 5단계: 완료 안내 패널 ----
        print("\n" + "="*50)
        print("🎉 [SUCCESS] 슈카 AI 모델 탄생!")
        print(f"📍 위치: {final_dest}")
        print("🚀 AMEVA-STT-Agent에서 '기타 모델 선택'으로 불러오세요.")
        print("="*50 + "\n")

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
