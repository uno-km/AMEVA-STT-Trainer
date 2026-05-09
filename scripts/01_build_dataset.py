"""
scripts/01_build_dataset.py
[단계 1] 데이터셋 빌드 파이프라인 (병렬 처리 + 프리미엄 UI)
"""
import sys
import os
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Dict

# 프로젝트 루트를 Python 경로에 추가하여 src 모듈 임포트 가능하게 설정
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data.scraper   import scrape_channel
from src.data.processor import process_video
from src.data.validator import validate_dataset
from src.core.config    import METADATA_PATH
from src.utils          import logger

def main():
    # 실시간 대시보드 화면 활성화 (시스템 자원 및 진행 상황 모니터링)
    with logger.dashboard_context():
        logger.info("=" * 50)
        logger.info("[1단계] 데이터셋 빌드 시작 (Parallel & Rich)")
        logger.info("=" * 50)

        # 1. 유튜브 채널 정보 수집
        logger.set_status("유튜브 수집 중", "채널 목록 조회")
        # 설정된 채널에서 최신 영상 목록 및 오디오/자막 다운로드 수행
        video_list = scrape_channel()

        # 수집된 영상이 없는 경우 종료
        if not video_list:
            logger.warning("수집된 영상이 없습니다.")
            return

        # 2. 오디오 전처리 및 청크 분할 (멀티프로세싱 활용)
        logger.set_status("오디오 전처리 중", "병렬 처리 엔진 가동")
        # 모든 영상의 청크 정보를 모을 리스트
        all_entries = []
        # 시스템 코어 수에 따라 최대 병렬 작업 수 결정 (최대 8개)
        max_workers = min(os.cpu_count() or 4, 8)
        
        # 프로세스 풀 생성하여 병렬 처리 시작
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # 개별 영상에 대한 전처리 작업을 백그라운드 프로세스로 등록
            futures = {
                executor.submit(process_video, vid, date, a_path, v_path): vid 
                for vid, date, a_path, v_path in video_list if a_path and v_path
            }
            # 완료된 작업 수 카운트
            completed = 0
            # 작업이 완료되는 순서대로 결과 처리
            for future in as_completed(futures):
                vid = futures[future]
                completed += 1
                try:
                    # 전처리 결과(청크 정보 목록) 수신
                    entries = future.result()
                    if entries: 
                        all_entries.extend(entries)
                    # 작업 완료 알림 및 상태바 갱신
                    logger.success(f"[{completed}/{len(video_list)}] {vid} 완료")
                    logger.set_status("오디오 전처리 중", f"진행률: {completed}/{len(video_list)}")
                except Exception as e:
                    # 개별 영상 처리 중 발생한 오류 기록
                    logger.error(f"[{vid}] 에러: {e}")

        # 3. 메타데이터 저장
        # 수집된 모든 청크 정보를 데이터프레임으로 변환
        df = pd.DataFrame(all_entries if all_entries else [], columns=["file_name", "transcription"])
        # CSV 파일로 저장 (BOM 포함 UTF-8)
        df.to_csv(METADATA_PATH, index=False, encoding="utf-8-sig")

        # 4. 데이터셋 무결성 검수
        logger.set_status("검수 중")
        # 생성된 데이터셋의 파일 존재 여부 및 텍스트 품질 검증
        validate_dataset()
        logger.success("데이터셋 준비 완료")

if __name__ == "__main__":
    # 메인 함수 실행
    main()
