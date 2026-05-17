import os
import pandas as pd
import re
from rich.console import Console
from rich.table import Table

console = Console()

def run_qa(metadata_path: str):
    if not os.path.exists(metadata_path):
        console.print(f"[red]에러: 메타데이터 파일을 찾을 수 없습니다: {metadata_path}[/red]")
        return

    # 1. 데이터 로드 및 정렬 (파일명 순으로 정렬해야 인접 청크 비교 가능)
    df = pd.read_csv(metadata_path)
    df = df.sort_values("file_name").reset_index(drop=True)
    total_samples = len(df)
    
    # 2. 중복(Overlap) 탐지 강화 (최대 30자까지 탐색)
    overlap_count = 0
    def _norm(s): return re.sub(r"\s+", "", str(s))

    for i in range(len(df) - 1):
        curr_text = _norm(df.iloc[i]['transcription'])
        next_text = _norm(df.iloc[i+1]['transcription'])
        
        found = False
        for length in range(30, 4, -1):
            if curr_text.endswith(next_text[:length]):
                found = True
                break
        if found:
            overlap_count += 1

    # 3. 구두점 띄어쓰기 오류 (콤마 포함 정밀 검사)
    punct_errors = df['transcription'].str.contains(r'[,\.?!][가-힣a-zA-Z]', regex=True).sum()

    # 4. CPS (Characters Per Second) 체크 - 텍스트 밀도 확인
    # (오디오 파일 길이를 읽지 못하는 환경을 고려하여 텍스트 기반 추정 지표 제공)
    df['text_len'] = df['transcription'].apply(lambda x: len(str(x)))
    avg_len = df['text_len'].mean()
    too_short = (df['text_len'] < 5).sum()
    
    # 5. 특수 기호 및 괄호 잔존 체크 (학습 정합성 방해 요소)
    symbol_count = df['transcription'].str.contains(r'[%$]', regex=True).sum()
    paren_count = df['transcription'].str.contains(r'[\(\)\[\]]', regex=True).sum()

    # 리포트 출력
    table = Table(title="🛡️ AMEVA-STT 데이터셋 품질 검증 리포트 (Pro)")
    table.add_column("검사 항목", style="cyan")
    table.add_column("결과 수치", style="magenta")
    table.add_column("판정", style="bold")

    table.add_row("전체 샘플 수", f"{total_samples}개", "OK")
    table.add_row("청크 간 텍스트 중복 (Fuzzy)", f"{overlap_count}건", "✅" if overlap_count == 0 else "⚠️ 위험")
    table.add_row("구두점 뒤 띄어쓰기 오류", f"{punct_errors}건", "✅" if punct_errors == 0 else "⚠️ 수정필요")
    table.add_row("미치환 특수기호 (%$)", f"{symbol_count}건", "✅" if symbol_count == 0 else "⚠️ 발견")
    table.add_row("라벨 내 괄호 잔존 (())", f"{paren_count}건", "✅" if paren_count == 0 else "⚠️ 정합성위험")
    table.add_row("너무 짧은 문장 (<5자)", f"{too_short}건", "✅" if too_short == 0 else "⚠️ 체크요망")
    table.add_row("평균 문장 길이", f"{avg_len:.1f}자", "-")

    console.print(table)
    
    if overlap_count > 0 or punct_errors > 0 or paren_count > 0:
        console.print("[bold yellow]💡 조치 필요:[/bold yellow] 전처리 엔진(processor.py)이 업데이트되었습니다. [bold cyan]01_build_dataset.py[/bold cyan]를 다시 실행하여 데이터셋을 갱신하십시오.")
    else:
        console.print("[bold green]✨ 축하합니다! 모든 검증을 통과했습니다. 최상의 정합성을 가진 데이터셋입니다.[/bold green]")

if __name__ == "__main__":
    default_path = r"C:\ameva\AMEVA-STT-Trainer\dataset\metadata.csv"
    run_qa(default_path)
