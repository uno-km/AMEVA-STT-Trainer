"""
AMEVA STT Engine - Premium CLI Edition
메인 진입점 (cli/cli.py)
"""
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich import box

console = Console()

from cli.client.api_client import api_client

def print_header():
    art = (
        " █████╗ ███╗   ███╗███████╗██╗   ██╗ █████╗\n"
        "██╔══██╗████╗ ████║██╔════╝██║   ██║██╔══██╗\n"
        "███████║██╔████╔██║█████╗  ██║   ██║███████║\n"
        "██╔══██║██║╚██╔╝██║██╔══╝  ╚██╗ ██╔╝██╔══██║\n"
        "██║  ██║██║ ╚═╝ ██║███████╗ ╚████╔╝ ██║  ██║\n"
        "╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝  ╚═══╝  ╚═╝  ╚═╝"
    )
    console.print(Panel(
        f"[bold cyan]{art}[/bold cyan]\n"
        "[dim]STT Engine · Headless Remote CLI · Powered by Rich[/dim]",
        box=box.DOUBLE_EDGE, expand=True
    ))

def check_server_health():
    with console.status("[yellow]서버 연결 확인 중...[/yellow]"):
        if not api_client.check_health():
            console.print(Panel(
                "[bold red]❌ 백엔드 API 서버에 연결할 수 없습니다.[/bold red]\n\n"
                "[white]서버가 실행 중인지 확인하세요.[/white]\n"
                "[dim]명령어: uvicorn src.backend.main:app --host 0.0.0.0 --port 8000[/dim]",
                border_style="red"
            ))
            sys.exit(1)

def main_menu():
    from cli.views.tasks import show_task_list, start_new_task
    from cli.views.monitor import watch_logs
    from cli.views.explorer import show_file_explorer
    from cli.views.db_view import show_db_viewer
    from cli.views.sysinfo import show_system_status

    check_server_health()

    while True:
        console.clear()
        print_header()
        console.print("\n[bold white]원하는 작업을 선택하세요[/bold white]\n")
        console.print("  [bold cyan]1[/bold cyan]  📋  원격 태스크 관리 (목록 / 이어하기 / 정지)")
        console.print("  [bold cyan]2[/bold cyan]  🚀  신규 학습 파이프라인 시작 (서버 기동)")
        console.print("  [bold cyan]3[/bold cyan]  📡  실시간 로그 & 차트 모니터 (Plotext)")
        console.print("  [bold cyan]4[/bold cyan]  📂  원격 파일 익스플로러 (API)")
        console.print("  [bold cyan]5[/bold cyan]  🗄️   원격 DB 인스펙터 (API)")
        console.print("  [bold cyan]6[/bold cyan]  🖥️   서버 시스템 리소스 현황 (API)")
        console.print("  [bold red]0[/bold red]  ❌  종료\n")

        choice = Prompt.ask("[bold yellow]선택[/bold yellow]", choices=["0","1","2","3","4","5","6"], default="1")

        if choice == "1":
            show_task_list()
        elif choice == "2":
            start_new_task()
        elif choice == "3":
            watch_logs()
        elif choice == "4":
            show_file_explorer()
        elif choice == "5":
            show_db_viewer()
        elif choice == "6":
            show_system_status()
        elif choice == "0":
            console.print("[green]안녕히 계세요![/green]")
            break

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[red]강제 종료됨.[/red]")
        sys.exit(0)

