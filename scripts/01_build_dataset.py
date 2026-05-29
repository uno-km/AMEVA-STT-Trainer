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

# --- FFmpeg 경로 자동 등록 (pydub 경고 방지) ---
FFMPEG_C_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
FFMPEG_BIN_DIR = os.path.dirname(FFMPEG_C_PATH)
if os.path.exists(FFMPEG_C_PATH):
    if FFMPEG_BIN_DIR not in os.environ.get("PATH", ""):
        os.environ["PATH"] = FFMPEG_BIN_DIR + os.pathsep + os.environ.get("PATH", "")

import pandas as pd
from collections import Counter
from rich.table import Table
from rich.panel import Panel
import argparse

# 프로젝트 루트 디렉터리를 Python 경로에 등록
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data.scraper   import scrape_channel
from src.data.processor import process_video, estimate_video_chunks
from src.data.validator import validate_dataset
from src.core.config    import METADATA_PATH, DATASET_DIR
from src.utils          import logger


def run_full_investigation(metadata_path=METADATA_PATH, dataset_dir=DATASET_DIR):
    """데이터셋 빌드 완료 후 품질 상태를 전수 조사하여 구체적인 진단 내역과 함께 출력한다."""
    # 대시보드 종료 후 화면을 한 번 깨끗하게 밀어줌
    if os.name == 'nt': os.system('cls')
    else: os.system('clear')

    if not os.path.exists(metadata_path):
        logger.error(f"{metadata_path}를 찾을 수 없어 전수 조사를 건너뜁니다.")
        return

    df = pd.read_csv(metadata_path)
    total_records = len(df)
    
    # 1. 파일 존재 여부 및 오디오 물리 통계 수집
    from pydub import AudioSegment
    import numpy as np
    import re
    
    missing_count = 0
    durations = []
    cps_list = []
    dbfs_list = []
    
    # 중복 감지 상세 내역용 리스트
    repetition_samples = []
    stutter_count = 0
    
    col_name = 'transcription_clean' if 'transcription_clean' in df.columns else 'transcription'
    raw_col_name = 'transcription'
    
    for idx, row in df.iterrows():
        file_name = row['file_name']
        abs_path = os.path.join(dataset_dir, file_name)
        
        if not os.path.exists(abs_path):
            missing_count += 1
            continue
            
        # 1-1. 오디오 정보 및 통계 추출
        try:
            audio = AudioSegment.from_wav(abs_path)
            dur_sec = len(audio) / 1000.0
            durations.append(dur_sec)
            
            clean_text = str(row.get(col_name, "")).strip()
            raw_text = str(row.get(raw_col_name, "")).strip()
            
            if dur_sec > 0:
                cps_list.append(len(clean_text) / dur_sec)
            dbfs_list.append(audio.dBFS if audio.dBFS != float('-inf') else -96.0)
        except Exception:
            continue
            
        # 1-2. 구어체 연속 반복(adjacent n-gram) 상세 분석
        words = [w for w in clean_text.split() if w and re.match(r'^[a-zA-Z0-9가-힣]+$', w)]
        if len(words) >= 2:
            has_repeat = False
            repeated_pattern = None
            repeat_n = 0
            for n in (1, 2, 3):
                if len(words) >= n * 2:
                    grams = [tuple(words[i:i+n]) for i in range(len(words)-n+1)]
                    for i in range(len(grams) - n):
                        if grams[i] == grams[i+n]:
                            has_repeat = True
                            repeated_pattern = " ".join(grams[i])
                            repeat_n = n
                            break
                if has_repeat:
                    break
            if has_repeat:
                stutter_count += 1
                if len(repetition_samples) < 5:
                    repetition_samples.append({
                        "file_name": file_name,
                        "pattern": repeated_pattern,
                        "n": repeat_n,
                        "text": raw_text
                    })

    # 2. 날짜 누락 분석
    na_count = df[df['file_name'].str.startswith('NA', na=False)].shape[0]

    # 3. 기술 통계량 연산
    avg_dur = np.mean(durations) if durations else 0.0
    med_dur = np.median(durations) if durations else 0.0
    min_dur = np.min(durations) if durations else 0.0
    max_dur = np.max(durations) if durations else 0.0
    
    avg_cps = np.mean(cps_list) if cps_list else 0.0
    med_cps = np.median(cps_list) if cps_list else 0.0
    max_cps = np.max(cps_list) if cps_list else 0.0
    
    avg_dbfs = np.mean(dbfs_list) if dbfs_list else 0.0
    med_dbfs = np.median(dbfs_list) if dbfs_list else 0.0

    # 결과 리포트 출력용 Rich 콘솔 가동
    from rich.console import Console
    console = Console()

    console.print("\n[bold cyan]======================================================================[/]")
    console.print("[bold white]  AMEVA-STT Preprocessing Pipeline Deep Profiler[/]")
    console.print("[bold cyan]======================================================================[/]\n")

    # [1] 전체 요약 검수 표
    table = Table(title="[bold yellow]Dataset Verification Summary[/]", show_header=True, header_style="bold magenta", border_style="bright_blue")
    table.add_column("검사항목", style="white")
    table.add_column("측정치", justify="right", style="cyan")
    table.add_column("판정", justify="center")

    integrity_status = "[bold green]PERFECT[/]" if missing_count == 0 else "[bold red]MISSING[/]"
    table.add_row("전체 데이터 수", f"{total_records}개", "-")
    table.add_row("오디오 무결성 (WAV 존재)", f"{total_records - missing_count}/{total_records}", integrity_status)
    
    stutter_ratio = (stutter_count / total_records) * 100 if total_records > 0 else 0.0
    table.add_row("텍스트 연속 반복 (1~3gram)", f"{stutter_ratio:.1f}% ({stutter_count}건)", "[bold green]INFO[/]")
    
    date_status = "[bold green]VALIDATED[/]" if na_count == 0 else "[bold yellow]UNKNOWN[/]"
    table.add_row("날짜 정보 무결성", f"{total_records - na_count}/{total_records}", date_status)

    console.print(table)
    console.print()

    # [2] 물리 데이터 분포 상세 통계
    console.print("[bold yellow]  [1] 물리 데이터 분포 상세 통계 (Physical Distribution Stats)[/]")
    console.print(f"  * [bold white]총 학습 오디오 시간 (Total Length)[/]: {sum(durations)/60:.2f}분 ({sum(durations)/3600:.3f}시간)")
    console.print(f"  * [bold white]세그먼트 길이 (Duration)[/]: 평균 {avg_dur:.2f}초 | 중앙값 {med_dur:.2f}초 | 최소 {min_dur:.2f}초 | 최대 {max_dur:.2f}초")
    console.print(f"  * [bold white]발화 속도/텍스트 밀도 (CPS)[/]: 평균 {avg_cps:.2f}자/초 | 중앙값 {med_cps:.2f}자/초 (최대 {max_cps:.2f}자/초)")
    console.print(f"  * [bold white]오디오 음량 에너지 (dBFS)[/]: 평균 {avg_dbfs:.2f} dBFS | 중앙값 {med_dbfs:.2f} dBFS (Peak Normalization 완료)")
    console.print()

    # [3] 구어체 인접 연속 반복(Adjacent Repetition) 상세 검출 샘플 (Top 5 Chunks)
    console.print("[bold yellow]  [2] 구어체 인접 연속 반복 감지 상세 내역 (Adjacent Repetitive Patterns - Top 5 Chunks)[/]")
    if repetition_samples:
        for idx, sample in enumerate(repetition_samples, 1):
            console.print(f"  {idx}. [bold cyan]{sample['file_name']}[/] | 반복 패턴: [bold magenta]\"{sample['pattern']}\"[/] ([bold yellow]{sample['n']}-gram[/] 연속 반복)")
            console.print(f"     └─ 원문: \"{sample['text']}\"")
    else:
        console.print("  * 감지된 연속 반복 단어/단어구가 없습니다.")
    console.print()

    # [4] 상위 3개 데이터 샘플 등록 로그
    console.print("[bold yellow]  [3] 생성된 청크 데이터 상위 3개 레코드 샘플 (Top 3 Chunks Registry)[/]")
    for i in range(min(3, total_records)):
        row = df.iloc[i]
        console.print(f"  * [[bold green]Sample {i+1}[/]] [bold cyan]{row['file_name']}[/]")
        console.print(f"    └─ 정제 텍스트: \"{row[col_name]}\"")
    console.print()

    console.print("[bold cyan]======================================================================[/]")
    logger.success("데이터셋 전처리 및 무결성 정밀 프로파일링 완료.")
    console.print("[bold cyan]======================================================================[/]\n")


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
            logger.info(f"▶ [데이터 수집 시작] 유튜브 채널 URL '{args.url}' 에서 최신 {args.count}개 영상을 분석 및 수집하기 시작합니다.")
        else:
            logger.info(f"▶ [데이터 수집 시작] 로컬 폴더 '{args.folder}' 에서 파일 스캔 및 매칭을 시작합니다.")

        if not is_local:
            video_list = scrape_channel(url=args.url, count=args.count, target_dir=target_dir)
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
        processed_vids = set()
        
        # --- 1단계 이어하기 보존 (Incremental Load) ---
        if os.path.exists(local_metadata_path):
            try:
                existing_df = pd.read_csv(local_metadata_path)
                def extract_vid(path_str):
                    parts = path_str.replace("\\", "/").split("/")
                    return parts[-3] if len(parts) >= 5 else None
                vids = existing_df['file_name'].apply(extract_vid).dropna().unique()
                processed_vids.update(vids)
                all_entries.extend(existing_df.to_dict('records'))
                logger.info(f"▶ 기존 메타데이터 발견! ({len(existing_df)}개 청크, {len(processed_vids)}개 영상). 이어서 전처리를 시작합니다.")
            except Exception as e:
                logger.warning(f"기존 메타데이터 로드 실패: {e}")

        # 글로벌 파이프라인 이벤트 카운터 초기화
        from src.data.processor import PIPELINE_COUNTERS
        PIPELINE_COUNTERS["invalid_timestamp_skip"] = 0
        PIPELINE_COUNTERS["overlap_clamp_count"] = 0
        PIPELINE_COUNTERS["post_clamp_skip"] = 0
        PIPELINE_COUNTERS["too_short_chunk_drop"] = 0

        # 청킹 개수 고속 시뮬레이션 예측 계산
        logger.info("▶ [전처리 준비] 자막 파일 분석을 통한 예상 총 청크 개수 계산 중...")
        total_expected_chunks = 0
        for vid, date_str, a_path, v_path in video_list:
            if vid in processed_vids: continue
            if v_path and os.path.exists(v_path):
                total_expected_chunks += estimate_video_chunks(v_path)
        logger.info(f"▶ [전처리 준비 완료] 전체 {len(video_list)}개 자막 스트림 분석 완료. 예상 최종 청크 수: {total_expected_chunks}개")

        completed_chunks = 0
        last_logged_pct = -10

        for i, (vid, date_str, a_path, v_path) in enumerate(video_list):
            if not a_path or not v_path: continue
            if vid in processed_vids:
                logger.info(f"▶ [SKIP] 이미 전처리 완료된 영상입니다: {vid}")
                continue
            logger.set_status("오디오 전처리 중", f"[{i+1}/{len(video_list)}] {vid} 분할 중")
            # [수정] target_dir을 넘겨서 해당 폴더에 청크 저장
            entries = process_video(vid, date_str, a_path, v_path, mode=args.mode, output_dir=target_dir)
            all_entries.extend(entries)
            
            # 실시간 진행률 및 마일스톤 로그 출력
            completed_chunks += len(entries)
            pct = (completed_chunks / total_expected_chunks) * 100 if total_expected_chunks > 0 else 0
            logger.info(f"▶ [청킹 진행] [{i+1}/{len(video_list)}] 영상 '{vid}' 분할 완료 (+{len(entries)}개 청크) -> 누적 {completed_chunks}/{total_expected_chunks}개 ({pct:.1f}%)")
            
            # --- 중간 저장 (Incremental Save) ---
            df_temp = pd.DataFrame(all_entries)
            df_temp.to_csv(local_metadata_path, index=False, encoding="utf-8-sig")
            
            # 10% 마일스톤 돌파 감지 및 알림
            current_10_block = int(pct // 10) * 10
            if current_10_block > last_logged_pct:
                logger.info(f"▶ [청킹 마일스톤] 전체 데이터셋 전처리 {current_10_block}% 완료! (현재 누적 {completed_chunks}개 청크 가공 완료)")
                last_logged_pct = current_10_block
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
            
            # --- DB tb_chunk 동기화 ---
            if task_id:
                try:
                    from src.backend.core.database import db_manager
                    from datetime import datetime
                    with db_manager.get_connection() as conn:
                        cur = conn.cursor()
                        create_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        for entry in all_entries:
                            cur.execute('''
                                INSERT INTO tb_chunk (task_id, chunk_path, transcript, create_dt)
                                VALUES (?, ?, ?, ?)
                            ''', (task_id, entry['file_name'], entry.get('transcription_clean', entry.get('transcription')), create_dt))
                        conn.commit()
                        logger.info(f"▶ DB tb_chunk 동기화 완료 ({len(all_entries)}개 청크)")
                except Exception as e:
                    logger.warning(f"tb_chunk DB 동기화 실패: {e}")

            logger.success(f"--- [1단계 완료] 태스크 {task_id} 데이터셋 구축 성공 ---")
        else:
            logger.error("데이터셋 구축 실패: 생성된 데이터가 없습니다.")
            sys.exit(1)

if __name__ == "__main__":
    main()
