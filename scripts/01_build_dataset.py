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


def run_full_investigation(metadata_path=METADATA_PATH, dataset_dir=DATASET_DIR):
    """데이터셋 빌드 완료 후 품질 상태를 전수 조사하여 예쁘게 출력한다."""
    # [수정] 대시보드 종료 후 화면을 한 번 깨끗하게 밀어줌
    if os.name == 'nt': os.system('cls')
    else: os.system('clear')

    if not os.path.exists(metadata_path):
        logger.error(f"{metadata_path}를 찾을 수 없어 전수 조사를 건너뜁니다.")
        return

    df = pd.read_csv(metadata_path)
    total_records = len(df)
    
    # 1. 파일 존재 여부 확인
    missing_count = 0
    for fname in df['file_name']:
        if not os.path.exists(os.path.join(dataset_dir, fname)):
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
        logger.info("⚠️ 일부 데이터에 보정이 필요할 수 있습니다. 위 리포트를 참고해 주세요.")


def main():
    parser = argparse.ArgumentParser(description="AMEVA-STT Dataset Builder")
    parser.add_argument("--mode", type=str, default="basic", choices=["basic", "advanced"], help="전처리 모드 선택")
    parser.add_argument("--task-id", type=str, help="태스크 ID (자동화 연동용)")
    parser.add_argument("--source_type", type=str, default="youtube")
    parser.add_argument("--url", type=str, default="")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--folder", type=str, default="")
    parser.add_argument("--name", type=str, help="태스크 전용 폴더명")
    args = parser.parse_args()

    task_id = args.task_id or os.environ.get("CURRENT_TASK_ID")
    
    # [핵심] 태스크 전용 경로 설정 (데이터 격리)
    if args.name:
        target_dir = os.path.abspath(os.path.join("dataset", args.name))
        os.makedirs(target_dir, exist_ok=True)
        local_metadata_path = os.path.join(target_dir, "metadata.csv")
    else:
        target_dir = DATASET_DIR
        local_metadata_path = METADATA_PATH

    # 실시간 대시보드 화면 활성화
    with logger.dashboard_context():
        logger.info("=" * 50)
        logger.info(f"[1단계] 데이터셋 빌드 시작 (태스크: {task_id})")
        logger.info(f"출력 경로: {target_dir}")
        logger.info("=" * 50)

        # 1. 데이터 수집 (유튜브 혹은 폴더)
        logger.set_status("데이터 수집 중", "채널 목록 및 오디오 수집")
        video_list = []
        is_local = bool(args.folder) or (args.source_type == "local")

        if not is_local:
            video_list = scrape_channel(url=args.url, count=args.count)
        else:
            folder_path = args.folder
            logger.info(f"로컬 폴더 모드 가동: {folder_path}")
            if not os.path.exists(folder_path):
                logger.error(f"지정된 로컬 폴더가 존재하지 않습니다: {folder_path}")
                sys.exit(1)
            
            import glob
            from datetime import datetime
            today_str = datetime.today().strftime("%Y%m%d")
            
            # 폴더 내 모든 하위 경로에서 .wav 오디오 파일 재귀 탐색
            wav_files = glob.glob(os.path.join(folder_path, "**", "*.wav"), recursive=True)
            for wav_path in wav_files:
                # 렉 유도 방지: 이미 분할된 chunks 폴더 내부의 wav는 원본이 아니므로 제외
                if "chunks" in wav_path.replace("\\", "/").split("/"):
                    continue
                    
                parent_dir = os.path.dirname(wav_path)
                video_id = os.path.basename(parent_dir) # 폴더명이 곧 영상 ID (예: gZ1HlsRJV1w)
                
                # 해당 디렉토리 내에 있는 모든 .vtt 파일 리스팅
                local_vtts = glob.glob(os.path.join(parent_dir, "*.vtt"))
                vtt_path = None
                
                if local_vtts:
                    # 1순위: 파일명이 영상 ID로 시작하는 VTT 검색
                    for vf in local_vtts:
                        if os.path.basename(vf).startswith(video_id):
                            vtt_path = vf
                            break
                    # 2순위: 폴더 내에 자막이 단 1개만 있다면 무조건 매칭
                    if not vtt_path and len(local_vtts) == 1:
                        vtt_path = local_vtts[0]
                
                if vtt_path:
                    video_list.append((video_id, today_str, wav_path, vtt_path))
                    logger.info(f"로컬 파일 매칭 성공: {video_id} -> {os.path.basename(wav_path)} + {os.path.basename(vtt_path)}")
                else:
                    logger.info(f"⚠️ 자막(.vtt) 매칭 실패로 제외: {os.path.basename(wav_path)}")

        if not video_list:
            logger.info("⚠️ 수집된 영상이 없습니다.")
            sys.exit(1)

        # 2. 오디오 전처리 및 청크 분할
        logger.set_status("오디오 전처리 중", "병렬 처리 및 자막 병합")
        all_entries = []
        for i, (vid, date_str, a_path, v_path) in enumerate(video_list):
            if not a_path or not v_path: continue
            logger.set_status("오디오 전처리 중", f"[{i+1}/{len(video_list)}] {vid} 분할 중")
            # [수정] target_dir을 넘겨서 해당 폴더에 청크 저장
            entries = process_video(vid, date_str, a_path, v_path, mode=args.mode, output_dir=target_dir)
            all_entries.extend(entries)
        # 3. metadata.csv 저장 (격리된 폴더에 저장)
        if all_entries:
            df = pd.DataFrame(all_entries)
            df.to_csv(local_metadata_path, index=False, encoding="utf-8-sig")
            logger.info(f"메타데이터 저장 완료: {len(df)}개 레코드 -> {local_metadata_path}")

            # 4. 데이터셋 검수
            logger.set_status("검수 중", "데이터 무결성 검증")
            validate_dataset(metadata_path=local_metadata_path, dataset_dir=target_dir)
            
            # 리포트 출력 (격리된 경로 기준)
            run_full_investigation(local_metadata_path, target_dir)
            logger.success(f"--- [1단계 완료] 태스크 {task_id} 데이터셋 구축 성공 ---")
        else:
            logger.error("데이터셋 구축 실패: 생성된 데이터가 없습니다.")
            sys.exit(1)

if __name__ == "__main__":
    main()
