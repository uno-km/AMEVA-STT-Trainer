"""
scripts/legacy/make_dataset_raw.py
[백업] 데이터셋을 구축하기 위한 레거시 전처리 스크립트.
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
CHANNEL_URL = "https://www.youtube.com/@syukaworld/videos"
MAX_VIDEOS = 30
OUTPUT_DIR = "dataset"
WAV_DIR = os.path.join(OUTPUT_DIR, "wav")
RAW_DIR = os.path.join(OUTPUT_DIR, "raw")
METADATA_PATH = os.path.join(OUTPUT_DIR, "metadata.csv")

SAMPLE_RATE = 16000
MAX_CHUNK_DURATION_MS = 25000
MIN_CHUNK_DURATION_MS = 3000
AUDIO_PADDING_MS = 100

os.makedirs(WAV_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)

def get_latest_video_ids(channel_url, count=30):
    print(f"[*] 채널에서 최근 {count}개의 영상 ID를 가져옵니다: {channel_url}")
    cmd = [
        "yt-dlp",
        "--print", "id",
        "--playlist-items", f"1:{count}",
        "--flat-playlist",
        channel_url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[ERROR] 영상 ID를 가져오는 데 실패했습니다:", result.stderr)
        return []
    ids = result.stdout.strip().split('\n')
    return [vid for vid in ids if vid]

def download_audio(video_id):
    output_path = os.path.join(RAW_DIR, f"{video_id}.wav")
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return output_path
    
    cmd = [
        "yt-dlp",
        "-x", "--audio-format", "wav",
        "--audio-quality", "0",
        "--postprocessor-args", f"ffmpeg:-ar {SAMPLE_RATE} -ac 1",
        "-o", os.path.join(RAW_DIR, f"{video_id}.%(ext)s"),
        f"https://www.youtube.com/watch?v={video_id}"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        print(f"\n[ERROR] 오디오 생성 실패 ({video_id}):\n{result.stderr[:300]}")
        return None
    return output_path

def get_transcript(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            return transcript_list.find_transcript(['ko']).fetch()
        except:
            return transcript_list.find_generated_transcript(['ko']).fetch()
    except Exception as e:
        print(f"\n[WARNING] 자막을 가져올 수 없습니다 ({video_id}): {e}")
        return None

def clean_text(t: str) -> str:
    t = t.replace('\n', ' ').strip()
    t = re.sub(r"\[.*?\]|\(.*?\)", "", t)
    t = t.replace("♪", "").strip()
    t = re.sub(r"\s+", " ", t)
    return t

def process_video(video_id):
    audio_path = download_audio(video_id)
    transcript = get_transcript(video_id)
    if not audio_path or not transcript:
        return []

    try:
        audio = AudioSegment.from_wav(audio_path)
    except Exception as e:
        print(f"\n[ERROR] 오디오 파일을 읽을 수 없습니다 ({video_id}): {e}")
        return []

    metadata_entries = []
    current_text = ""
    current_start_ms = -1
    current_end_ms = 0
    chunk_count = 0
    
    for entry in transcript:
        start_ms = int(entry['start'] * 1000)
        end_ms = start_ms + int(entry['duration'] * 1000)
        
        text = clean_text(entry['text'])
        if not text:
            continue
            
        if current_start_ms == -1:
            current_start_ms = start_ms
            
        if (end_ms - current_start_ms) > MAX_CHUNK_DURATION_MS and current_text:
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
                chunk_count += 1
            
            current_start_ms = start_ms
            current_end_ms = end_ms
            current_text = text
        else:
            current_text = (current_text + " " + text).strip() if current_text else text
            current_end_ms = end_ms

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
    video_ids = get_latest_video_ids(CHANNEL_URL, MAX_VIDEOS)
    all_metadata = []
    for v_id in tqdm(video_ids, desc="[*] 비디오 처리 중", unit="영상"):
        entries = process_video(v_id)
        all_metadata.extend(entries)
        if all_metadata:
            df = pd.DataFrame(all_metadata)
            df.to_csv(METADATA_PATH, index=False, encoding='utf-8-sig')

    print(f"\n🎉 파이프라인 완료! 생성된 완벽한 오디오 조각: {len(all_metadata)}개")
    print(f"💾 메타데이터 저장 위치: {METADATA_PATH}")

if __name__ == "__main__":
    main()
