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
    AudioSegment 슬라이스를 16kHz Mono 16-bit 표준 PCM WAV 규격으로 강제 포맷팅하여 안전하게 저장한다.
    MIN_CHUNK_DURATION_MS 미만이면 저장하지 않고 False를 반환한다.
    """
    if len(audio) < CFG["min_chunk_duration_ms"]:
        return False
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # [고도화] Whisper 입력을 위해 16,000Hz 샘플레이트, Mono(1채널), 16-bit PCM(sample_width=2) 강제 리샘플링 포맷팅
    standardized = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    standardized.export(out_path, format="wav")
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
    """오디오 음량을 표준 레벨로 맞춘다. (Peak Level Normalization)"""
    try:
        return effects.normalize(audio)
    except Exception:
        return audio

def trim_silence(audio: AudioSegment, base_thresh: float = -40.0, chunk_size: int = 10) -> AudioSegment:
    """
    오디오의 '앞뒤'에 존재하는 불필요한 공백/침묵 구간만 지능적으로 절단하여 반환한다.
    (1) 전체 평균 볼륨(dBFS)을 기준으로 침묵 데시벨을 유동적으로 계산하는 적응형 임계치(Adaptive Threshold) 적용 (완전 무음 -inf 대응 안전망 탑재)
    (2) 최소 20ms 연속으로 소리가 감지될 때 실제 발화 시작으로 판단하는 최소 연속 구간 가드(Consecutive Frame Guard) 적용
    (3) 중간에 말하다가 멈추는 무음은 온전히 유지하여, 오디오-자막 간의 시계열 동기화 왜곡을 완벽히 방지한다.
    """
    if len(audio) < 100:
        return audio
        
    # 전체 평균 볼륨에 따라 적응형 임계치 설정 (완전 디지털 무음 -inf 대응용 안전 가드)
    avg_db = audio.dBFS
    if avg_db == float('-inf') or avg_db < -90.0:
        avg_db = -50.0
    silence_thresh = max(-50.0, min(-30.0, avg_db - 15.0))
    
    start_trim = 0
    end_trim = len(audio)
    
    # 20ms 연속 (10ms * 2프레임) 소리 감지 시 통과
    consecutive_frames = 2
    
    # 1. 앞쪽(Leading) 침묵 스캔
    for ms in range(0, len(audio) - chunk_size * consecutive_frames, chunk_size):
        triggered = True
        for i in range(consecutive_frames):
            if audio[ms + i*chunk_size : ms + (i+1)*chunk_size].dBFS <= silence_thresh:
                triggered = False
                break
        if triggered:
            start_trim = ms
            break
            
    # 2. 뒤쪽(Trailing) 침묵 스캔
    for ms in range(len(audio), chunk_size * consecutive_frames, -chunk_size):
        triggered = True
        for i in range(consecutive_frames):
            if audio[ms - (i+1)*chunk_size : ms - i*chunk_size].dBFS <= silence_thresh:
                triggered = False
                break
        if triggered:
            end_trim = ms
            break
            
    # 말소리 시작/종료 시 음운이 급격히 잘리는 현상(Clipping)을 막기 위해 100ms의 안전 버퍼 적용
    start_trim = max(0, start_trim - 100)
    end_trim = min(len(audio), end_trim + 100)
    
    if start_trim >= end_trim or (end_trim - start_trim) < 100:
        return audio
        
    return audio[start_trim:end_trim]
