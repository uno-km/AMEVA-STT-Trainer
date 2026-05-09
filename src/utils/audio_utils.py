"""
src/utils/audio_utils.py
오디오 파일 관련 유틸리티.
- pydub AudioSegment 로딩 및 WAV 변환/저장 헬퍼
"""
import os
from pydub import AudioSegment
from src.core.config import CFG
from src.core.exceptions import AudioError

# --- FFmpeg 경로 자동 탐지 ---
# C:\ffmpeg 에 설치된 FFmpeg 실행 파일 절대 경로
FFMPEG_C_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
if os.path.exists(FFMPEG_C_PATH):
    # pydub 이 사용할 FFmpeg 바이너리 경로를 명시적으로 지정 (시스템 PATH 불필요)
    AudioSegment.converter = FFMPEG_C_PATH
    # ffprobe도 같은 위치에 있을 확률이 높음
    AudioSegment.ffprobe = os.path.join(os.path.dirname(FFMPEG_C_PATH), "ffprobe.exe")


def load_wav(path: str) -> AudioSegment:
    """
    WAV 파일을 로드한다.
    Raises AudioError (손상된 파일 시).
    """
    # 파일이 없거나 0바이트인 경우 즉시 예외 발생
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise AudioError(f"파일 없음 또는 0바이트: {path}")
    try:
        # pydub 으로 WAV 파일을 메모리에 로드하여 AudioSegment 객체로 반환
        return AudioSegment.from_wav(path)
    except Exception as e:
        # pydub 파싱 실패 시 커스텀 AudioError 로 감싸서 상위로 전달
        raise AudioError(f"pydub 로드 실패 ({path}): {e}") from e


def export_chunk(audio: AudioSegment, out_path: str) -> bool:
    """
    AudioSegment 슬라이스를 WAV로 저장한다.
    MIN_CHUNK_DURATION_MS 미만이면 저장하지 않고 False를 반환한다.
    """
    # 설정값보다 짧은 청크는 학습에 무의미하므로 버림
    if len(audio) < CFG["min_chunk_duration_ms"]:
        return False
    # 출력 디렉터리가 없으면 자동으로 생성
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # WAV 포맷으로 파일 저장
    audio.export(out_path, format="wav")
    return True


def slice_audio(audio: AudioSegment, start_ms: int, end_ms: int) -> AudioSegment:
    """
    패딩을 적용하여 오디오를 잘라낸다.
    오디오 범위를 벗어나지 않도록 clamping 처리한다.
    """
    # 설정값에서 앞뒤 패딩 밀리초 값을 가져옴 (단어 잘림 방지)
    pad = CFG["audio_padding_ms"]
    # 시작점: 패딩만큼 앞당기되 0 미만으로 내려가지 않도록 고정
    s = max(0, start_ms - pad)
    # 끝점: 패딩만큼 늘리되 전체 오디오 길이를 초과하지 않도록 고정
    e = min(len(audio), end_ms + pad)
    # 계산된 범위로 오디오 슬라이싱 후 반환
    return audio[s:e]
