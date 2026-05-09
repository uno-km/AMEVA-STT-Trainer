"""
src/utils/logger.py
Rich 라이브러리를 활용한 프리미엄 고정형 대시보드 로거.
"""
import os
import psutil
from datetime import datetime
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from src.core.config import LOG_DIR

# Rich 콘솔 객체
console = Console()
RUN_LOG_PATH = os.path.join(LOG_DIR, "pipeline_run.log")

class UIState:
    current_task = "대기 중"
    sub_task = ""
    start_time = datetime.now()
    is_dashboard_active = False # 대시보드 활성 상태 플래그

state = UIState()

def get_color_by_pct(pct: float) -> str:
    pct = max(0, min(100, pct))
    if pct < 50:
        r = int((pct / 50) * 255)
        g = 255
        b = 0
    else:
        r = 255
        g = int(255 - ((pct - 50) / 50) * 255)
        b = 0
    return f"#{r:02x}{g:02x}{b:02x}"

def create_status_layout():
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    elapsed = str(datetime.now() - state.start_time).split(".")[0]

    cpu_color = get_color_by_pct(cpu)
    ram_color = get_color_by_pct(ram)

    table = Table.grid(expand=True)
    table.add_column(justify="left", ratio=1)
    table.add_column(justify="right", ratio=1)

    status_text = Text.assemble(
        (f" [TASK] {state.current_task} ", "bold magenta"),
        (f" | {state.sub_task}", "dim white") if state.sub_task else ""
    )
    
    sys_info = Text.assemble(
        (" CPU ", "bold white"), (f"{cpu:>4}% ", cpu_color),
        (" RAM ", "bold white"), (f"{ram:>4}% ", ram_color),
        (" TIME ", "bold white"), (f"{elapsed} ", "yellow")
    )

    table.add_row(status_text, sys_info)
    
    return Panel(
        table,
        title="[bold blue]AMEVA-STT 실시간 대시보드[/]",
        border_style="blue",
        padding=(0, 1)
    )

def _write_to_file(level: str, message: str):
    os.makedirs(LOG_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(RUN_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [{level}] {message}\n")

def info(message: str):
    _write_to_file("INFO", message)
    # 대시보드가 켜져 있을 때는 줄줄이 출력하지 않고 무시 (설치 프로그램 스타일)
    if not state.is_dashboard_active:
        console.print(f"[bold blue]INFO[/] {message}")
    else:
        # 대신 대시보드 하단 상태를 실시간 업데이트 (필요한 경우)
        if "완료" in message or "생성" in message:
            set_status(sub_task=message)

def warning(message: str):
    _write_to_file("WARNING", message)
    # 경고는 중요하므로 대시보드 모드에서도 출력하되, live를 깨지 않도록 처리 가능
    if not state.is_dashboard_active:
        console.print(f"[bold yellow]WARN[/] [yellow]{message}[/]")

def error(message: str):
    _write_to_file("ERROR", message)
    if not state.is_dashboard_active:
        console.print(f"[bold red]ERR [/] [red]{message}[/]", style="underline")

def success(message: str):
    _write_to_file("SUCCESS", message)
    if not state.is_dashboard_active:
        console.print(f"[bold green]OK  [/] [green]{message}[/]")

def dashboard_context():
    state.start_time = datetime.now()
    state.is_dashboard_active = True
    
    # Live 객체 생성 (종료 시 플래그 리셋을 위해 context를 수동 관리하지 않고 
    # 호출부에서 with 문을 사용할 때 flag가 유지되도록 함)
    # 실제로는 with 블록이 끝나면 is_dashboard_active를 False로 돌려줘야 함
    return Live(
        create_status_layout(), 
        refresh_per_second=4, 
        get_renderable=create_status_layout,
        transient=True
    )

def stop_dashboard():
    """대시보드 모드를 명시적으로 종료 (플래그 리셋)"""
    state.is_dashboard_active = False

def set_status(main_task: str = None, sub_task: str = None):
    if main_task: state.current_task = main_task
    if sub_task: state.sub_task = sub_task
