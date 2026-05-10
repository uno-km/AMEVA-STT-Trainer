"""
src/utils/logger.py
Rich 라이브러리를 활용한 프리미엄 고정형 대시보드 로거.
"""
import os
import psutil
from datetime import datetime
from rich.console import Console
from rich.live import Live
from win10toast import ToastNotifier
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

_notifier = ToastNotifier()

def notify_windows(title: str, message: str, duration: int = 5):
    """윈도우 시스템 트레이 알림을 띄운다."""
    try:
        _notifier.show_toast(title, message, duration=duration, threaded=True)
    except: pass

def _write_to_file(level: str, message: str):
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(RUN_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] [{level}] {message}\n")

def info(message: str):
    _write_to_file("INFO", message)
    if not state.is_dashboard_active:
        console.print(f"[bold blue]INFO[/] {message}")
    elif "완료" in message or "생성" in message:
        set_status(sub_task=message)

def error(message: str):
    _write_to_file("ERROR", message)
    if not state.is_dashboard_active:
        console.print(f"[bold red]ERR [/] {message}")
    notify_windows("⚠️ AMEVA-STT 오류", message[:100])

def success(message: str):
    _write_to_file("SUCCESS", message)
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
    state.is_dashboard_active = True
    return Live(create_status_layout(), refresh_per_second=4, get_renderable=create_status_layout, transient=True)

def stop_dashboard():
    state.is_dashboard_active = False
