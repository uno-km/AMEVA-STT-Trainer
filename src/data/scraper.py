"""
src/data/scraper.py
유튜브 채널에서 영상 오디오 및 VTT 자막을 수집한다.
"""
import os
import sys
import subprocess
from datetime import datetime
from typing import List, Tuple, Optional

from src.core.config import CFG, DATASET_DIR
from src.core.exceptions import NetworkError, exception_guard
from src.utils import logger


# --- FFmpeg 경로 자동 탐지 ---
FFMPEG_C_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
FFMPEG_BIN_DIR = os.path.dirname(FFMPEG_C_PATH) if os.path.exists(FFMPEG_C_PATH) else None

VideoInfo = Tuple[str, str, Optional[str], Optional[str]]


@exception_guard(location="get_video_info_list() -> yt-dlp 채널 조회", reraise=True)
def get_video_info_list(channel_url: str, count: int) -> List[Tuple[str, str, str]]:
    """채널에서 최신 N개 영상의 (video_id, upload_date, title) 목록을 반환한다."""
    logger.info(f"채널 조회 시작: {channel_url} (최대 {count}개)")

    # [수정] --flat-playlist에서 날짜가 누락되는 경우를 위해 포맷 변경
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--print", "%(id)s|%(upload_date)s|%(title)s",
        "--playlist-items", f"1:{count}",
        "--flat-playlist",
        "--no-warnings",
        channel_url,
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=False)

    if result.returncode != 0:
        err_msg = result.stderr.decode("utf-8", errors="ignore") if result.stderr else "알 수 없는 오류"
        raise NetworkError(f"yt-dlp 채널 조회 실패:\n{err_msg[:500]}")

    if not result.stdout:
        return []

    output = result.stdout.decode("utf-8", errors="ignore")
    pairs = []
    today = datetime.now().strftime("%Y%m%d")
    
    for line in output.strip().split("\n"):
        line = line.strip()
        if line.count("|") < 2:
            continue
        parts = line.split("|", 2)
        vid      = parts[0].strip()
        # 날짜가 "NA"이거나 비어있으면 오늘 날짜로 대체 (폴더 구조 유지 목적)
        date_raw = parts[1].strip()
        date_str = date_raw if (date_raw and date_raw != "NA") else today
        title    = parts[2].strip() if len(parts) > 2 else "Untitled"
        
        if vid:
            pairs.append((vid, date_str, title))

    logger.info(f"영상 {len(pairs)}개 정보 확인 완료")
    return pairs


def date_to_folder(date_str: str, video_id: str) -> str:
    """'YYYYMMDD' -> 'dataset/YYYY/MM/DD/{video_id}'"""
    try:
        # 날짜가 최소 8자리(YYYYMMDD)인지 확인
        if len(date_str) < 8:
            raise ValueError("Invalid date length")
        y, m, d = date_str[:4], date_str[4:6], date_str[6:8]
        return os.path.join(DATASET_DIR, y, m, d, video_id)
    except Exception:
        logger.warning(f"날짜 형식 오류 ({date_str}), unknown 폴더 사용: {video_id}")
        return os.path.join(DATASET_DIR, "unknown", video_id)


@exception_guard(location="download_video_data() -> yt-dlp 다운로드")
def download_video_data(video_id: str, video_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """오디오(WAV)와 VTT 자막을 다운로드한다."""
    os.makedirs(video_dir, exist_ok=True)

    audio_path = os.path.join(video_dir, "raw.wav")
    vtt_path   = os.path.join(video_dir, f"{video_id}.ko.vtt")
    url        = f"https://www.youtube.com/watch?v={video_id}"

    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
        logger.info(f"[SKIP] 오디오 이미 존재: {video_id}")
    else:
        sr = CFG["sample_rate"]
        audio_cmd = [
            sys.executable, "-m", "yt_dlp", "-x", "--audio-format", "wav",
            "--audio-quality", "0",
            "--postprocessor-args", f"ffmpeg:-ar {sr} -ac 1",
            "--no-playlist",
        ]
        if FFMPEG_BIN_DIR:
            audio_cmd.extend(["--ffmpeg-location", FFMPEG_BIN_DIR])
            
        audio_cmd.extend([
            "-o", os.path.join(video_dir, "raw.%(ext)s"),
            url,
        ])
        res = subprocess.run(audio_cmd, capture_output=True, text=False)
        if res.returncode != 0 or not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            audio_path = None

    if os.path.exists(vtt_path) and os.path.getsize(vtt_path) > 0:
        logger.info(f"[SKIP] VTT 이미 존재: {video_id}")
    else:
        vtt_cmd = [
            sys.executable, "-m", "yt_dlp",
            "--write-auto-subs", "--sub-format", "vtt", "--sub-langs", "ko",
            "--skip-download",
            "--no-playlist",
            "-o", os.path.join(video_dir, "%(id)s.%(ext)s"),
            url,
        ]
        res = subprocess.run(vtt_cmd, capture_output=True, text=False)
        if not os.path.exists(vtt_path) or os.path.getsize(vtt_path) == 0:
            vtt_path = None

    return audio_path, vtt_path


def scrape_channel() -> List[VideoInfo]:
    channel_url = CFG["channel_url"]
    max_videos  = CFG["max_videos"]

    pairs = get_video_info_list(channel_url, max_videos)
    results: List[VideoInfo] = []

    for idx, (video_id, date_str, title) in enumerate(pairs):
        display_title = (title[:25] + "..") if len(title) > 25 else title
        logger.set_status("유튜브 수집 중", f"[{idx+1}/{len(pairs)}] {display_title}")
        
        video_dir = date_to_folder(date_str, video_id)
        audio_path, vtt_path = download_video_data(video_id, video_dir) or (None, None)
        results.append((video_id, date_str, audio_path, vtt_path))

    logger.info(f"수집 완료: 총 {len(results)}개 영상 처리")
    return results
