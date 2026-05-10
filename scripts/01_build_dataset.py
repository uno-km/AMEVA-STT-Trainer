"""
scripts/01_build_dataset.py
[단계 1] 유튜브 데이터 수집 및 전처리 파이프라인.

기능:
  1. 유튜브 채널에서 최신 영상 목록 확보
  2. 오디오(WAV) 및 자막(VTT) 다운로드
  3. 자막 기반 오디오 청크 분할 및 텍스트 정제 (중복 제거 포함)
  4. 데이터셋 품질 전수 검사 및 리포트 출력
"""
import sys
import os
import pandas as pd
from collections import Counter
from rich.table import Table
from rich.panel import Panel
import argparse

# 프로젝트 루트 디렉터리를 Python 경로에 등록
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data.scraper   import scrape_channel
from src.data.processor import process_video
from src.data.validator import validate_dataset
from src.core.config    import METADATA_PATH, DATASET_DIR
from src.utils          import logger


def run_full_investigation():
    """데이터셋 빌드 완료 후 품질 상태를 전수 조사하여 예쁘게 출력한다."""
    # [수정] 대시보드 종료 후 화면을 한 번 깨끗하게 밀어줌
    if os.name == 'nt': os.system('cls')
    else: os.system('clear')

    if not os.path.exists(METADATA_PATH):
        logger.error("metadata.csv를 찾을 수 없어 전수 조사를 건너뜁니다.")
        return

    df = pd.read_csv(METADATA_PATH)
    total_records = len(df)
    
    # 1. 파일 존재 여부 확인
    missing_count = 0
    for fname in df['file_name']:
        if not os.path.exists(os.path.join(DATASET_DIR, fname)):
            missing_count += 1
    
    # 2. 텍스트 중복(말더듬) 분석 - 더 엄격한 기준으로 검사
    stutter_count = 0
    for text in df['transcription'].fillna(""):
        words = str(text).split()
        if len(words) > 5:
            # 3글자 이상의 연속된 단어 뭉치가 반복되는지 확인
            trigrams = [" ".join(words[i:i+3]) for i in range(len(words)-2)]
            if trigrams:
                _, tri_count = Counter(trigrams).most_common(1)[0]
                if tri_count > 1: stutter_count += 1

    # 3. 날짜 누락 분석
    na_count = df[df['file_name'].str.startswith('NA', na=False)].shape[0]

    # 결과 표 생성 (디자인 개선)
    table = Table(title="[bold cyan]✨ AMEVA-STT 최종 데이터셋 품질 리포트[/]", show_header=True, header_style="bold magenta", border_style="bright_blue")
    table.add_column("검사 항목", style="white")
    table.add_column("측정치", justify="right", style="cyan")
    table.add_column("판정", justify="center")

    # 무결성 행
    integrity_status = "[bold green]PERFECT[/]" if missing_count == 0 else "[bold red]MISSING[/]"
    table.add_row("전체 데이터 수", f"{total_records}개", "-")
    table.add_row("파일 무결성", f"{total_records - missing_count}/{total_records}", integrity_status)
    
    # 중복도 행 (5% 미만이면 사실상 CLEAN)
    stutter_ratio = (stutter_count/total_records) * 100
    if stutter_ratio < 1.0: stutter_status = "[bold green]EXCELLENT[/]"
    elif stutter_ratio < 5.0: stutter_status = "[bold green]CLEAN[/]"
    else: stutter_status = "[bold yellow]NEED-CHECK[/]"
    
    table.add_row("텍스트 중복도", f"{stutter_ratio:.1f}% ({stutter_count}건)", stutter_status)
    
    # 날짜 행
    date_status = "[bold green]VALIDATED[/]" if na_count == 0 else "[bold yellow]UNKNOWN[/]"
    table.add_row("날짜 정보 무결성", f"{total_records - na_count}/{total_records}", date_status)

    logger.console.print("\n" * 2)
    logger.console.print(table)
    logger.console.print("\n")
    
    if stutter_ratio < 5.0 and missing_count == 0:
        logger.success("🎊 축하합니다! 데이터셋이 최상의 상태로 준비되었습니다. 이제 02단계 학습을 시작하세요!")
    else:
        logger.warning("일부 데이터에 보정이 필요할 수 있습니다. 위 리포트를 참고해 주세요.")


def main():
    parser = argparse.ArgumentParser(description="AMEVA-STT Dataset Builder")
    parser.add_argument("--mode", type=str, default="basic", choices=["basic", "advanced"], help="전처리 모드 선택 (basic: 25초 고정, advanced: 15초 스마트)")
    args = parser.parse_args()

    # 실시간 대시보드 화면 활성화
    with logger.dashboard_context():
        logger.info("=" * 50)
        logger.info(f"[1단계] 데이터셋 빌드 시작 (모드: {args.mode.upper()})")
        logger.info("=" * 50)

        # 1. 유튜브 채널 정보 수집 및 다운로드
        logger.set_status("유튜브 수집 중", "채널 목록 및 오디오 수집")
        video_list = scrape_channel()

        if not video_list:
            logger.warning("수집된 영상이 없습니다.")
            return

        # 2. 오디오 전처리 및 청크 분할
        logger.set_status("오디오 전처리 중", "병렬 처리 및 자막 병합")
        all_entries = []
        for i, (vid, date_str, a_path, v_path) in enumerate(video_list):
            if not a_path or not v_path:
                continue
            
            # 진행 상황 업데이트
            logger.set_status("오디오 전처리 중", f"[{i+1}/{len(video_list)}] {vid} 분할 중")
            
            # 자막 중복 제거 및 청크 생성 로직 실행 (모드 전달)
            entries = process_video(vid, date_str, a_path, v_path, mode=args.mode)
            all_entries.extend(entries)

        # 3. metadata.csv 저장
        if all_entries:
            df = pd.DataFrame(all_entries)
            df.to_csv(METADATA_PATH, index=False, encoding="utf-8-sig")
            logger.info(f"메타데이터 저장 완료: {len(df)}개 레코드")

            # 4. 데이터셋 검수 (기존 검수 로직)
            logger.set_status("검수 중", "데이터 무결성 검증")
            validate_dataset()
        else:
            logger.error("생성된 데이터셋 레코드가 없습니다.")

    # [수정] 대시보드 종료 및 플래그 초기화
    logger.stop_dashboard()
    
    # 이제 터미널에 리포트 출력 (화면 고정)
    run_full_investigation()
    logger.success("데이터셋 준비 프로세스 종료")


if __name__ == "__main__":
    main()
