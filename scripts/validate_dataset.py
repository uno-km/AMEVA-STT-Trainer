"""
scripts/validate_dataset.py
[선택] 단독으로 실행 가능한 데이터셋 무결성 검수 스크립트.
01_build_dataset.py 내부에도 포함되어 있으나,
데이터 수집 없이 검수만 다시 돌리고 싶을 때 사용한다.
"""
import sys
import os

# 프로젝트 루트 디렉터리를 Python 경로에 등록하여 src 모듈을 불러올 수 있도록 설정
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data.validator import validate_dataset
from src.utils import logger


def main():
    # 검수 작업 시작 알림
    logger.info("데이터셋 단독 검수 시작")
    
    # 3중 무결성 검수(파일 존재, 용량 확인, 텍스트 품질) 실행
    # 불량 레코드를 제거하고 정제된 데이터프레임을 반환함
    clean_df = validate_dataset()
    
    # 최종 결과 요약 출력
    logger.info(f"검수 완료: 유효 샘플 {len(clean_df)}개")


if __name__ == "__main__":
    # 메인 함수 호출
    main()
