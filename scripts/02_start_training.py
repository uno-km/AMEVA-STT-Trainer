"""
scripts/02_start_training.py
[단계 2] LoRA 학습 실행 엔트리 포인트.

- 이미 저장된 체크포인트가 있으면 자동으로 이어서 학습한다.
- 학습 시작 전 데이터셋 존재 여부를 사전 점검한다.
"""
import sys
import os

# 프로젝트 루트 디렉터리를 Python 경로에 등록하여 src 모듈을 불러올 수 있도록 설정
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.training.trainer import run_training
from src.core.config      import METADATA_PATH
from src.utils            import logger


def main():
    # 실시간 모니터링 대시보드 환경 구축 (경과 시간, 자원 사용량 등 표시)
    with logger.dashboard_context():
        logger.info("=" * 50)
        logger.info("[2단계] LoRA 학습 시작")
        logger.info("=" * 50)

        # 1. 데이터셋 무결성 사전 점검
        # 전처리된 메타데이터 파일(metadata.csv)이 존재하는지 확인
        if not os.path.exists(METADATA_PATH):
            # 파일이 없으면 학습을 진행할 수 없으므로 에러 출력 후 종료
            logger.error(f"metadata.csv 없음: {METADATA_PATH}")
            logger.error("먼저 01_build_dataset.py를 실행하세요.")
            sys.exit(1)

        # 2. 학습 파이프라인 가동
        # 모델 로드, LoRA 적용, 학습 루프 실행 등 핵심 로직 호출
        run_training()

        # 3. 종료 알림
        logger.success("=" * 50)
        logger.success("[2단계] 학습 완료")
        logger.success("=" * 50)


if __name__ == "__main__":
    # 메인 실행부 호출
    main()
