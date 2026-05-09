"""
scripts/02_start_training.py
[단계 2] Whisper LoRA 학습을 시작한다.
시스템 자원(RAM) 점검 및 사용자 승인 절차 포함.
"""
import sys
import os
import psutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm

# 프로젝트 루트를 Python 경로에 등록
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.training.trainer import run_training
from src.core.config import CFG
from src.utils import logger

console = Console()

def check_resources() -> bool:
    """학습 시작 전 RAM 점유율 및 상위 프로세스 정보를 출력하고 승인을 받는다."""
    vm = psutil.virtual_memory()
    total_gb = vm.total / (1024**3)
    used_gb  = vm.used / (1024**3)
    free_gb  = vm.available / (1024**3)
    pct      = vm.percent

    # 상위 메모리 점유 프로세스 추출 (Top 5)
    processes = []
    for proc in psutil.process_iter(['name', 'memory_info']):
        try:
            # RSS (Resident Set Size) 사용
            mem = proc.info['memory_info'].rss / (1024**3)
            processes.append((proc.info['name'], mem))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    # 메모리 사용량 순으로 정렬 후 상위 5개 추출
    top_procs = sorted(processes, key=lambda x: x[1], reverse=True)[:5]

    # 프로세스 리스트 테이블 생성
    proc_table = Table(box=None, show_header=False, width=50)
    proc_table.add_column("Process", style="cyan")
    proc_table.add_column("Usage", justify="right", style="bold yellow")
    
    for name, mem in top_procs:
        proc_table.add_row(f" • {name[:20]}", f"{mem:.2f} GB")

    # 통합 정보 레이아웃
    summary = Table.grid(expand=True)
    summary.add_column(ratio=1)
    
    # 1. 기본 통계
    summary.add_row(f"[bold white]전체 메모리:[/] [dim]{total_gb:>38.2f} GB[/]")
    summary.add_row(f"[bold white]사용 중인 메모리:[/] [orange1]{used_gb:>34.2f} GB ({pct}%) [/]")
    summary.add_row(f"[bold white]여유 메모리:[/] [green]{free_gb:>38.2f} GB[/]")
    summary.add_row("")
    summary.add_row("[bold cyan]📊 메모리 점유 TOP 5 프로세스[/]")
    summary.add_row(proc_table)

    status_msg = "위험 (정리 필요)" if pct > 90 else ("주의" if pct > 80 else "양호")
    status_color = "red" if pct > 90 else ("yellow" if pct > 80 else "green")

    panel = Panel(
        summary,
        title="[bold cyan]🚀 학습 전 시스템 자원 점검[/]",
        subtitle=f"[bold {status_color}]상태: {status_msg}[/]",
        padding=(1, 2),
        border_style="cyan"
    )

    console.print("\n")
    console.print(panel)
    
    return Confirm.ask("\n[bold white]그래도 진행할까요?[/]")

def main():
    logger.info("=" * 50)
    logger.info("[2단계] Whisper LoRA 학습 시작")
    logger.info("=" * 50)

    # 1. 시스템 자원 확인
    if not check_resources():
        logger.warning("사용자가 학습을 취소했습니다.")
        return

    # 2. 학습 실행 (메인 로직 호출)
    try:
        run_training()
    except Exception as e:
        logger.error(f"학습 도중 오류 발생: {e}")

if __name__ == "__main__":
    main()
