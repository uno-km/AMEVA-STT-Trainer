"""
src/utils/logger.py
Rich 라이브러리를 활용한 프리미엄 고정형 대시보드 로거.
"""
import os
import sys
from contextlib import nullcontext
import psutil
from datetime import datetime
from rich.console import Console
from rich.live import Live
# from win10toast import ToastNotifier
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress_bar import ProgressBar
from src.core.config import LOG_DIR

# Rich 콘솔 객체
console = Console()
RUN_LOG_PATH = os.path.join(LOG_DIR, "pipeline_run.log")

class UIState:
    current_task = "대기 중"
    sub_task = ""
    progress_pct = 0.0 # 고도화: 진행률 추가
    start_time = datetime.now()
    is_dashboard_active = False

state = UIState()

def get_color_by_pct(pct: float) -> str:
    pct = max(0, min(100, pct))
    if pct < 50:
        r = int((pct / 50) * 255); g = 255; b = 0
    else:
        r = 255; g = int(255 - ((pct - 50) / 50) * 255); b = 0
    return f"#{r:02x}{g:02x}{b:02x}"

def create_status_layout():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    elapsed = str(datetime.now() - state.start_time).split(".")[0]

    table = Table.grid(expand=True)
    table.add_column(justify="left", ratio=1)
    table.add_column(justify="right", ratio=1)

    status_text = Text.assemble(
        (f" [TASK] {state.current_task} ", "bold magenta"),
        (f" | {state.sub_task}", "dim white") if state.sub_task else ""
    )
    
    sys_info = Text.assemble(
        (" CPU ", "bold white"), (f"{cpu:>4}% ", get_color_by_pct(cpu)),
        (" RAM ", "bold white"), (f"{ram:>4}% ", get_color_by_pct(ram)),
        (" TIME ", "bold white"), (f"{elapsed} ", "yellow")
    )
    table.add_row(status_text, sys_info)

    # 고도화: 진행률 바 추가
    progress_bar = ProgressBar(
        total=100.0,
        completed=state.progress_pct,
        width=None,
        complete_style="green",
        finished_style="bold green"
    )
    
    main_layout = Table.grid(expand=True)
    main_layout.add_row(table)
    main_layout.add_row(Text("")) # 공백
    main_layout.add_row(progress_bar)
    
    return Panel(
        main_layout,
        title="[bold blue]AMEVA-STT 실시간 대시보드[/]",
        border_style="blue",
        padding=(0, 1)
    )

# from win10toast import ToastNotifier  # 안정성 문제로 비활성화

def notify_windows(title: str, message: str, duration: int = 5):
    """윈도우 알림 기능을 비활성화함 (시스템 안정성 우선)"""
    pass

def _write_to_db(level: str, message: str):
    """파일 대신 SQLite DB에 로그를 영구 기록합니다."""
    try:
        from src.backend.core.database import db_manager
        # 환경변수에서 현재 실행 중인 태스크 ID가 있으면 획득하여 기록
        task_id = os.environ.get("CURRENT_TASK_ID")
        db_manager.add_log(level, message, task_id)
    except Exception:
        # DB 오류 시 fallback으로 콘솔에만 출력
        pass

def info(message: str):
    _write_to_db("INFO", message)
    if not state.is_dashboard_active:
        console.print(f"[bold blue]INFO[/] {message}")
    elif "완료" in message or "생성" in message:
        set_status(sub_task=message)

def error(message: str):
    _write_to_db("ERROR", message)
    if not state.is_dashboard_active:
        console.print(f"[bold red]ERR [/] {message}")
    notify_windows("⚠️ AMEVA-STT 오류", message[:100])

def success(message: str):
    _write_to_db("SUCCESS", message)
    if not state.is_dashboard_active:
        console.print(f"[bold green]OK  [/] {message}")
    notify_windows("✅ AMEVA-STT 완료", message[:100])

def update_progress(pct: float):
    """진행률을 업데이트한다. (0.0 ~ 100.0)"""
    state.progress_pct = max(0.0, min(100.0, pct))

def set_status(main_task: str = None, sub_task: str = None):
    if main_task: state.current_task = main_task
    if sub_task: state.sub_task = sub_task

def dashboard_context():
    state.start_time = datetime.now()
    # 터미널(TTY)이 아니거나 백그라운드 파이프 실행인 경우 Live 대시보드를 비활성화하여 교착상태(deadlock)를 예방합니다.
    if not sys.stdout.isatty() or os.environ.get("CURRENT_TASK_ID"):
        state.is_dashboard_active = False
        return nullcontext()
    
    state.is_dashboard_active = True
    return Live(create_status_layout(), refresh_per_second=4, get_renderable=create_status_layout, transient=True)

def stop_dashboard():
    state.is_dashboard_active = False
