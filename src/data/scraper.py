"""
src/data/scraper.py
유튜브 채널에서 영상 오디오 및 VTT 자막을 수집한다.

파이프라인:
  1. yt-dlp로 채널의 최신 N개 영상 ID + 업로드 날짜 수집
  2. 날짜 기반 폴더 생성: dataset/YYYY/MM/DD/{video_id}/
  3. yt-dlp로 오디오(WAV, 16kHz mono)와 VTT 자막 동시 다운로드
  4. 결과 반환: [(video_id, upload_date_str, audio_path, vtt_path)]

NOTE: youtube_transcript_api 대신 yt-dlp VTT 방식을 사용한다.
      API 방식은 차단/레이트리밋에 취약하지만,
      yt-dlp는 실제 브라우저 요청을 흉내내어 훨씬 안정적이다.
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
# C:\ffmpeg 에 FFmpeg 가 설치되어 있으면 해당 경로 사용
FFMPEG_C_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
# FFmpeg 실행 파일이 실제로 존재하면 bin 디렉터리 경로 저장, 없으면 None
FFMPEG_BIN_DIR = os.path.dirname(FFMPEG_C_PATH) if os.path.exists(FFMPEG_C_PATH) else None

# ---------------------------------------------------------------------------- #
#  타입 정의                                                                     #
# ---------------------------------------------------------------------------- #
# (video_id, date_str "YYYYMMDD", audio_path, vtt_path) 4-튜플 타입 별칭
VideoInfo = Tuple[str, str, Optional[str], Optional[str]]


# ---------------------------------------------------------------------------- #
#  영상 정보 수집                                                                #
# ---------------------------------------------------------------------------- #

def find_cookies_file() -> Optional[str]:
    """cookies.txt 파일의 흔한 위치들을 뒤져서 실제 존재하는 절대경로를 반환합니다."""
    for p in [
        os.path.abspath("cookies.txt"),
        "/content/cookies.txt",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "cookies.txt"))
    ]:
        if os.path.exists(p):
            return p
    return None


@exception_guard(location="get_video_info_list() -> yt-dlp 채널 조회", reraise=True)
def get_video_info_list(channel_url: str, count: int) -> List[Tuple[str, str, str]]:
    """
    채널에서 최신 N개 영상의 (video_id, upload_date, title) 튜플 목록을 반환한다.
    upload_date 형식: YYYYMMDD (예: 20260423)
    """
    logger.info(f"채널 조회 시작: {channel_url} (최대 {count}개)")

    # yt-dlp: ID, 업로드 날짜, 제목을 파이프(|) 구분자로 출력
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--print", "%(id)s|%(upload_date)s|%(title)s",  # 출력 포맷: id|날짜|제목
        "--playlist-items", f"1:{count}",      # 최신 count개만 가져오기
        "--flat-playlist",                     # 영상 내용은 다운로드하지 않고 목록만 수집
        "--no-warnings",
        "--extractor-args", "youtube:player_client=android,web"
    ]
    
    cookie_path = find_cookies_file()
    if cookie_path:
        cmd.extend(["--cookies", cookie_path])
        
    cmd.append(channel_url)
    
    # [수정] 인코딩 오류 방지를 위해 바이트 단위로 캡처 후 수동 디코딩
    result = subprocess.run(cmd, capture_output=True, text=False)

    # 반환 코드가 0이 아니면 yt-dlp 실행 실패
    if result.returncode != 0:
        err_msg = result.stderr.decode("utf-8", errors="ignore") if result.stderr else "알 수 없는 오류"
        raise NetworkError(f"yt-dlp 채널 조회 실패:\n{err_msg[:500]}")

    # stdout 이 비어있으면 빈 리스트 반환
    if not result.stdout:
        return []

    # 바이트 데이터를 문자열로 변환 (한글 인코딩 충돌 방지를 위해 errors="ignore" 적용)
    output = result.stdout.decode("utf-8", errors="ignore")
    
    pairs = []
    today = datetime.now().strftime("%Y%m%d")
    
    for line in output.strip().split("\n"):
        line = line.strip()
        # 파이프 구분자가 최소 2개(id|date|title) 있어야 함
        if line.count("|") < 2:
            continue
        # 첫 번째와 두 번째 파이프를 기준으로 분리
        parts = line.split("|", 2)
        vid      = parts[0].strip()
        # 날짜가 "NA"이거나 비어있으면 오늘 날짜로 대체 (폴더 구조 유지 목적)
        date_raw = parts[1].strip()
        date_str = date_raw if (date_raw and date_raw != "NA") else today
        title    = parts[2].strip() if len(parts) > 2 else "Untitled"
        
        if vid:
            pairs.append((vid, date_str, title))

    pairs = pairs[:count]
    logger.info(f"영상 {len(pairs)}개 정보 확인 완료")
    return pairs


# ---------------------------------------------------------------------------- #
#  날짜 -> 폴더 경로 변환                                                        #
# ---------------------------------------------------------------------------- #

def date_to_folder(date_str: str, video_id: str) -> str:
    """
    'YYYYMMDD' 형식의 날짜를 'dataset/YYYY/MM/DD/{video_id}' 절대 경로로 변환한다.
    날짜 파싱 실패 시 'dataset/unknown/{video_id}'로 폴백한다.
    기존에 동일한 video_id 폴더가 dataset 하위에 존재할 경우 해당 경로를 그대로 반환해 중복 다운로드를 차단합니다.
    """
    # [중복 차단] 기존에 이미 다운로드된 video_id 폴더가 존재한다면 그 경로를 우선 재사용
    if os.path.exists(DATASET_DIR):
        for root, dirs, files in os.walk(DATASET_DIR):
            if video_id in dirs:
                existing_path = os.path.join(root, video_id)
                if os.path.exists(os.path.join(existing_path, "raw.wav")):
                    return existing_path

    try:
        # 날짜가 최소 8자리(YYYYMMDD)인지 확인
        if len(date_str) < 8:
            raise ValueError("Invalid date length")
        y, m, d = date_str[:4], date_str[4:6], date_str[6:8]
        # DATASET_DIR 하위에 연/월/일/video_id 구조로 경로 조합
        return os.path.join(DATASET_DIR, y, m, d, video_id)
    except Exception:
        # 날짜 형식이 올바르지 않으면 unknown 폴더로 폴백
        logger.warning(f"날짜 파싱 실패 ({date_str}), unknown 폴더로 이동: {video_id}")
        return os.path.join(DATASET_DIR, "unknown", video_id)


# ---------------------------------------------------------------------------- #
#  오디오 + VTT 다운로드                                                         #
# ---------------------------------------------------------------------------- #

@exception_guard(location="download_video_data() -> yt-dlp 다운로드")
def download_video_data(video_id: str, video_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """
    단일 영상의 오디오(WAV)와 VTT 자막을 video_dir에 다운로드한다.
    Returns: (audio_path, vtt_path) - 실패한 항목은 None
    """
    # 영상 전용 디렉터리가 없으면 생성
    os.makedirs(video_dir, exist_ok=True)

    # 최종 저장될 오디오 파일 경로 (raw.wav)
    audio_path = os.path.join(video_dir, "raw.wav")
    # VTT 파일명 패턴: yt-dlp가 {video_id}.ko.vtt 형태로 저장한다
    vtt_path   = os.path.join(video_dir, f"{video_id}.ko.vtt")
    # 유튜브 영상 URL 조합
    url        = f"https://www.youtube.com/watch?v={video_id}"
    
    cookie_path = find_cookies_file()

    # ----- 오디오: 이미 존재하면 스킵 -----
    if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
        logger.info(f"[SKIP] 오디오 이미 존재: {video_id}")
    else:
        # 설정값에서 샘플링 레이트 가져오기
        sr = CFG["sample_rate"]
        # yt-dlp 오디오 추출 명령어 구성
        audio_cmd = [
            sys.executable, "-m", "yt_dlp", "-x", "--audio-format", "wav",
            "--audio-quality", "0",
            "--postprocessor-args", f"ffmpeg:-ar {sr} -ac 1",
            "--no-playlist",
            "--extractor-args", "youtube:player_client=android,web"
        ]
        if cookie_path:
            audio_cmd.extend(["--cookies", cookie_path])

        # FFmpeg 경로가 감지되면 위치 추가
        if FFMPEG_BIN_DIR:
            audio_cmd.extend(["--ffmpeg-location", FFMPEG_BIN_DIR])
            
        # 출력 파일 경로 및 URL 추가
        audio_cmd.extend([
            "-o", os.path.join(video_dir, "raw.%(ext)s"),
            url,
        ])
        # 오디오 다운로드 실행 (바이트 캡처로 인코딩 충돌 방지)
        res = subprocess.run(audio_cmd, capture_output=True, text=False)
        # 실패 또는 파일 미생성·0바이트이면 audio_path 를 None 으로 표시
        if res.returncode != 0 or not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            err_msg = res.stderr.decode("utf-8", errors="ignore") if res.stderr else "오류"
            logger.error(f"오디오 다운로드 실패: {video_id}\n{err_msg[:300]}")
            audio_path = None

    # ----- VTT 자막: 이미 존재하면 스킵 -----
    if os.path.exists(vtt_path) and os.path.getsize(vtt_path) > 0:
        logger.info(f"[SKIP] VTT 이미 존재: {video_id}")
    else:
        # yt-dlp 자동 자막 다운로드 명령어 구성 (오디오 재다운로드 방지)
        vtt_cmd = [
            sys.executable, "-m", "yt_dlp",
            "--write-auto-subs", "--sub-format", "vtt", "--sub-langs", "ko",
            "--skip-download",   # 오디오는 위에서 이미 받았으므로 재다운 방지
            "--no-playlist",
            "--extractor-args", "youtube:player_client=android,web"
        ]
        if cookie_path:
            vtt_cmd.extend(["--cookies", cookie_path])
            
        vtt_cmd.extend([
            "-o", os.path.join(video_dir, "%(id)s.%(ext)s"),
            url,
        ])
        # 자막 다운로드 실행
        res = subprocess.run(vtt_cmd, capture_output=True, text=False)
        # 파일이 생성되지 않았거나 0바이트이면 vtt_path 를 None 으로 표시
        if not os.path.exists(vtt_path) or os.path.getsize(vtt_path) == 0:
            logger.warning(f"VTT 자막 없음 (자막 미제공 영상일 수 있음): {video_id}")
            vtt_path = None

    return audio_path, vtt_path


def sanitize_channel_url(url: str) -> str:
    """유튜브 채널 URL일 경우 쇼츠/라이브를 제외한 일반 업로드 동영상만 가져오도록 /videos 접미사를 자동 보정합니다."""
    if not url:
        return url
    url = url.strip().rstrip("/")
    if ("youtube.com" in url or "youtu.be" in url) and any(x in url for x in ["/@", "/c/", "/channel/", "/user/"]):
        if not any(url.endswith(sub) for sub in ["/videos", "/shorts", "/streams", "/live"]):
            url += "/videos"
    return url


# ---------------------------------------------------------------------------- #
#  전체 채널 수집 진입점                                                          #
# ---------------------------------------------------------------------------- #

def scrape_channel(url: str = None, count: int = None, target_dir: str = None) -> List[VideoInfo]:
    """
    제공된 URL 혹은 설정의 채널에서 최신 N개 영상을 수집한다.
    VideoInfo 리스트를 반환한다.
    """
    # 전역 설정 혹은 인자로 받은 채널 URL 과 최대 수집 영상 수 로드
    channel_url = url if url else CFG["channel_url"]
    channel_url = sanitize_channel_url(channel_url)
    max_videos  = count if count else CFG["max_videos"]

    # 영상 ID, 날짜, 제목 목록 수집
    pairs = get_video_info_list(channel_url, max_videos)
    # 수집 결과를 담을 리스트 초기화
    results: List[VideoInfo] = []

    # 기존 파일 개수 계산 (스킵할 영상 카운트)
    existing_count = 0
    if target_dir and os.path.exists(target_dir):
        raw_dir = os.path.join(target_dir, "raw")
        if os.path.exists(raw_dir):
            for video_id, _, _ in pairs:
                path = os.path.join(raw_dir, video_id, "raw.wav")
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    existing_count += 1
    elif not target_dir and os.path.exists(DATASET_DIR):
        for video_id, _, _ in pairs:
            # global date_to_folder fallback check
            for root, dirs, files in os.walk(DATASET_DIR):
                if video_id in dirs:
                    existing_path = os.path.join(root, video_id)
                    if os.path.exists(os.path.join(existing_path, "raw.wav")):
                        existing_count += 1
                        break

    remaining_count = len(pairs) - existing_count
    logger.info(f"▶ [수집 분석] 전체 {len(pairs)}개 영상 중 이미 다운로드된 {existing_count}개 영상을 제외하고, 나머지 {remaining_count}개 영상의 수집을 시작합니다.")

    # 각 영상에 대해 폴더 경로 결정 후 오디오·자막 다운로드
    for idx, (video_id, date_str, title) in enumerate(pairs):
        # 대시보드 상태 업데이트: 현재 다운로드 중인 영상 제목 표시
        display_title = (title[:25] + "..") if len(title) > 25 else title
        logger.set_status("유튜브 수집 중", f"[{idx+1}/{len(pairs)}] {display_title}")
        
        # [수정] 태스크 격리 폴더가 있으면 해당 폴더의 raw 하위로 격리 저장
        if target_dir:
            video_dir = os.path.join(target_dir, "raw", video_id)
        else:
            video_dir = date_to_folder(date_str, video_id)
            
        # 다운로드 실행 후 결과 경로 수신 (실패 항목은 None)
        audio_path, vtt_path = download_video_data(video_id, video_dir) or (None, None)
        results.append((video_id, date_str, audio_path, vtt_path))
        
        # 다운로드 결과 상세 실시간 로그 출력
        if audio_path and os.path.exists(audio_path):
            size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            folder_rel = os.path.relpath(video_dir, os.getcwd())
            logger.info(f"▶ [수집 완료] {idx+1}/{len(pairs)} - 제목: {title} | ID: {video_id} | 용량: {size_mb:.2f}MB | 폴더: {folder_rel}")
            
            # [DB tb_metadata 저장]
            task_id = os.environ.get("CURRENT_TASK_ID")
            if task_id:
                try:
                    from src.backend.core.database import db_manager
                    with db_manager.get_connection() as conn:
                        cur = conn.cursor()
                        # 중복 기록 방지 검사
                        cur.execute('SELECT 1 FROM tb_metadata WHERE task_id = ? AND file_name = ?', (task_id, video_id))
                        if not cur.fetchone():
                            create_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            cur.execute('''
                                INSERT INTO tb_metadata (task_id, file_name, folder_path, create_dt)
                                VALUES (?, ?, ?, ?)
                            ''', (task_id, video_id, video_dir, create_dt))
                            conn.commit()
                except Exception as e:
                    logger.warning(f"tb_metadata DB 저장 실패: {e}")
        else:
            logger.warning(f"▶ [수집 실패] {idx+1}/{len(pairs)} - 제목: {title} | ID: {video_id}")

    logger.info(f"수집 완료: 총 {len(results)}개 영상 처리")
    return results
