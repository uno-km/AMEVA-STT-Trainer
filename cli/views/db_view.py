"""
cli/views/db_view.py
DB 인스펙터: 테이블 조회 + 커스텀 SELECT SQL 실행
"""
import os, sys, sqlite3
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich import box

console = Console()
DB_PATH = os.path.join(project_root, "db", "stt_trainer.db")

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

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _run_query(sql: str, params=None) -> tuple:
    """(columns, rows) 반환. SELECT만 허용."""
    if not sql.strip().lower().startswith("select"):
        return None, "❌ SELECT 구문만 허용됩니다."
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(sql, params or [])
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return [], []
        cols = list(rows[0].keys())
        return cols, [list(r) for r in rows]
    except Exception as e:
        return None, str(e)

def _render_result(cols, rows, title="결과"):
    if cols is None:
        console.print(f"[red]{rows}[/red]")
        return
    if not rows:
        console.print("[yellow]결과 없음[/yellow]")
        return

    # 페이지네이션
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
        # 컬럼 목록 획득 후 OR 검색
        try:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info({table_name})")
            cols_info = [r[1] for r in cur.fetchall()]
            conn.close()
            where = " OR ".join([f"CAST({c} AS TEXT) LIKE ?" for c in cols_info])
            sql = f"SELECT * FROM {table_name} WHERE {where} LIMIT 500"
            params = [f"%{keyword}%"] * len(cols_info)
        except Exception as e:
            console.print(f"[red]스키마 조회 실패: {e}[/red]")
            Prompt.ask("\n[dim]엔터[/dim]")
            return
    else:
        sql = f"SELECT * FROM {table_name} LIMIT 500"
        params = []

    cols, rows = _run_query(sql, params)
    _render_result(cols, rows, title=f"🗄️ {table_name}")


def show_db_viewer():
    while True:
        console.clear()
        console.print(Panel("[bold cyan]🗄️ DB 인스펙터[/bold cyan]", expand=False))
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
    console.print(Panel("[bold yellow]⚡ 커스텀 SELECT SQL 실행[/bold yellow]", expand=False))
    console.print("[dim]예시: SELECT * FROM tb_task WHERE status='SUCCESS'[/dim]")
    console.print("[dim]      SELECT task_id, COUNT(*) FROM tb_metric GROUP BY task_id[/dim]\n")

    sql = Prompt.ask("SQL 입력")
    if not sql.strip():
        return
    cols, rows = _run_query(sql)
    _render_result(cols, rows, title="커스텀 쿼리 결과")
