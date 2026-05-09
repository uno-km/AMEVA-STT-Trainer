"""
src/core/exceptions.py
전역 예외 관리자.
- 모든 파이프라인 스크립트에서 import하여 사용한다.
- 에러 발생 시 logs/syuka_error_log.md에 누적 기록한다.
- @exception_guard 데코레이터로 함수에 자동 적용 가능하다.
"""
import os
import sys
import traceback
import functools
from datetime import datetime

# 로그 파일 경로 (프로젝트 루트 기준)
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "syuka_error_log.md")


# ---------------------------------------------------------------------------- #
#  커스텀 예외 클래스 계층                                                       #
# ---------------------------------------------------------------------------- #

# 파이프라인 전체 공통 베이스 예외: 모든 커스텀 예외의 부모 클래스
class PipelineError(Exception):
    """파이프라인 전체를 아우르는 베이스 예외."""
    pass

# 네트워크 통신 실패 시 사용하는 예외
class NetworkError(PipelineError):
    """yt-dlp 다운로드, 유튜브 API 요청 실패."""
    pass

# 오디오 파일 손상·파싱 실패 시 사용하는 예외
class AudioError(PipelineError):
    """오디오 파일 손상, pydub 파싱 실패."""
    pass

# 자막 파일 누락·파싱 실패 시 사용하는 예외
class TranscriptError(PipelineError):
    """VTT/자막 파일 없음, 파싱 실패."""
    pass

# 데이터셋 파일 쌍 불일치·0바이트 파일 발견 시 사용하는 예외
class DataIntegrityError(PipelineError):
    """metadata.csv - wav 파일 쌍 불일치, 0바이트 파일."""
    pass

# 학습 루프 내 오류·메모리 부족 시 사용하는 예외
class TrainingError(PipelineError):
    """학습 루프 내 예외, OOM 등."""
    pass

# 모델 로딩·저장·변환 실패 시 사용하는 예외
class ModelError(PipelineError):
    """모델 로딩, 저장, 변환 실패."""
    pass


# ---------------------------------------------------------------------------- #
#  로그 기록 함수                                                                #
# ---------------------------------------------------------------------------- #

def log_exception(error: Exception, location: str = "Unknown") -> None:
    """
    예외를 logs/syuka_error_log.md에 포맷하여 누적 기록한다.
    Args:
        error   : 발생한 예외 객체
        location: "함수명() -> 수행 작업" 형태의 문자열
    """
    # 로그 파일이 위치할 디렉터리가 없으면 자동 생성
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    # 현재 시각을 'YYYY-MM-DD HH:MM:SS' 형식으로 포맷팅
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 예외 클래스 이름 추출 (예: AudioError)
    error_type = type(error).__name__
    # 스택 트레이스 전체 문자열 수집
    tb = traceback.format_exc()

    # Markdown 블록 형식으로 기록
    entry = (
        f"\n## [{timestamp}] {error_type}\n"
        f"- **발생 위치**: {location}\n"
        f"- **메시지**: {str(error)}\n"
        f"```\n{tb}```\n"
        f"---\n"
    )

    # 로그 파일에 추가 모드로 기록 (기존 내용 보존)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry)

    # 콘솔에도 간략히 출력
    print(f"[ERROR] {timestamp} | {error_type} @ {location}")
    print(f"        {str(error)}")


# ---------------------------------------------------------------------------- #
#  @exception_guard 데코레이터                                                  #
# ---------------------------------------------------------------------------- #

def exception_guard(location: str = None, reraise: bool = False):
    """
    함수에 붙이면 예외를 자동으로 log_exception으로 기록한다.
    Args:
        location: 생략 시 함수명을 자동 사용.
        reraise : True이면 기록 후 예외를 다시 던진다 (치명적 오류 시 사용).
    Usage:
        @exception_guard(location="process_video() -> VTT 파싱")
        def process_video(...): ...
    """
    def decorator(func):
        # functools.wraps 로 원본 함수의 이름·독스트링 보존
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # location 이 없으면 함수 이름을 자동으로 사용
            loc = location or f"{func.__name__}()"
            try:
                # 원본 함수 실행
                return func(*args, **kwargs)
            except Exception as e:
                # 예외 발생 시 로그 파일에 기록
                log_exception(e, loc)
                if reraise:
                    # 치명적 오류: 기록 후 예외를 다시 상위로 전파
                    raise
                return None  # 실패 시 None 반환 -> 호출부에서 방어 처리
        return wrapper
    return decorator
