"""
src/models/downloader.py
Whisper 모델을 C:\ameva\models\stt\ 에 다운로드한다.

- HuggingFace Hub에서 GGUF 파일 직접 다운로드
- 이미 존재하면 스킵 (용량 낭비 방지)
- whisper-tiny의 공식 GGUF: ggerganov/whisper.cpp 레포에서 제공
"""
import os
import urllib.request
from src.core.config import GGUF_DIR
from src.core.exceptions import ModelError, exception_guard
from src.utils import logger

# whisper-tiny 모델의 공식 GGUF 바이너리 다운로드 주소 목록
GGUF_FILES = {
    # 기본 정밀도 모델
    "ggml-tiny.bin"   : "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
    # 8비트 양자화 모델
    "ggml-tiny-q8_0.bin" : "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny-q8_0.bin",
}


@exception_guard(location="download_gguf_model() -> urllib 다운로드", reraise=True)
def download_gguf_model(filename: str = "ggml-tiny.bin") -> str:
    """
    지정한 GGUF 파일을 GGUF_DIR에 다운로드한다.
    이미 존재하면 스킵하고 경로를 반환한다.

    Args:
        filename: GGUF_FILES의 키 값 (기본: ggml-tiny.bin)
    Returns:
        저장된 절대 경로
    """
    # 요청된 파일명이 지원 목록에 있는지 확인
    if filename not in GGUF_FILES:
        raise ModelError(f"지원하지 않는 파일명: {filename}. 선택 가능: {list(GGUF_FILES.keys())}")

    # GGUF 모델 저장용 디렉터리 생성 (이미 있으면 무시)
    os.makedirs(GGUF_DIR, exist_ok=True)
    # 최종 저장될 절대 경로 조합
    dest_path = os.path.join(GGUF_DIR, filename)

    # 파일이 이미 존재하고 크기가 0이 아니면 다운로드 생략
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        logger.info(f"[SKIP] 이미 존재: {dest_path}")
        return dest_path

    # 다운로드할 원본 URL 획득
    url = GGUF_FILES[filename]
    logger.info(f"다운로드 시작: {url}")
    logger.info(f"저장 경로: {dest_path}")

    # 다운로드 진행 상황을 표시하기 위한 내부 콜백 함수
    def _progress(block_num, block_size, total_size):
        # 현재까지 내려받은 바이트 수 계산
        downloaded = block_num * block_size
        # 전체 용량 대비 백분율 계산 (0으로 나누기 방지 포함)
        pct = downloaded / total_size * 100 if total_size > 0 else 0
        # 터미널 한 줄에 진행률과 누적 용량(MB) 표시 (커서 위치 고정)
        print(f"\r  진행: {pct:.1f}% ({downloaded // 1024 // 1024}MB)", end="", flush=True)

    # 표준 라이브러리를 사용하여 HTTP 다운로드 실행 (진행률 콜백 연결)
    urllib.request.urlretrieve(url, dest_path, reporthook=_progress)
    print()  # 다운로드 완료 후 줄바꿈

    # 다운로드 완료 후 파일 존재 여부 및 유효성 재확인
    if not os.path.exists(dest_path) or os.path.getsize(dest_path) == 0:
        raise ModelError(f"다운로드 후 파일 없음 또는 0바이트: {dest_path}")

    logger.info(f"다운로드 완료: {dest_path}")
    return dest_path
