"""
scripts/02_start_training.py
[단계 2] Whisper LoRA 학습을 시작한다.
시스템 자원(RAM) 점검 및 사용자 승인 절차 포함.
사용법: python scripts/02_start_training.py [--skip]
"""
import sys
import os
import psutil
import argparse
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

def check_resources(skip_confirm: bool = False) -> bool:
    """학습 시작 전 RAM 점유율 및 상위 프로세스 정보를 출력한다."""
    vm = psutil.virtual_memory()
    total_gb = vm.total / (1024**3)
    used_gb  = vm.used / (1024**3)
    free_gb  = vm.available / (1024**3)
    pct      = vm.percent

    # 상위 메모리 점유 프로세스 추출 (Top 5)
    processes = []
    for proc in psutil.process_iter(['name', 'memory_info']):
        try:
            mem = proc.info['memory_info'].rss / (1024**3)
            processes.append((proc.info['name'], mem))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    top_procs = sorted(processes, key=lambda x: x[1], reverse=True)[:5]

    proc_table = Table(box=None, show_header=False, width=50)
    proc_table.add_column("Process", style="cyan")
    proc_table.add_column("Usage", justify="right", style="bold yellow")
    
    for name, mem in top_procs:
        proc_table.add_row(f" • {name[:20]}", f"{mem:.2f} GB")

    summary = Table.grid(expand=True)
    summary.add_column(ratio=1)
    summary.add_row(f"[bold white]전체 메모리:[/] [dim]{total_gb:>38.2f} GB[/]")
    summary.add_row(f"[bold white]사용 중인 메모리:[/] [orange1]{used_gb:>34.2f} GB ({pct}%) [/]")
    summary.add_row(f"[bold white]여유 메모리:[/] [green]{free_gb:>38.2f} GB[/]")
    summary.add_row("")
    summary.add_row("[bold cyan] 메모리 점유 TOP 5 프로세스[/]")
    summary.add_row(proc_table)

    status_msg = "위험 (정리 필요)" if pct > 90 else ("주의" if pct > 80 else "양호")
    status_color = "red" if pct > 90 else ("yellow" if pct > 80 else "green")

    panel = Panel(
        summary,
        title="[bold cyan] 학습 전 시스템 자원 점검[/]",
        subtitle=f"[bold {status_color}]상태: {status_msg}[/]",
        padding=(1, 2),
        border_style="cyan"
    )

    console.print("\n")
    console.print(panel)
    
    if skip_confirm:
        logger.info("--skip 옵션으로 인해 승인 절차를 건너뜁니다.")
        return True
        
    return Confirm.ask("\n[bold white]그래도 진행할까요?[/]")

def main():
    parser = argparse.ArgumentParser(description="AMEVA-STT Training Script")
    parser.add_argument("--skip", action="store_true", help="기존 데이터셋 생성을 건너뛰고 학습만 시작")
    parser.add_argument("--resume_from_checkpoint", type=str, default=None, help="학습을 재개할 체크포인트 경로")
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("[2단계] Whisper LoRA 학습 시작")
    logger.info("=" * 50)

    # 1. 시스템 자원 확인 (skip 옵션 전달)
    if not check_resources(skip_confirm=args.skip):
        logger.warning("사용자가 학습을 취소했습니다.")
        return

    # 2. WandB 초기화 (설정된 경우)
    if CFG["wandb"]["enabled"]:
        import wandb
        os.environ["WANDB_PROJECT"] = CFG["wandb"]["project"]
        os.environ["WANDB_MODE"] = CFG["wandb"]["mode"]
        wandb.init(
            project=CFG["wandb"]["project"],
            config=CFG,
            name=f"Roadmap-{CFG['model_id'].split('/')[-1]}-Step{CFG['max_steps']}"
        )
        logger.info(f"[WandB] '{CFG['wandb']['project']}' 프로젝트로 로그 전송 시작 (Mode: {CFG['wandb']['mode']})")

    # 3. 학습 실행
    try:
        run_training(resume_from_checkpoint=args.resume_from_checkpoint)
    except Exception as e:
        logger.error(f"학습 도중 오류 발생: {e}")
    finally:
        if CFG["wandb"]["enabled"]:
            import wandb
            wandb.finish()

if __name__ == "__main__":
    main()
