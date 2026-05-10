"""
src/utils/audio_utils.py
오디오 파일 관련 유틸리티.
- pydub AudioSegment 로딩 및 WAV 변환/저장 헬퍼
"""
import os
import sys
from pydub import AudioSegment, effects
from pydub.silence import split_on_silence
from src.core.config import CFG
from src.core.exceptions import AudioError

# --- FFmpeg 경로 자동 탐지 및 경고 방지 ---
FFMPEG_C_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
FFMPEG_BIN_DIR = os.path.dirname(FFMPEG_C_PATH)

if os.path.exists(FFMPEG_C_PATH):
    # 1. pydub 직접 경로 지정
    AudioSegment.converter = FFMPEG_C_PATH
    AudioSegment.ffprobe = os.path.join(FFMPEG_BIN_DIR, "ffprobe.exe")
    
    # 2. 시스템 PATH에 추가 (pydub의 RuntimeWarning 방지용)
    if FFMPEG_BIN_DIR not in os.environ["PATH"]:
        os.environ["PATH"] += os.pathsep + FFMPEG_BIN_DIR


def load_wav(path: str) -> AudioSegment:
    """
    WAV 파일을 로드한다.
    Raises AudioError (손상된 파일 시).
    """
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raise AudioError(f"파일 없음 또는 0바이트: {path}")
    try:
        return AudioSegment.from_wav(path)
    except Exception as e:
        raise AudioError(f"pydub 로드 실패 ({path}): {e}") from e


def export_chunk(audio: AudioSegment, out_path: str) -> bool:
    """
    AudioSegment 슬라이스를 WAV로 저장한다.
    MIN_CHUNK_DURATION_MS 미만이면 저장하지 않고 False를 반환한다.
    """
    if len(audio) < CFG["min_chunk_duration_ms"]:
        return False
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    audio.export(out_path, format="wav")
    return True


def slice_audio(audio: AudioSegment, start_ms: int, end_ms: int) -> AudioSegment:
    """
    패딩을 적용하여 오디오를 잘라낸다.
    오디오 범위를 벗어나지 않도록 clamping 처리한다.
    """
    pad = CFG["audio_padding_ms"]
    s = max(0, start_ms - pad)
    e = min(len(audio), end_ms + pad)
    return audio[s:e]

def normalize_audio(audio: AudioSegment) -> AudioSegment:
    """오디오 음량을 표준 레벨로 맞춘다."""
    return effects.normalize(audio)

def trim_silence(audio: AudioSegment) -> AudioSegment:
    """오디오 앞뒤의 침묵을 제거한다."""
    # -40dB 이하를 침묵으로 간주, 최소 침묵 길이는 500ms
    chunks = split_on_silence(audio, min_silence_len=500, silence_thresh=-40, keep_silence=100)
    if not chunks:
        return audio
    # 잘려진 청크들을 다시 합쳐서 반환
    combined = AudioSegment.empty()
    for chunk in chunks:
        combined += chunk
    return combined
