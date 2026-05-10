"""
scripts/prepare_validation.py
지정된 단일 유튜브 영상을 다운로드하여 30초 단위 검증 데이터셋을 구축함.
"""
import os
import sys
import pandas as pd

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data.scraper import download_video_data, date_to_folder
from src.data.processor import process_video
from src.core.config import DATASET_DIR
from src.utils import logger

def main():
    # 1. 목표 영상 정보 (사용자 지정)
    video_url = "https://www.youtube.com/watch?v=gZ1HlsRJV1w"
    video_id = "gZ1HlsRJV1w"
    date_str = "20260510" # 오늘 날짜 (검증용)
    
    # 검증셋 저장 경로 설정
    val_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "validation_set"))
    val_audio_dir = os.path.join(val_root, "audio")
    val_metadata_path = os.path.join(val_root, "metadata.csv")
    
    os.makedirs(val_audio_dir, exist_ok=True)

    with logger.dashboard_context():
        logger.info("=" * 50)
        logger.info("[검증셋 구축] 최신 영상 데이터 확보 시작")
        logger.info(f"URL: {video_url}")
        logger.info("=" * 50)

        # 2. 다운로드 (이미 있으면 스킵됨)
        logger.set_status("다운로드 중", f"영상 ID: {video_id}")
        video_dir = date_to_folder(date_str, video_id)
        a_path, v_path = download_video_data(video_id, video_dir)
        
        if not a_path or not v_path:
            logger.error("다운로드 실패!")
            return

        # 3. 전처리 및 분할 (30초 단위)
        logger.set_status("오디오 분할 중", "30초 단위 청킹 및 자막 병합")
        
        # process_video는 기본적으로 DATASET_DIR를 기준으로 작동하므로, 
        # 검증셋을 위해 잠시 설정을 바꾸거나 수동으로 경로를 조작함
        # 여기서는 편의상 dataset/validation_tmp 폴더에 생성 후 옮기는 방식을 택함
        entries = process_video(video_id, date_str, a_path, v_path, mode="basic")

        # 4. 검증셋 폴더로 정리
        logger.set_status("정리 중", "검증셋 폴더로 파일 이동")
        val_entries = []
        for entry in entries:
            old_rel_path = entry["file_name"] # 2026/05/10/id/chunks/chunk_0000.wav
            old_abs_path = os.path.join(DATASET_DIR, old_rel_path)
            
            # 새 파일명 생성
            new_filename = f"val_{os.path.basename(old_rel_path)}"
            new_abs_path = os.path.join(val_audio_dir, new_filename)
            
            # 파일 복사
            import shutil
            shutil.copy2(old_abs_path, new_abs_path)
            
            val_entries.append({
                "file_name": new_filename,
                "transcription": entry["transcription"]
            })

        # 5. CSV 저장
        df = pd.DataFrame(val_entries)
        df.to_csv(val_metadata_path, index=False, encoding="utf-8-sig")
        
    logger.stop_dashboard()
    print("\n" + "=" * 50)
    print(f"✅ 검증셋 구축 완료!")
    print(f"📍 오디오: {val_audio_dir}")
    print(f"📍 메타데이터: {val_metadata_path}")
    print(f"📊 총 샘플 수: {len(df)}개")
    print("=" * 50)

if __name__ == "__main__":
    main()
