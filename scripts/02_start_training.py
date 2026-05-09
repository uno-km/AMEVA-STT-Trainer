"""
scripts/02_start_training.py
[단계 2] LoRA 학습 실행 엔트리 포인트.

- 이미 저장된 체크포인트가 있으면 자동으로 이어서 학습한다.
- 학습 시작 전 데이터셋 존재 여부 및 시스템 자원(RAM)을 사전 점검한다.
"""
import sys
import os
import psutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm

# 프로젝트 루트 디렉터리를 Python 경로에 등록
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.training.trainer import run_training
from src.core.config      import METADATA_PATH
from src.utils            import logger

console = Console()

def check_resources():
    """학습 시작 전 시스템 자원(RAM) 상태를 점검하고 사용자 승인을 받는다."""
    mem = psutil.virtual_memory()
    total_gb = mem.total / 1024**3
    used_gb = mem.used / 1024**3
    free_gb = mem.available / 1024**3
    percent = mem.percent

    # 상태에 따른 색상 결정
    color = "green"
    if percent >= 90:
        color = "red"
    elif percent >= 80:
        color = "yellow"

    # 시각적인 테이블 생성
    table = Table.grid(expand=True)
    table.add_column(justify="left")
    table.add_column(justify="right")
    
    table.add_row("전체 메모리:", f"{total_gb:.2f} GB")
    table.add_row("사용 중인 메모리:", f"[{color}]{used_gb:.2f} GB ({percent}%)[/]")
    table.add_row("여유 메모리:", f"{free_gb:.2f} GB")
    
    # 예쁜 패널로 출력
    console.print("\n")
    console.print(Panel(
        table,
        title="[bold cyan]🚀 학습 전 시스템 자원 점검[/]",
        border_style=color,
        padding=(1, 2),
        subtitle=f"[bold {color}]상태: {'위험' if percent >= 90 else '주의' if percent >= 80 else '양호'}[/]"
    ))

    if percent >= 80:
        console.print(f"[bold yellow]⚠️  메모리 사용량이 {percent}%로 높습니다. 불필요한 앱(브라우저 등)을 종료하는 것을 권장합니다.[/]")
    
    # 사용자 승인 요청
    return Confirm.ask("\n[bold white]학습을 시작할까요?[/]")

def main():
    # 1. 시스템 자원 체크 (대시보드 시작 전)
    if not check_resources():
        console.print("[bold red]학습이 사용자에 의해 취소되었습니다.[/]")
        sys.exit(0)

    # 2. 실시간 모니터링 대시보드 환경 구축
    with logger.dashboard_context():
        logger.info("=" * 50)
        logger.info("[2단계] LoRA 학습 시작")
        logger.info("=" * 50)

        # 데이터셋 무결성 사전 점검
        if not os.path.exists(METADATA_PATH):
            logger.error(f"metadata.csv 없음: {METADATA_PATH}")
            logger.error("먼저 01_build_dataset.py를 실행하세요.")
            sys.exit(1)

        # 학습 파이프라인 가동
        run_training()

        # 종료 알림
        logger.success("=" * 50)
        logger.success("[2단계] 학습 완료")
        logger.success("=" * 50)


if __name__ == "__main__":
    main()
