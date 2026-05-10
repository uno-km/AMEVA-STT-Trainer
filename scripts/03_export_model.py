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
from rich.panel              import Panel
from rich.table              import Table
from rich.console            import Group


def main():
    with logger.dashboard_context():
        logger.info("=" * 50)
        logger.info("[3단계] 모델 내보내기 및 병합 시작")
        logger.info("=" * 50)

        # ---- 1단계: LoRA 가중치 병합 ----
        logger.set_status("모델 병합 중", "LoRA 어댑터와 베이스 모델을 합치는 중...")
        
        if not os.path.exists(LORA_DIR):
            logger.error(f"LoRA 어댑터 없음: {LORA_DIR}")
            return

        # 실제 병합 로직 실행
        merged_path = merge_and_save()
        logger.success(f"병합 완료: {merged_path}")

        # ---- 2단계: GGUF 가이드 패널 구성 ----
        logger.set_status("완료", "최종 모델 생성 완료!")
        
        guide_text = (
            "[bold yellow][1] whisper.cpp 빌드[/]\n"
            "   git clone https://github.com/ggerganov/whisper.cpp.git\n"
            "   cd whisper.cpp && cmake -B build && cmake --build build --config Release\n\n"
            "[bold yellow][2] GGUF 변환[/]\n"
            f"   python whisper.cpp/models/convert-h5-to-gguf.py {merged_path} .\n\n"
            "[bold yellow][3] 양자화 (선택)[/]\n"
            "   ./build/bin/quantize ggml-model.bin ggml-model-q4_0.bin q4_0\n\n"
            f"[bold cyan][DONE] 최종 파일 이동 -> {GGUF_DIR}[/]"
        )
        
        guide_panel = Panel(
            guide_text,
            title="[bold cyan]🚀 GGUF 변환 절차 가이드[/]",
            border_style="bright_blue",
            padding=(1, 2)
        )
        
        # 대시보드 종료 후 가이드 출력
        logger.stop_dashboard()
        print("\n")
        logger.console.print(guide_panel)
        print("\n")
        
        logger.info("[3단계] 모든 프로세스 종료")


if __name__ == "__main__":
    # 메인 실행부 호출
    main()
