"""
cli/views/monitor.py
실시간 로그 모니터 + 메트릭 차트 (Plotext + Rich Live 기반)
"""
import os, sys, time
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, IntPrompt
from rich import box
import plotext as plt

from cli.client.api_client import api_client

console = Console()

def _make_bar(pct: float, width: int = 20, color: str = "green") -> str:
    filled = int(pct / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{color}]{bar}[/{color}] {pct:.1f}%"

def _build_plotext_chart(loss_hist, acc_hist, width=100, height=15):
    """Plotext를 사용해 ANSI 텍스트 차트를 렌더링합니다."""
    plt.clf()
    plt.plotsize(width, height)
    plt.theme("clear")
    plt.colorless() # Rich의 Panel 안에서 렌더링 시 충돌을 막기 위해 무색/혹은 특정색 지정
    
    if loss_hist:
        plt.plot(loss_hist, marker="dot", color="red", label="Loss")
    if acc_hist:
        plt.plot(acc_hist, marker="dot", color="green", label="Accuracy")
        
    if not loss_hist and not acc_hist:
        plt.plot([0], [0], marker="dot")
        
    plt.title("실시간 메트릭 추이 (Loss & Accuracy)")
    # build()를 호출해 ANSI 문자열 추출
    ansi_chart = plt.build()
    return Text.from_ansi(ansi_chart)

def watch_logs(task_id: str = None):
    if not task_id:
        res = api_client.get("/api/v1/tasks/list")
        if "error" in res:
            console.print(f"[red]API 통신 오류: {res['error']}[/red]")
            Prompt.ask("\n[dim]엔터[/dim]")
            return
            
        tasks = res.get("tasks", [])
        if not tasks:
            console.print("[yellow]등록된 태스크가 없습니다.[/yellow]")
            Prompt.ask("\n[dim]엔터[/dim]")
            return
            
        console.clear()
        console.print("[bold cyan]모니터링할 원격 태스크를 선택하세요[/bold cyan]\n")
        for i, t in enumerate(tasks, 1):
            status_color = {"SUCCESS":"green","RUNNING":"yellow","FAILED":"red"}.get(t['status'],'white')
            console.print(f"  [{i}] [{status_color}]{t['status']:10}[/{status_color}]  {t['tsk_nm']}  [dim]({t['id'][:8]})[/dim]")
        pick = IntPrompt.ask("\n번호", default=1)
        task_id = tasks[pick - 1]['id']

    console.clear()
    console.print(f"[bold cyan]📡 원격 실시간 모니터 — Task {task_id[:8]} | Ctrl+C 종료[/bold cyan]\n")

    LEVEL_STYLE = {"INFO": "white", "ERROR": "bold red", "WARNING": "bold yellow",
                   "SUCCESS": "bold green", "CRITICAL": "bold red on black"}

    try:
        with Live(console=console, refresh_per_second=2, screen=False) as live:
            while True:
                # ── 로그 ──
                logs_res = api_client.get(f"/api/v1/tasks/logs?task_id={task_id}")
                logs = logs_res.get("logs", []) if isinstance(logs_res, dict) else []
                if isinstance(logs, str): logs = []
                log_rows = logs[-20:]

                log_table = Table(box=box.MINIMAL, show_header=False, expand=True)
                log_table.add_column("시간", style="dim", width=10, no_wrap=True)
                log_table.add_column("레벨", width=9, no_wrap=True)
                log_table.add_column("메시지")
                for lg in log_rows:
                    lvl = lg.get('level', 'INFO')
                    style = LEVEL_STYLE.get(lvl, 'white')
                    log_table.add_row(
                        lg.get('timestamp', ''),
                        f"[{style}][{lvl}][/{style}]",
                        Text(lg.get('message', ''), overflow="fold")
                    )

                # ── 메트릭 ──
                metrics_res = api_client.get(f"/api/v1/tasks/metrics?task_id={task_id}")
                metrics = metrics_res.get("metrics", []) if isinstance(metrics_res, dict) else []
                
                loss_history = []
                acc_history = []
                latest_loss = latest_acc = latest_step = latest_speed = 0
                
                if metrics:
                    loss_history = [m['loss'] for m in metrics if m.get('loss') is not None][-100:]
                    acc_history  = [m['accuracy'] for m in metrics if m.get('accuracy') is not None][-100:]
                    latest_loss  = loss_history[-1] if loss_history else 0
                    latest_acc   = acc_history[-1]  if acc_history  else 0
                    latest_step  = metrics[-1].get('step', 0) if metrics else 0
                    latest_speed = metrics[-1].get('speed', 0) if metrics else 0

                # ── 시스템 리소스 ──
                sys_res = api_client.get("/api/v1/system/resources")
                cpu_pct = sys_res.get('cpu', 0) if isinstance(sys_res, dict) else 0
                ram_pct = sys_res.get('ram', 0) if isinstance(sys_res, dict) else 0
                gpu_pct = sys_res.get('gpu', 0) if isinstance(sys_res, dict) else 0

                # ── 태스크 상태 ──
                report_res = api_client.get(f"/api/v1/tasks/report?task_id={task_id}")
                task_info = report_res.get("task_info", {}) if isinstance(report_res, dict) else {}
                cur_status = task_info.get('status', 'UNKNOWN') if task_info else 'UNKNOWN'
                status_color = {"RUNNING":"yellow","SUCCESS":"green","FAILED":"red"}.get(cur_status,"white")

                # ── 레이아웃 조립 ──
                status_bar = Text()
                status_bar.append(f" Task: {task_id[:8]}  ", style="bold cyan")
                status_bar.append(f"Status: {cur_status}  ", style=f"bold {status_color}")
                status_bar.append(f"Step: {latest_step}  ", style="magenta")
                status_bar.append(f"Loss: {latest_loss:.4f}  ", style="red")
                status_bar.append(f"Acc: {latest_acc:.4f}  ", style="green")
                status_bar.append(f"Speed: {latest_speed:.2f} steps/s", style="cyan")

                # Plotext 차트 렌더링
                terminal_width = console.measure("").maximum
                chart_width = min(terminal_width - 10, 100) # 가로 최대 너비 조정
                chart_ansi = _build_plotext_chart(loss_history, acc_history, width=chart_width, height=12)

                res_bar_txt = (
                    f"CPU  {_make_bar(cpu_pct, 25, 'cyan')}   "
                    f"RAM  {_make_bar(ram_pct, 25, 'yellow')}   "
                    f"GPU  {_make_bar(gpu_pct, 25, 'magenta')}"
                )

                grid = Table.grid(expand=True)
                grid.add_row(Panel(status_bar, border_style="cyan", height=3))
                grid.add_row(Panel(chart_ansi, border_style="blue"))
                grid.add_row(Panel(res_bar_txt, title="[bold]🖥️ 서버 시스템 리소스[/bold]", border_style="green", height=3))
                grid.add_row(Panel(log_table, title=f"[bold]📜 실시간 로그 (최신 20개)[/bold]", border_style="white"))

                live.update(grid)

                if cur_status in ("SUCCESS", "FAILED"):
                    time.sleep(2)
                    break

                time.sleep(0.5) # 500ms API Polling

    except KeyboardInterrupt:
        pass

    console.print("\n[yellow]모니터링 종료.[/yellow]")
    Prompt.ask("[dim]엔터를 눌러 돌아가기[/dim]")
