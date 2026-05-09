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

# 프로젝트 루트 디렉터리를 Python 경로에 등록하여 src 모듈을 불러올 수 있도록 설정
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.whisper_lora import merge_and_save
from src.core.config         import MERGED_DIR, GGUF_DIR, LORA_DIR
from src.utils               import logger


def main():
    # 모델 내보내기 작업 시작 알림
    logger.info("=" * 50)
    logger.info("[3단계] 모델 내보내기 시작")
    logger.info("=" * 50)

    # ---- 1단계: LoRA 가중치 병합 ----
    # 학습 결과물인 LoRA 어댑터 폴더가 존재하는지 확인
    if not os.path.exists(LORA_DIR):
        # 학습 결과가 없으면 병합할 수 없으므로 종료
        logger.error(f"LoRA 어댑터 없음: {LORA_DIR}. 먼저 02_start_training.py를 실행하세요.")
        sys.exit(1)

    # 베이스 모델 가중치에 LoRA 가중치를 더해 단일 모델 파일로 합치기
    merged_path = merge_and_save()
    logger.info(f"병합 모델 저장 완료: {merged_path}")

    # ---- 2단계: GGUF(Whisper.cpp용) 변환 가이드 출력 ----
    # 윈도우 환경에서 GGUF 변환은 외부 툴(whisper.cpp)이 필요하므로 명령어 가이드를 출력함
    print("\n" + "=" * 60)
    print("  GGUF 변환 절차 (수동 실행)")
    print("=" * 60)
    print(f"\n[1] whisper.cpp 소스 코드 획득 및 빌드 (최초 1회)")
    print("    git clone https://github.com/ggerganov/whisper.cpp.git")
    print("    cd whisper.cpp && cmake -B build && cmake --build build --config Release")
    
    print(f"\n[2] 병합된 HuggingFace 모델을 GGUF 포맷으로 변환")
    # 병합된 모델 경로를 인자로 전달하여 변환 스크립트 실행 안내
    print(f"    python whisper.cpp/models/convert-h5-to-gguf.py {merged_path} .")
    
    print(f"\n[3] 모델 용량 최적화를 위한 양자화 (선택 사항)")
    # 변환된 바이너리를 q4_0(4비트) 방식으로 압축 안내
    print(f"    ./build/bin/quantize ggml-model.bin ggml-model-q4_0.bin q4_0")
    
    print(f"\n[4] 생성된 GGUF 파일을 프로젝트 공통 모델 저장소로 이동")
    # 최종 결과물을 보관할 시스템 경로 안내
    print(f"    대상 경로: {GGUF_DIR}")
    print("=" * 60)

    # 전체 단계 완료 로그
    logger.info("[3단계] 내보내기 완료")


if __name__ == "__main__":
    # 메인 실행부 호출
    main()
