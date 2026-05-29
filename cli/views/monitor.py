"""
cli/views/monitor.py
실시간 로그 모니터 + 메트릭 스파크라인 차트 (Rich Live 기반)
"""
import os, sys, time
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from rich.prompt import Prompt, IntPrompt
from rich import box

console = Console()

# ── 브라유 스파크라인 ──────────────────────────────────────────────────────────
_BRAILLE = " ⣀⣄⣤⣦⣶⣷⣿"

def _sparkline(values: list, width: int = 40) -> str:
    if not values:
        return " " * width
    mn, mx = min(values), max(values)
    span = mx - mn or 1
    tail = values[-width:] if len(values) >= width else values
    chars = []
    for v in tail:
        idx = int((v - mn) / span * (len(_BRAILLE) - 1))
        chars.append(_BRAILLE[idx])
    line = "".join(chars)
    return line.ljust(width)

def _make_bar(pct: float, width: int = 20, color: str = "green") -> str:
    filled = int(pct / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{color}]{bar}[/{color}] {pct:.1f}%"

# ── 메인 모니터 함수 ──────────────────────────────────────────────────────────
def watch_logs(task_id: str = None):
    from src.backend.core.database import db_manager
    from src.backend.api.pipeline_api import list_tasks, get_resources

    if not task_id:
        res = list_tasks()
        tasks = res.get("tasks", [])
        if not tasks:
            console.print("[yellow]등록된 태스크가 없습니다.[/yellow]")
            Prompt.ask("\n[dim]엔터[/dim]")
            return
        console.clear()
        console.print("[bold cyan]모니터링할 태스크를 선택하세요[/bold cyan]\n")
        for i, t in enumerate(tasks, 1):
            status_color = {"SUCCESS":"green","RUNNING":"yellow","FAILED":"red"}.get(t['status'],'white')
            console.print(f"  [{i}] [{status_color}]{t['status']:10}[/{status_color}]  {t['tsk_nm']}  [dim]({t['id'][:8]})[/dim]")
        pick = IntPrompt.ask("\n번호", default=1)
        task_id = tasks[pick - 1]['id']

    console.clear()
    console.print(f"[bold cyan]📡 실시간 모니터 — Task {task_id[:8]} | Ctrl+C 종료[/bold cyan]\n")

    loss_history = []
    acc_history = []
    cpu_history = []

    LEVEL_STYLE = {"INFO": "white", "ERROR": "bold red", "WARNING": "bold yellow",
                   "SUCCESS": "bold green", "CRITICAL": "bold red on black"}

    try:
        with Live(console=console, refresh_per_second=1, screen=False) as live:
            while True:
                # ── 로그 ──
                db_logs = db_manager.get_logs(task_id, limit=60)
                log_rows = db_logs[-25:]

                log_table = Table(box=box.MINIMAL, show_header=False, expand=True)
                log_table.add_column("시간", style="dim", width=10, no_wrap=True)
                log_table.add_column("레벨", width=9, no_wrap=True)
                log_table.add_column("메시지")
                for lg in log_rows:
                    dt = lg.get('create_dt', '')
                    tp = dt.split(' ')[-1] if ' ' in dt else dt
                    lvl = lg.get('level', 'INFO')
                    style = LEVEL_STYLE.get(lvl, 'white')
                    log_table.add_row(
                        tp,
                        f"[{style}][{lvl}][/{style}]",
                        Text(lg.get('message', ''), overflow="fold")
                    )

                # ── 메트릭 ──
                metrics = db_manager.get_metrics(task_id)
                if metrics:
                    loss_history = [m['loss'] for m in metrics if m.get('loss') is not None]
                    acc_history  = [m['accuracy'] for m in metrics if m.get('accuracy') is not None]
                    latest_loss  = loss_history[-1] if loss_history else 0
                    latest_acc   = acc_history[-1]  if acc_history  else 0
                    latest_step  = metrics[-1].get('step', 0) if metrics else 0
                    latest_speed = metrics[-1].get('speed', 0) if metrics else 0
                else:
                    latest_loss = latest_acc = latest_step = latest_speed = 0

                # ── 시스템 리소스 ──
                try:
                    sysres = get_resources()
                    cpu_pct = sysres.get('cpu', 0)
                    ram_pct = sysres.get('ram', 0)
                    gpu_pct = sysres.get('gpu', 0)
                    cpu_history.append(cpu_pct)
                    if len(cpu_history) > 60:
                        cpu_history.pop(0)
                except:
                    cpu_pct = ram_pct = gpu_pct = 0

                # ── 태스크 상태 ──
                task_info = db_manager.get_task_details(task_id)
                cur_status = task_info.get('status', 'UNKNOWN') if task_info else 'UNKNOWN'
                status_color = {"RUNNING":"yellow","SUCCESS":"green","FAILED":"red"}.get(cur_status,"white")

                # ── 레이아웃 조립 ──
                # 1) 상단 상태 바
                status_bar = Text()
                status_bar.append(f" Task: {task_id[:8]}  ", style="bold cyan")
                status_bar.append(f"Status: {cur_status}  ", style=f"bold {status_color}")
                status_bar.append(f"Step: {latest_step}  ", style="magenta")
                status_bar.append(f"Loss: {latest_loss:.4f}  ", style="red")
                status_bar.append(f"Acc: {latest_acc:.4f}  ", style="green")
                status_bar.append(f"Speed: {latest_speed:.2f} steps/s", style="cyan")

                # 2) 메트릭 차트
                loss_spark = _sparkline(loss_history, 50)
                acc_spark  = _sparkline(acc_history, 50)
                cpu_spark  = _sparkline(cpu_history, 50)

                metric_table = Table(box=box.SIMPLE, show_header=False, expand=True)
                metric_table.add_column("라벨", style="dim", width=12)
                metric_table.add_column("차트")
                metric_table.add_column("현재값", width=12, justify="right")
                metric_table.add_row("[red]Loss[/red]",      f"[red]{loss_spark}[/red]",    f"[red]{latest_loss:.4f}[/red]")
                metric_table.add_row("[green]Accuracy[/green]", f"[green]{acc_spark}[/green]", f"[green]{latest_acc:.4f}[/green]")
                metric_table.add_row("[cyan]CPU[/cyan]",     f"[cyan]{cpu_spark}[/cyan]",   f"[cyan]{cpu_pct:.1f}%[/cyan]")

                # 3) 리소스 바
                res_bar_txt = (
                    f"CPU  {_make_bar(cpu_pct, 25, 'cyan')}   "
                    f"RAM  {_make_bar(ram_pct, 25, 'yellow')}   "
                    f"GPU  {_make_bar(gpu_pct, 25, 'magenta')}"
                )

                # 최종 패널 조합
                grid = Table.grid(expand=True)
                grid.add_row(Panel(status_bar, border_style="cyan", height=3))
                grid.add_row(Panel(metric_table, title="[bold]📈 학습 메트릭 차트[/bold]", border_style="blue"))
                grid.add_row(Panel(res_bar_txt, title="[bold]🖥️ 시스템 리소스[/bold]", border_style="green", height=3))
                grid.add_row(Panel(log_table, title=f"[bold]📜 실시간 로그 (최신 25개)[/bold]", border_style="white"))

                live.update(grid)

                # 완료 시 자동 중단
                if cur_status in ("SUCCESS", "FAILED"):
                    time.sleep(2)
                    break

                time.sleep(1)

    except KeyboardInterrupt:
        pass

    console.print("\n[yellow]모니터링 종료.[/yellow]")
    Prompt.ask("[dim]엔터를 눌러 돌아가기[/dim]")
