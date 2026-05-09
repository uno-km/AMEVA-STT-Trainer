"""
scripts/download_model.py
[선택] whisper-tiny GGUF 파일을 C:\\ameva\\AI_Models\\ggml\\ 에 다운로드한다.
학습 전 추론 기준선 테스트를 위해 사용한다.
"""
import sys
import os

# 프로젝트 루트 디렉터리를 Python 경로에 등록하여 src 모듈을 불러올 수 있도록 설정
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.downloader import download_gguf_model
from src.utils import logger


def main():
    # GGUF 모델 다운로드 시작 알림
    logger.info("whisper-tiny GGUF 다운로드 시작")
    
    # downloader 모듈을 호출하여 지정된 파일명을 원격 저장소에서 받아옴
    # 이미 파일이 있는 경우 자동으로 스킵 처리됨
    path = download_gguf_model("ggml-tiny.bin")
    
    # 다운로드 성공 시 저장 경로 출력
    if path:
        logger.info(f"완료: {path}")


if __name__ == "__main__":
    # 메인 함수 실행
    main()
