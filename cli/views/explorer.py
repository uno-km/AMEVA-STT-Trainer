"""
cli/views/explorer.py
원격 서버 파일 익스플로러 (API 기반)
"""
import os, sys
from rich.console import Console
from rich.tree import Tree
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich import box

from cli.client.api_client import api_client

console = Console()

def _human_size(n: int) -> str:
    for unit in ["B","KB","MB","GB"]:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"

def _build_tree(parent: Tree, nodes: list):
    for node in sorted(nodes, key=lambda x: (not x.get('is_dir'), x.get('name', '').lower())):
        name = node.get("name", "")
        if name in ("chunks", "__pycache__", ".git", "venv"):
            parent.add(f"[dim]{name}/  [yellow](스킵)[/yellow][/dim]")
            continue
            
        if node.get("is_dir"):
            branch = parent.add(f"[bold yellow]📁 {name}/[/bold yellow]")
            _build_tree(branch, node.get("children", []))
        else:
            size = _human_size(node.get("size", 0))
            ext = os.path.splitext(name)[1].lower()
            icon = {"csv":"📊","log":"📜","db":"🗄️","docx":"📄","gguf":"🤖","pt":"🧠","wav":"🎵","mp3":"🎵","json":"📋","yaml":"⚙️","txt":"📝"}.get(ext.lstrip('.'), "📄")
            parent.add(f"{icon} [white]{name}[/white]  [dim]{size}[/dim]  [dim cyan]{node.get('path', '')}[/dim cyan]")

def _view_file(path: str):
    console.clear()
    console.print(Panel(f"[bold]📝 원격 파일 뷰어: {os.path.basename(path)}[/bold]", expand=False))
    
    with console.status("[yellow]서버에서 파일 내용을 불러오는 중...[/yellow]"):
        res = api_client.get("/api/v1/files/read", {"path": path})
        
    if "error" in res:
        console.print(f"[red]파일 열기 실패: {res['error']}[/red]")
        Prompt.ask("\n[dim]엔터[/dim]")
        return
        
    content_type = res.get("type", "text")
    content = res.get("content", [])
    
    if not content:
        console.print("[yellow]빈 파일입니다.[/yellow]")
        Prompt.ask("\n[dim]엔터[/dim]")
        return

    page_size = 40
    total_pages = max(1, (len(content) + page_size - 1) // page_size)
    page = 0

    while True:
        console.clear()
        console.print(Panel(f"[bold]📝 {os.path.basename(path)}[/bold]  [dim]총 {len(content)}줄/행  페이지 {page+1}/{total_pages}[/dim]", expand=False))
        
        chunk = content[page * page_size : (page + 1) * page_size]
        
        if content_type == "csv":
            table = Table(box=box.SIMPLE_HEAVY, show_lines=False)
            if page == 0:
                headers = chunk[0]
                rows = chunk[1:]
            else:
                headers = content[0]
                rows = chunk
                
            for h in headers: table.add_column(str(h), style="cyan", max_width=30, overflow="fold")
            for row in rows: table.add_row(*[str(c) for c in row])
            console.print(table)
        else:
            for i, line in enumerate(chunk, page * page_size + 1):
                console.print(f"[dim]{i:5d}[/dim]  {str(line).rstrip()}")
                
        nav = Prompt.ask("\n[dim]n=다음  p=이전  q=닫기[/dim]", choices=["n","p","q"], default="q")
        if nav == "n" and page < total_pages - 1:
            page += 1
        elif nav == "p" and page > 0:
            page -= 1
        elif nav == "q":
            break

def _open_file_action(path: str):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".csv", ".log", ".txt", ".md", ".yaml", ".yml", ".json"):
        _view_file(path)
    else:
        console.print(f"[yellow]지원하지 않는 확장자입니다 (원격 열람 불가): {path}[/yellow]")
        Prompt.ask("[dim]엔터[/dim]")

def show_file_explorer():
    CATEGORIES = {
        "1": ("dataset", "📦 Dataset"),
        "2": ("outputs", "🤖 Outputs (학습 결과 / 체크포인트 / 모델)"),
        "3": ("logs",    "📜 Logs"),
        "4": ("configs", "⚙️  Configs"),
    }

    while True:
        console.clear()
        console.print(Panel("[bold cyan]📂 원격 파일 익스플로러 (API 기반)[/bold cyan]", expand=False))
        for k, v in CATEGORIES.items():
            console.print(f"  [cyan]{k}[/cyan]  {v[1]}")
        console.print("  [red]0[/red]  ◀ 돌아가기\n")

        pick = Prompt.ask("선택", choices=["0","1","2","3","4"], default="0")
        if pick == "0":
            return

        key, label = CATEGORIES[pick]
        
        with console.status("[yellow]서버에서 폴더 구조를 불러오는 중...[/yellow]"):
            res = api_client.get("/api/v1/files/explorer")
            
        if "error" in res:
            console.print(f"[red]서버 오류: {res['error']}[/red]")
            Prompt.ask("\n[dim]엔터[/dim]")
            continue
            
        nodes = res.get(key, [])
        console.clear()
        tree = Tree(f"[bold cyan]{label}[/bold cyan] (원격)")
        _build_tree(tree, nodes)
        console.print(tree)

        console.print("\n[dim]파일 경로를 직접 입력하여 열람하거나 엔터로 돌아가기:[/dim]")
        path = Prompt.ask("경로 (엔터=돌아가기)", default="")
        if path.strip():
            _open_file_action(path.strip())
