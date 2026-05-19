import os
import sys

# --- FFmpeg 경로 자동 등록 및 pydub 경고 방지 ---
FFMPEG_C_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
FFMPEG_BIN_DIR = os.path.dirname(FFMPEG_C_PATH)

if os.path.exists(FFMPEG_C_PATH):
    # 시스템 PATH에 추가
    if FFMPEG_BIN_DIR not in os.environ.get("PATH", ""):
        os.environ["PATH"] = FFMPEG_BIN_DIR + os.pathsep + os.environ.get("PATH", "")
    
    # pydub 모듈에 직접 바인딩
    try:
        from pydub import AudioSegment
        AudioSegment.converter = FFMPEG_C_PATH
        AudioSegment.ffprobe = os.path.join(FFMPEG_BIN_DIR, "ffprobe.exe")
    except ImportError:
        pass
