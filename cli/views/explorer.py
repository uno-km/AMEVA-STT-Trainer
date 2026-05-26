"""
cli/views/explorer.py
파일 익스플로러 (dataset / outputs / logs / configs) + CSV/텍스트 파일 뷰어
"""
import os, sys, csv
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from rich.console import Console
from rich.tree import Tree
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich.text import Text
from rich import box

console = Console()
BASE_DIR = project_root

def _human_size(n: int) -> str:
    for unit in ["B","KB","MB","GB"]:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"

def _build_tree(parent: Tree, path: str, depth: int = 0, max_depth: int = 3, skip_names=None):
    if skip_names is None:
        skip_names = {"chunks", "__pycache__", ".git", "venv"}
    if depth > max_depth:
        return
    try:
        entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        return
    for entry in entries:
        if entry.name in skip_names:
            branch = parent.add(f"[dim]{entry.name}/  [yellow](스킵 — 내부 수천개 파일)[/yellow][/dim]")
            continue
        if entry.is_dir():
            branch = parent.add(f"[bold yellow]📁 {entry.name}/[/bold yellow]")
            _build_tree(branch, entry.path, depth + 1, max_depth)
        else:
            size = _human_size(entry.stat().st_size)
            ext = os.path.splitext(entry.name)[1].lower()
            icon = {"csv":"📊","log":"📜","db":"🗄️","docx":"📄","gguf":"🤖","pt":"🧠","wav":"🎵","mp3":"🎵","json":"📋","yaml":"⚙️","txt":"📝"}.get(ext.lstrip('.'), "📄")
            parent.add(f"{icon} [white]{entry.name}[/white]  [dim]{size}[/dim]  [dim cyan]{entry.path}[/dim cyan]")


def _collect_files_flat(path: str, exts: list = None) -> list:
    """파일 목록 평탄화 (선택 가능하게)"""
    results = []
    skip = {"chunks", "__pycache__", ".git", "venv"}
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in skip]
        for f in files:
            if exts is None or os.path.splitext(f)[1].lower() in exts:
                results.append(os.path.join(root, f))
    return results


def _view_csv(path: str):
    console.clear()
    console.print(Panel(f"[bold]📊 CSV 뷰어: {os.path.basename(path)}[/bold]", expand=False))
    try:
        with open(path, newline='', encoding='utf-8', errors='replace') as f:
            reader = list(csv.reader(f))
        if not reader:
            console.print("[yellow]빈 파일입니다.[/yellow]")
            Prompt.ask("\n[dim]엔터[/dim]")
            return
        headers = reader[0]
        rows = reader[1:]

        # 페이지네이션
        page_size = 40
        total_pages = max(1, (len(rows) + page_size - 1) // page_size)
        page = 0

        while True:
            console.clear()
            console.print(Panel(f"[bold]📊 {os.path.basename(path)}[/bold]  [dim]총 {len(rows)}행  페이지 {page+1}/{total_pages}[/dim]", expand=False))
            table = Table(box=box.SIMPLE_HEAVY, show_lines=False)
            for h in headers:
                table.add_column(h, style="cyan", max_width=30, overflow="fold")
            for row in rows[page * page_size : (page + 1) * page_size]:
                table.add_row(*[str(c) for c in row])
            console.print(table)

            nav = Prompt.ask("\n[dim]n=다음  p=이전  q=닫기[/dim]", choices=["n","p","q"], default="q")
            if nav == "n" and page < total_pages - 1:
                page += 1
            elif nav == "p" and page > 0:
                page -= 1
            elif nav == "q":
                break
    except Exception as e:
        console.print(f"[red]파일 열기 실패: {e}[/red]")
        Prompt.ask("\n[dim]엔터[/dim]")


def _view_text(path: str):
    console.clear()
    console.print(Panel(f"[bold]📝 텍스트 뷰어: {os.path.basename(path)}[/bold]", expand=False))
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        page_size = 40
        total_pages = max(1, (len(lines) + page_size - 1) // page_size)
        page = 0

        while True:
            console.clear()
            console.print(Panel(f"[bold]{os.path.basename(path)}[/bold]  [dim]{len(lines)}줄  {page+1}/{total_pages}페이지[/dim]", expand=False))
            start = page * page_size
            for i, line in enumerate(lines[start:start + page_size], start + 1):
                console.print(f"[dim]{i:5d}[/dim]  {line.rstrip()}")
            nav = Prompt.ask("\n[dim]n=다음  p=이전  q=닫기[/dim]", choices=["n","p","q"], default="q")
            if nav == "n" and page < total_pages - 1:
                page += 1
            elif nav == "p" and page > 0:
                page -= 1
            elif nav == "q":
                break
    except Exception as e:
        console.print(f"[red]파일 열기 실패: {e}[/red]")
        Prompt.ask("\n[dim]엔터[/dim]")


def _open_file_action(path: str):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        _view_csv(path)
    elif ext in (".log", ".txt", ".md", ".yaml", ".yml", ".json"):
        _view_text(path)
    elif sys.platform == "win32":
        console.print(f"[dim]시스템에서 파일을 엽니다: {path}[/dim]")
        os.startfile(path)
    else:
        console.print(f"[yellow]경로: {path}[/yellow]")
        Prompt.ask("[dim]엔터[/dim]")


def show_file_explorer():
    CATEGORIES = {
        "1": ("dataset",  "📦 Dataset",  os.path.join(BASE_DIR, "dataset")),
        "2": ("outputs",  "🤖 Outputs",  os.path.join(BASE_DIR, "outputs")),
        "3": ("logs",     "📜 Logs",     os.path.join(BASE_DIR, "logs")),
        "4": ("configs",  "⚙️  Configs",  os.path.join(BASE_DIR, "configs")),
    }

    while True:
        console.clear()
        console.print(Panel("[bold cyan]📂 파일 익스플로러[/bold cyan]", expand=False))
        console.print("  [cyan]1[/cyan]  📦 Dataset")
        console.print("  [cyan]2[/cyan]  🤖 Outputs (학습 결과 / 체크포인트 / 모델)")
        console.print("  [cyan]3[/cyan]  📜 Logs")
        console.print("  [cyan]4[/cyan]  ⚙️  Configs")
        console.print("  [cyan]f[/cyan]  🔍 전체 파일 검색 (확장자 필터)")
        console.print("  [red]0[/red]  ◀ 돌아가기\n")

        pick = Prompt.ask("선택", choices=["0","1","2","3","4","f"], default="0")
        if pick == "0":
            return
        elif pick == "f":
            _search_files()
            continue

        key, label, base_path = CATEGORIES[pick]
        _browse_directory(label, base_path)


def _browse_directory(label: str, base_path: str):
    if not os.path.exists(base_path):
        console.print(f"[yellow]경로가 존재하지 않습니다: {base_path}[/yellow]")
        Prompt.ask("\n[dim]엔터[/dim]")
        return

    console.clear()
    tree = Tree(f"[bold cyan]{label}[/bold cyan]  [dim]{base_path}[/dim]")
    with console.status("[yellow]스캔 중...[/yellow]"):
        _build_tree(tree, base_path)
    console.print(tree)

    console.print("\n[dim]파일 경로를 직접 입력하여 열거나 엔터로 돌아가기:[/dim]")
    path = Prompt.ask("경로 (엔터=돌아가기)", default="")
    if path.strip() and os.path.isfile(path.strip()):
        _open_file_action(path.strip())


def _search_files():
    console.clear()
    console.print(Panel("[bold]🔍 전체 파일 검색[/bold]", expand=False))
    keyword = Prompt.ask("검색 키워드 (파일명 포함)")
    ext_filter = Prompt.ask("확장자 필터 (예: .csv .log, 빈칸=전체)", default="")
    exts = [e.strip() if e.strip().startswith(".") else f".{e.strip()}" for e in ext_filter.split() if e.strip()] or None

    with console.status(f"[yellow]'{keyword}' 검색 중...[/yellow]"):
        results = []
        search_dirs = [
            os.path.join(BASE_DIR, d)
            for d in ("dataset","outputs","logs","configs","scripts")
            if os.path.isdir(os.path.join(BASE_DIR, d))
        ]
        for d in search_dirs:
            for f in _collect_files_flat(d, exts):
                if keyword.lower() in os.path.basename(f).lower():
                    results.append(f)

    if not results:
        console.print("[yellow]검색 결과가 없습니다.[/yellow]")
        Prompt.ask("\n[dim]엔터[/dim]")
        return

    table = Table(title=f"검색 결과: {len(results)}개", box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("파일명", style="cyan")
    table.add_column("크기", justify="right", style="dim")
    table.add_column("경로", style="dim")
    for i, f in enumerate(results[:50], 1):
        size = _human_size(os.path.getsize(f))
        table.add_row(str(i), os.path.basename(f), size, os.path.dirname(f))
    console.print(table)
    if len(results) > 50:
        console.print(f"[dim]... 외 {len(results)-50}개[/dim]")

    choices = [str(i) for i in range(len(results[:50]) + 1)]
    pick = Prompt.ask("\n번호 선택하여 열기 (0=취소)", choices=choices, default="0")
    if pick != "0":
        _open_file_action(results[int(pick)-1])
