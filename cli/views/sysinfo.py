"""
cli/views/sysinfo.py
시스템 리소스 현황 (CPU / RAM / GPU 실시간 바 + 히스토리 스파크라인)
"""
import os, sys, time
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich import box

console = Console()

_BRAILLE = " ⣀⣄⣤⣦⣶⣷⣿"

def _sparkline(values: list, width: int = 35) -> str:
    if not values:
        return " " * width
    mn, mx = min(values), max(values)
    span = mx - mn or 1
    tail = values[-width:] if len(values) >= width else values
    chars = [_BRAILLE[int((v - mn) / span * (len(_BRAILLE) - 1))] for v in tail]
    return "".join(chars).ljust(width)

def _make_bar(pct: float, width: int = 30, color: str = "green") -> str:
    filled = int(max(0, min(100, pct)) / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{color}]{bar}[/{color}] {pct:.1f}%"

def show_system_status():
    console.clear()
    from cli.client.api_client import api_client

    cpu_hist, ram_hist, gpu_hist = [], [], []

    console.print("[bold cyan]🖥️  시스템 리소스 실시간 모니터 | Ctrl+C 종료[/bold cyan]\n")

    try:
        with Live(console=console, refresh_per_second=2, screen=False) as live:
            for _ in range(120):  # 최대 2분
                res = api_client.get("/api/v1/system/resources")
                if "error" in res and res["error"]:
                    cpu = ram = gpu = 0
                    ram_used = ram_total = disk_pct = disk_used = disk_total = 0
                    gpu_mem = "N/A"
                    procs = []
                    disk_str = "N/A"
                else:
                    cpu = res.get('cpu', 0)
                    ram = res.get('ram', 0)
                    gpu = res.get('gpu', 0)
                    gpu_mem = res.get('gpu_mem', 'N/A')
                    ram_used = res.get('ram_used', 0)
                    ram_total = res.get('ram_total', 0)
                    disk_pct = res.get('disk_pct', 0)
                    disk_used = res.get('disk_used', 0)
                    disk_total = res.get('disk_total', 0)
                    procs = res.get('processes', [])
                    disk_str = f"[dim]{disk_used:.1f}/{disk_total:.1f} GB[/dim]  {_make_bar(disk_pct, 20, 'blue')}"

                cpu_hist.append(cpu)
                ram_hist.append(ram)
                gpu_hist.append(gpu)
                if len(cpu_hist) > 60: cpu_hist.pop(0)
                if len(ram_hist) > 60: ram_hist.pop(0)
                if len(gpu_hist) > 60: gpu_hist.pop(0)

                # 프로세스 목록 (상위 5개)
                proc_table = Table(box=box.MINIMAL, show_header=True, expand=True)
                proc_table.add_column("PID", style="dim", width=7)
                proc_table.add_column("프로세스명", style="cyan")
                proc_table.add_column("CPU%", justify="right", style="red", width=7)
                proc_table.add_column("메모리", justify="right", style="yellow", width=10)
                
                for p in procs:
                    proc_table.add_row(str(p.get('pid')), p.get('name'), p.get('cpu'), p.get('mem'))

                grid = Table.grid(expand=True)
                grid.add_row(Panel(
                    f"[bold]CPU[/bold]   {_make_bar(cpu, 30, 'cyan')}   [dim]{cpu:.1f}%[/dim]\n"
                    f"[dim cyan]{_sparkline(cpu_hist, 35)}[/dim cyan]\n\n"
                    f"[bold]RAM[/bold]   {_make_bar(ram, 30, 'yellow')}   [dim]{ram_used:.1f}/{ram_total:.1f} GB[/dim]\n"
                    f"[dim yellow]{_sparkline(ram_hist, 35)}[/dim yellow]\n\n"
                    f"[bold]GPU[/bold]   {_make_bar(gpu, 30, 'magenta')}   [dim]{gpu_mem}[/dim]\n"
                    f"[dim magenta]{_sparkline(gpu_hist, 35)}[/dim magenta]\n\n"
                    f"[bold]DISK[/bold]  {disk_str}",
                    title="[bold]📊 리소스 사용량 + 히스토리[/bold]", border_style="cyan"
                ))
                grid.add_row(Panel(proc_table, title="[bold]⚙️ 상위 프로세스 (CPU 순)[/bold]", border_style="green"))

                live.update(grid)
                time.sleep(0.5)

    except KeyboardInterrupt:
        pass

    console.print("\n[yellow]모니터링 종료.[/yellow]")
    Prompt.ask("[dim]엔터를 눌러 돌아가기[/dim]")
