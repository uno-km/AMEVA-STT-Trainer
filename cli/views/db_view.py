"""
cli/views/db_view.py
원격 DB 인스펙터 (API 기반)
"""
import os, sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich import box

from cli.client.api_client import api_client

console = Console()

TABLES = [
    "tb_task",
    "tb_task_dtl",
    "tb_metric",
    "tb_metadata",
    "tb_log",
    "tb_chunk",
    "tb_checkpoint",
    "tb_thread_log",
]

def _run_query(sql: str, params=None) -> tuple:
    """(columns, rows) 반환. 원격 API 호출"""
    res = api_client.post("/api/v1/db/query", {"sql": sql, "params": params or []})
    if "error" in res:
        return None, f"❌ 서버 에러: {res['error']}"
    return res.get("columns", []), res.get("rows", [])

def _render_result(cols, rows, title="결과"):
    if cols is None:
        console.print(f"[red]{rows}[/red]")
        Prompt.ask("\n[dim]엔터[/dim]")
        return
    if not rows:
        console.print("[yellow]결과 없음[/yellow]")
        Prompt.ask("\n[dim]엔터[/dim]")
        return

    page_size = 30
    total = len(rows)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = 0

    while True:
        console.clear()
        table = Table(
            title=f"{title}  [dim]{total}행  {page+1}/{total_pages}페이지[/dim]",
            box=box.ROUNDED, show_lines=False
        )
        for c in cols:
            table.add_column(str(c), style="cyan", overflow="fold", max_width=35)

        for row in rows[page * page_size : (page + 1) * page_size]:
            table.add_row(*[str(v) if v is not None else "[dim]NULL[/dim]" for v in row])

        console.print(table)
        nav = Prompt.ask("\n[dim]n=다음  p=이전  q=닫기[/dim]", choices=["n","p","q"], default="q")
        if nav == "n" and page < total_pages - 1:
            page += 1
        elif nav == "p" and page > 0:
            page -= 1
        elif nav == "q":
            break

def _browse_table(table_name: str):
    keyword = Prompt.ask(f"[dim][{table_name}] 검색 키워드 (빈칸=전체)[/dim]", default="")

    if keyword.strip():
        # PRAGMA 쿼리로 컬럼 정보 가져오기
        cols, info_rows = _run_query(f"PRAGMA table_info({table_name})")
        if cols is None:
            console.print(f"[red]스키마 조회 실패: {info_rows}[/red]")
            Prompt.ask("\n[dim]엔터[/dim]")
            return
            
        cols_info = [r[1] for r in info_rows]
        where = " OR ".join([f"CAST({c} AS TEXT) LIKE ?" for c in cols_info])
        sql = f"SELECT * FROM {table_name} WHERE {where} LIMIT 500"
        params = [f"%{keyword}%"] * len(cols_info)
    else:
        sql = f"SELECT * FROM {table_name} LIMIT 500"
        params = []

    with console.status("[yellow]서버에서 DB 조회 중...[/yellow]"):
        cols, rows = _run_query(sql, params)
    _render_result(cols, rows, title=f"🗄️ {table_name} (원격)")

def show_db_viewer():
    while True:
        console.clear()
        console.print(Panel("[bold cyan]🗄️ 원격 DB 인스펙터 (API)[/bold cyan]", expand=False))
        console.print("[dim]테이블 번호를 선택하거나 S를 눌러 커스텀 SQL을 실행하세요[/dim]\n")

        for i, t in enumerate(TABLES, 1):
            console.print(f"  [cyan]{i:2d}[/cyan]  {t}")

        console.print(f"\n  [bold yellow]S[/bold yellow]  ⚡ 커스텀 SELECT SQL 실행")
        console.print(f"  [red]0[/red]  ◀ 돌아가기\n")

        choices = [str(i) for i in range(len(TABLES) + 1)] + ["s", "S"]
        pick = Prompt.ask("선택", default="0")
        if pick.lower() == "s":
            _run_custom_sql()
        elif pick == "0":
            return
        elif pick.isdigit() and 1 <= int(pick) <= len(TABLES):
            _browse_table(TABLES[int(pick) - 1])

def _run_custom_sql():
    console.clear()
    console.print(Panel("[bold yellow]⚡ 커스텀 SELECT SQL 실행 (원격)[/bold yellow]", expand=False))
    console.print("[dim]예시: SELECT * FROM tb_task WHERE status='SUCCESS'[/dim]")
    console.print("[dim]      SELECT task_id, COUNT(*) FROM tb_metric GROUP BY task_id[/dim]\n")

    sql = Prompt.ask("SQL 입력")
    if not sql.strip():
        return
        
    with console.status("[yellow]쿼리 실행 중...[/yellow]"):
        cols, rows = _run_query(sql)
    _render_result(cols, rows, title="원격 커스텀 쿼리 결과")
