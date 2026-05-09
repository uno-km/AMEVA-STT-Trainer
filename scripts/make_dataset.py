"""
scripts/make_dataset.py
데이터셋을 구축하기 위한 전처리 스크립트.
유튜브 영상을 다운로드하고, 자막을 추출하여 오디오 조각(청크)으로 분할함.
"""
import os
import subprocess
import pandas as pd
from youtube_transcript_api import YouTubeTranscriptApi
from pydub import AudioSegment
import re
from tqdm import tqdm

# --- 기본 설정 ---
# 수집 대상 유튜브 채널의 동영상 목록 페이지 URL
CHANNEL_URL = "https://www.youtube.com/@syukaworld/videos"
# 수집할 최대 영상 개수
MAX_VIDEOS = 30
# 데이터셋이 저장될 기본 디렉터리
OUTPUT_DIR = "dataset"
# 최종 분할된 오디오 청크 저장 디렉터리
WAV_DIR = os.path.join(OUTPUT_DIR, "wav")
# 원본 영상에서 추출한 전체 오디오 저장 디렉터리
RAW_DIR = os.path.join(OUTPUT_DIR, "raw")
# 오디오 파일명과 전사 텍스트를 기록할 CSV 파일 경로
METADATA_PATH = os.path.join(OUTPUT_DIR, "metadata.csv")

# 오디오 처리 파라미터
SAMPLE_RATE = 16000           # Whisper 모델 표준 샘플링 레이트
MAX_CHUNK_DURATION_MS = 25000 # 한 청크의 최대 길이 (25초)
MIN_CHUNK_DURATION_MS = 3000  # 너무 짧은 오디오 조각 방지 (3초 미만 제외)
AUDIO_PADDING_MS = 100        # 단어 잘림 방지용 앞뒤 안전 마진 (0.1초)

# 필요한 저장 디렉터리들을 강제로 생성함
os.makedirs(WAV_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)

def get_latest_video_ids(channel_url, count=30):
    """지정된 채널에서 최신 영상들의 고유 ID 목록을 가져옴."""
    print(f"[*] 채널에서 최근 {count}개의 영상 ID를 가져옵니다: {channel_url}")
    # yt-dlp 도구를 사용하여 영상 ID만 추출하는 명령어 구성
    cmd = [
        "yt-dlp",
        "--print", "id",
        "--playlist-items", f"1:{count}",
        "--flat-playlist",
        channel_url
    ]
    # 외부 프로세스 실행 및 결과 수집
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[ERROR] 영상 ID를 가져오는 데 실패했습니다:", result.stderr)
        return []
    # 출력된 ID들을 줄 단위로 분리하여 리스트로 반환
    ids = result.stdout.strip().split('\n')
    return [vid for vid in ids if vid]

def download_audio(video_id):
    """유튜브 영상에서 오디오를 추출하여 WAV 파일로 저장함."""
    output_path = os.path.join(RAW_DIR, f"{video_id}.wav")
    
    # [안전장치 1] 이미 파일이 존재하고 용량이 0이 아니면 다운로드 생략
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return output_path
    
    # yt-dlp 를 사용하여 최고 품질의 오디오를 WAV(16kHz 모노)로 추출
    cmd = [
        "yt-dlp",
        "-x", "--audio-format", "wav",
        "--audio-quality", "0",
        "--postprocessor-args", f"ffmpeg:-ar {SAMPLE_RATE} -ac 1",
        "-o", os.path.join(RAW_DIR, f"{video_id}.%(ext)s"),
        f"https://www.youtube.com/watch?v={video_id}"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # [안전장치 2] 다운로드 프로세스 오류 또는 최종 파일 생성 실패 여부 확인
    if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        print(f"\n[ERROR] 오디오 생성 실패 ({video_id}):\n{result.stderr[:300]}")
        return None
        
    return output_path

def get_transcript(video_id):
    """유튜브 API를 통해 영상의 한국어 자막을 가져옴."""
    try:
        # 해당 영상에서 제공하는 자막 목록 확인
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            # 1순위: 수동으로 작성된 한국어('ko') 자막 시도
            return transcript_list.find_transcript(['ko']).fetch()
        except:
            # 2순위: 자동 생성된 한국어 자막 시도
            return transcript_list.find_generated_transcript(['ko']).fetch()
    except Exception as e:
        # 자막이 전혀 없는 영상의 경우 경고 출력
        print(f"\n[WARNING] 자막을 가져올 수 없습니다 ({video_id}): {e}")
        return None

def clean_text(t: str) -> str:
    """STT 학습 데이터의 품질을 높이기 위해 불필요한 특수 문자와 태그를 정제함."""
    # 줄바꿈 문자를 공백으로 변경
    t = t.replace('\n', ' ').strip()
    # 대괄호([])나 소괄호(())로 묶인 지시문(예: [음악], (박수)) 제거
    t = re.sub(r"\[.*?\]|\(.*?\)", "", t)
    # 음표 기호 제거
    t = t.replace("♪", "").strip()
    # 다중 공백을 하나의 공백으로 압축
    t = re.sub(r"\s+", " ", t)
    return t

def process_video(video_id):
    """개별 영상을 처리하여 오디오를 청크로 자르고 메타데이터 정보를 생성함."""
    # 오디오 다운로드 및 자막 데이터 획득
    audio_path = download_audio(video_id)
    transcript = get_transcript(video_id)
    
    # 둘 중 하나라도 없으면 처리 불가하므로 중단
    if not audio_path or not transcript:
        return []

    # [안전장치 3] pydub 라이브러리를 사용하여 오디오 로드 시 발생할 수 있는 에러 처리
    try:
        audio = AudioSegment.from_wav(audio_path)
    except Exception as e:
        print(f"\n[ERROR] 오디오 파일을 읽을 수 없습니다 ({video_id}): {e}")
        return []

    # 해당 영상에서 추출된 모든 청크 정보를 담을 리스트
    metadata_entries = []
    # 현재 누적 중인 자막 텍스트
    current_text = ""
    # 현재 청크의 시작 시간 (밀리초)
    current_start_ms = -1
    # 현재 청크의 끝 시간 (밀리초)
    current_end_ms = 0
    # 영상 내 청크 순서 번호
    chunk_count = 0
    
    # 자막의 각 대사 단위를 순회
    for entry in transcript:
        # 초 단위 시간을 밀리초로 변환
        start_ms = int(entry['start'] * 1000)
        end_ms = start_ms + int(entry['duration'] * 1000)
        
        # 텍스트 정제
        text = clean_text(entry['text'])
        if not text:
            continue
            
        # 첫 번째 자막이면 시작 시간 설정
        if current_start_ms == -1:
            current_start_ms = start_ms
            
        # 현재 누적된 자막들의 총 길이가 최대 청크 길이를 초과하면 저장 처리
        if (end_ms - current_start_ms) > MAX_CHUNK_DURATION_MS and current_text:
            chunk_filename = f"{video_id}_{chunk_count:04d}.wav"
            chunk_path = os.path.join(WAV_DIR, chunk_filename)
            
            # 앞뒤 안전 패딩 적용하여 자르기 범위 계산
            slice_start = max(0, current_start_ms - AUDIO_PADDING_MS)
            slice_end = min(len(audio), current_end_ms + AUDIO_PADDING_MS)
            
            # 오디오 잘라내기
            chunk_audio = audio[slice_start:slice_end]
            
            # 유효한 길이(최소 길이 이상)인 경우에만 파일로 저장
            if len(chunk_audio) >= MIN_CHUNK_DURATION_MS:
                chunk_audio.export(chunk_path, format="wav")
                metadata_entries.append({
                    "file_name": chunk_filename,
                    "transcription": current_text
                })
                chunk_count += 1
            
            # 변수들을 다음 청크를 위해 초기화
            current_start_ms = start_ms
            current_end_ms = end_ms
            current_text = text
            
        else:
            # 최대 길이에 도달하지 않았으면 텍스트를 계속 이어 붙임
            current_text = (current_text + " " + text).strip() if current_text else text
            current_end_ms = end_ms

    # 루프가 끝난 후 마지막으로 남은 자막 데이터 저장 처리
    if current_text:
        chunk_filename = f"{video_id}_{chunk_count:04d}.wav"
        chunk_path = os.path.join(WAV_DIR, chunk_filename)
        
        slice_start = max(0, current_start_ms - AUDIO_PADDING_MS)
        slice_end = min(len(audio), current_end_ms + AUDIO_PADDING_MS)
        
        chunk_audio = audio[slice_start:slice_end]
        
        if len(chunk_audio) >= MIN_CHUNK_DURATION_MS:
            chunk_audio.export(chunk_path, format="wav")
            metadata_entries.append({
                "file_name": chunk_filename,
                "transcription": current_text
            })

    return metadata_entries

def main():
    """전체 파이프라인의 시작점."""
    # 최신 영상 ID 목록 확보
    video_ids = get_latest_video_ids(CHANNEL_URL, MAX_VIDEOS)
    all_metadata = []
    
    # tqdm 라이브러리를 사용하여 처리 상황을 진행바(Progress Bar)로 표시
    for v_id in tqdm(video_ids, desc="[*] 비디오 처리 중", unit="영상"):
        # 각 영상별 전처리 수행
        entries = process_video(v_id)
        all_metadata.extend(entries)
        
        # [중간 저장] 예기치 못한 종료(메모리 부족, 네트워크 끊김 등) 시에도 데이터 유실 방지
        if all_metadata:
            df = pd.DataFrame(all_metadata)
            df.to_csv(METADATA_PATH, index=False, encoding='utf-8-sig')

    # 완료 리포트 출력
    print(f"\n🎉 파이프라인 완료! 생성된 완벽한 오디오 조각: {len(all_metadata)}개")
    print(f"💾 메타데이터 저장 위치: {METADATA_PATH}")

if __name__ == "__main__":
    # 스크립트 실행
    main()
