"""
cli/views/tasks.py
태스크 목록, 액션 다이얼로그, 신규 태스크 시작
"""
import os, sys, json

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.text import Text
from rich import box
from rich.columns import Columns

console = Console()

def _get_status_style(status: str) -> str:
    return {"SUCCESS": "bold green", "RUNNING": "bold yellow", "FAILED": "bold red", "CANCELED": "bold magenta"}.get(status, "dim")

def _get_level_label(level: int) -> str:
    return {1: "1단계 데이터 수집", 2: "2단계 학습", 3: "3단계 내보내기"}.get(level, f"Lv.{level}")

def show_task_list():
    from src.backend.api.pipeline_api import list_tasks
    from src.backend.core.database import db_manager

    while True:
        console.clear()
        console.print(Panel("[bold cyan]📋 태스크 관리[/bold cyan]", expand=False))

        res = list_tasks()
        tasks = res.get("tasks", [])

        if not tasks:
            console.print("[yellow]등록된 태스크가 없습니다.[/yellow]")
            Prompt.ask("\n[dim]엔터를 눌러 돌아가기[/dim]")
            return

        table = Table(box=box.ROUNDED, show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("태스크 명", style="cyan", min_width=20)
        table.add_column("ID (short)", style="dim", width=10)
        table.add_column("단계", style="magenta", width=18)
        table.add_column("상태", width=12)
        table.add_column("생성일시", style="dim", width=20)

        for i, t in enumerate(tasks, 1):
            status_text = Text(t['status'], style=_get_status_style(t['status']))
            table.add_row(
                str(i),
                t['tsk_nm'],
                t['id'][:8],
                _get_level_label(t.get('level', 1)),
                status_text,
                t.get('create_dt', 'N/A')
            )

        console.print(table)
        console.print("\n[dim]태스크 번호를 입력하면 액션을 선택합니다. [bold]0[/bold] = 메인으로[/dim]")

        choices = [str(i) for i in range(len(tasks) + 1)]
        pick = Prompt.ask("번호 선택", choices=choices, default="0")
        if pick == "0":
            return

        task = tasks[int(pick) - 1]
        _show_task_action_menu(task, db_manager)


def _show_task_action_menu(task: dict, db_manager):
    from src.backend.api.pipeline_api import start_train, stop_task
    from src.backend.core.reporter import report_generator
    from cli.views.monitor import watch_logs

    task_id = task['id']
    level = task.get('level', 1)
    status = task.get('status', 'FAILED')
    name = task['tsk_nm']

    while True:
        console.clear()
        status_style = _get_status_style(status)
        
        # --- traceback 파서 ---
        traceback_msg = ""
        if status in ("FAILED", "CANCELED", "STOPPED"):
            try:
                logs = db_manager.get_logs(task_id, limit=20)
                # reversed get_all returns chronologically, so we check bottom-up by reversing the list
                for log in reversed(logs):
                    msg = log.get('message', '')
                    if any(err in msg for err in ["Error:", "Exception:", "Traceback", "AttributeError", "OutOfMemoryError"]):
                        traceback_msg = f"\n\n[bold red]❌ 실패 원인:[/bold red] [yellow]{msg.strip()[:200]}[/yellow]"
                        break
            except:
                pass
                
        console.print(Panel(
            f"[bold]{name}[/bold]\n"
            f"ID: [dim]{task_id}[/dim]\n"
            f"상태: [{status_style}]{status}[/{status_style}]  |  {_get_level_label(level)}{traceback_msg}",
            title="🎯 태스크 액션", expand=False, border_style="cyan"
        ))

        options = []

        if level == 1:
            if status == "SUCCESS":
                options.append(("1", "➡️  2단계 모델 학습 설정으로 이동 (next_stage)", "next_stage"))
                options.append(("2", "🔍  1단계 리포트 열기", "view_report"))
                options.append(("3", "🔄  1단계 처음부터 재수행", "retry_stage"))
            elif status in ("FAILED", "CANCELED", "STOPPED"):
                meta_path = os.path.join(project_root, "dataset", f"{name}_{task_id[:8]}", "metadata.csv")
                has_meta = os.path.exists(meta_path)
                
                options.append(("1", "🛠️  1단계 이어서 수집 재개 (resume)", "resume_stage", "bold yellow"))
                if has_meta:
                    options.append(("2", "➡️  2단계 모델 학습 설정으로 이동 (중단 시점의 데이터로)", "next_stage", "bold green"))
                options.append(("3", "🔄  1단계 처음부터 재수행", "retry_stage"))
        elif level == 2:
            if status == "SUCCESS":
                options.append(("1", "➡️  3단계 내보내기로 이동 (next_stage)", "next_stage"))
            if status in ("FAILED", "CANCELED", "STOPPED"):
                options.append(("1", "🛠️  직전 체크포인트부터 이어서 학습 재개 (resume)", "resume_stage", "bold yellow"))
                options.append(("2", "➡️  3단계 내보내기로 이동", "next_stage"))
                options.append(("3", "🔄  2단계 처음부터 재수행", "retry_stage"))
            options.append(("r", "🔍  로그/리포트 확인", "view_report"))
        elif level == 3:
            options.append(("1", "🔍  최종 리포트 열기", "view_report", "bold green"))
            options.append(("2", "🔄  3단계 재수행", "retry_stage"))

        if status == "RUNNING":
            options.append(("s", "⛔  강제 종료", "stop"))

        options.append(("l", "📡  실시간 로그 모니터링", "logs"))
        options.append(("k", "🏁  체크포인트 이력 확인", "checkpoints"))
        options.append(("0", "◀  돌아가기", "back"))

        for key, label, *_ in options:
            style = _[1] if len(_) > 1 else "white"
            console.print(f"  [{style}]{key}[/{style}]  {label}")

        action_map = {o[0]: o[2] for o in options}
        pick = Prompt.ask("\n선택", choices=list(action_map.keys()), default="0")
        action = action_map[pick]

        if action == "back":
            return

        elif action == "logs":
            watch_logs(task_id)

        elif action == "checkpoints":
            _show_checkpoint_history(task_id, db_manager)

        elif action == "stop":
            if Confirm.ask("[bold red]정말 강제 종료하시겠습니까?[/bold red]", default=False):
                res = stop_task({"task_id": task_id})
                console.print(f"[yellow]종료 요청 결과: {res}[/yellow]")
                Prompt.ask("\n[dim]엔터[/dim]")
                return

        elif action == "view_report":
            _show_report(task_id, db_manager)

        elif action in ("next_stage", "retry_stage", "resume_stage"):
            _launch_action(action, task, db_manager, start_train)
            return


def _show_checkpoint_history(task_id: str, db_manager):
    console.clear()
    ckpts = []
    try:
        with db_manager.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT ckpt_id, ckpt_name, ckpt_path, create_dt FROM tb_checkpoint "
                "WHERE task_id = ? ORDER BY ckpt_id ASC", (task_id,)
            )
            ckpts = cur.fetchall()
    except Exception as e:
        console.print(f"[red]오류: {e}[/red]")

    if not ckpts:
        console.print("[yellow]기록된 체크포인트가 없습니다.[/yellow]")
    else:
        table = Table(title=f"🏁 체크포인트 이력 ({task_id[:8]})", box=box.ROUNDED)
        table.add_column("ID", style="dim", width=5)
        table.add_column("체크포인트 명", style="cyan")
        table.add_column("저장 시각", style="dim")
        table.add_column("경로 존재", width=8)
        for r in ckpts:
            exists = "✅" if os.path.exists(r["ckpt_path"]) else "❌"
            table.add_row(str(r["ckpt_id"]), r["ckpt_name"], r["create_dt"], exists)
        console.print(table)

    Prompt.ask("\n[dim]엔터를 눌러 돌아가기[/dim]")


def _show_report(task_id: str, db_manager):
    from src.backend.core.reporter import report_generator
    console.clear()
    console.print(Panel("[bold]📜 리포트 생성 중...[/bold]", expand=False))

    task = db_manager.get_task_details(task_id)
    if not task:
        console.print("[red]태스크 정보를 찾을 수 없습니다.[/red]")
        Prompt.ask("\n[dim]엔터[/dim]")
        return

    logs = db_manager.get_logs(task_id, limit=500)

    table = Table(title=f"태스크 요약: {task['tsk_nm']}", box=box.ROUNDED)
    table.add_column("항목", style="cyan", width=20)
    table.add_column("값", style="white")
    table.add_row("태스크 ID", task['id'])
    table.add_row("상태", task.get('status', 'N/A'))
    table.add_row("단계", _get_level_label(task.get('level', 1)))
    table.add_row("생성일시", task.get('create_dt', 'N/A'))
    table.add_row("모델 경로", task.get('model_path', 'N/A') or 'N/A')
    table.add_row("리포트 경로", task.get('report_path', 'N/A') or 'N/A')
    console.print(table)

    console.print(f"\n[dim]최근 로그 (최대 20개):[/dim]")
    log_table = Table(box=box.MINIMAL, show_header=False)
    log_table.add_column("Time", style="dim", width=10)
    log_table.add_column("Level", width=8)
    log_table.add_column("Message")
    level_styles = {"INFO": "white", "ERROR": "bold red", "WARNING": "bold yellow", "SUCCESS": "bold green"}
    for log in logs[-20:]:
        dt = log.get('create_dt', '')
        time_part = dt.split(' ')[-1] if ' ' in dt else dt
        lvl = log.get('level', 'INFO')
        log_table.add_row(time_part, f"[{level_styles.get(lvl,'white')}][{lvl}][/{level_styles.get(lvl,'white')}]", log.get('message',''))
    console.print(log_table)

    word_path = task.get('report_path')
    if Confirm.ask("\n📄 Word 보고서 생성 및 저장하시겠습니까?", default=False):
        try:
            with console.status("[yellow]Word 보고서 생성 중...[/yellow]"):
                path = report_generator.generate_task_report(task_id)
            console.print(f"[bold green]✅ 저장 완료: {path}[/bold green]")
            if sys.platform == 'win32' and Confirm.ask("Word 파일 바로 열기?", default=True):
                os.startfile(path)
        except Exception as e:
            console.print(f"[red]Word 보고서 생성 실패: {e}[/red]")

    Prompt.ask("\n[dim]엔터를 눌러 돌아가기[/dim]")


def _launch_action(action: str, task: dict, db_manager, start_train_fn):
    task_id = task['id']
    level = task.get('level', 1)

    console.clear()

    if action == "resume_stage":
        if level == 1:
            console.print(Panel("[bold yellow]🛠️ 1단계 이어서 수집 재개[/bold yellow]", expand=False))
            step_limit = 2 if Confirm.ask("2단계(학습)까지 자동 연결하시겠습니까?", default=True) else 1
            payload = {"task_id": task_id, "step_limit": step_limit}
            res = start_train_fn(payload)
            console.print(f"[bold green]✅ 이어하기 시작: {res}[/bold green]")
        else:
            console.print(Panel("[bold yellow]🛠️ 직전 체크포인트에서 학습 재개[/bold yellow]", expand=False))
            latest = db_manager.get_latest_checkpoint(task_id, step_level=2)
            if latest:
                console.print(f"[green]감지된 체크포인트: {latest['ckpt_name']}[/green]")
                console.print(f"[dim]경로: {latest['ckpt_path']}[/dim]")
            else:
                console.print("[yellow]⚠ tb_checkpoint에 기록된 체크포인트가 없습니다. 디스크에서 탐색합니다.[/yellow]")

            row = _get_saved_params(task_id, 2, db_manager)
            params = _fill_step2_params(row)
            if not Confirm.ask("\n위 파라미터로 이어서 학습을 재개하시겠습니까?", default=True):
                return
            payload = {"task_id": task_id, "step_limit": 2, "step2_params": params}
            res = start_train_fn(payload)
            console.print(f"[bold green]✅ 이어하기 시작: {res}[/bold green]")

    elif action == "retry_stage":
        target_step = level
        console.print(Panel(f"[bold]🔄 {_get_level_label(target_step)} 처음부터 재시작[/bold]", expand=False))
        if target_step == 2:
            row = _get_saved_params(task_id, 2, db_manager)
            params = _fill_step2_params(row)
            payload = {"task_id": task_id, "step_limit": 2, "step2_params": params}
            res = start_train_fn(payload)
        elif target_step == 3:
            row = _get_saved_params(task_id, 3, db_manager)
            method = json.loads(row or '{}').get('method', 'q4_0') if row else 'q4_0'
            payload = {"task_id": task_id, "step_limit": 3, "step3_params": {"action": "export_model", "auto_export": True, "method": method}}
            res = start_train_fn(payload)
        console.print(f"[bold green]✅ 재시작: {res}[/bold green]")

    elif action == "next_stage":
        next_step = level + 1
        console.print(Panel(f"[bold cyan]➡️ {_get_level_label(next_step)}으로 이동[/bold cyan]", expand=False))
        if next_step == 2:
            params = _prompt_step2_params()
            step_limit = 3 if Confirm.ask("3단계(내보내기)까지 자동 실행?", default=True) else 2
            step3 = _prompt_step3_params() if step_limit == 3 else {}
            payload = {"task_id": task_id, "step_limit": step_limit, "step2_params": params, "step3_params": step3}
            res = start_train_fn(payload)
        elif next_step == 3:
            step3 = _prompt_step3_params()
            payload = {"task_id": task_id, "step_limit": 3, "step2_params": {}, "step3_params": step3}
            res = start_train_fn(payload)
        console.print(f"[bold green]✅ 진행 시작: {res}[/bold green]")

    from cli.views.monitor import watch_logs
    if Confirm.ask("\n실시간 로그 모니터링을 시작하시겠습니까?", default=True):
        watch_logs(task_id)


def _get_saved_params(task_id: str, step_seq: int, db_manager) -> str:
    try:
        with db_manager.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT parameters FROM tb_task_dtl WHERE task_id=? AND step_seq=? ORDER BY dtl_id DESC LIMIT 1",
                (task_id, step_seq)
            )
            row = cur.fetchone()
            return row[0] if row else None
    except:
        return None


def _fill_step2_params(raw_json: str) -> dict:
    defaults = {"action":"start_training","model_id":"openai/whisper-tiny","max_steps":400,"learning_rate":"0.0001","batch_size":2,"gradient_accumulation":8}
    if raw_json:
        try:
            saved = json.loads(raw_json)
            defaults.update(saved)
        except:
            pass

    console.print("\n[dim]학습 파라미터 (저장된 값이 기본값입니다 - 엔터로 유지):[/dim]")
    model_id = Prompt.ask("모델 ID", default=defaults.get("model_id","openai/whisper-tiny"))
    max_steps = IntPrompt.ask("Max Steps", default=int(defaults.get("max_steps", 400)))
    lr = Prompt.ask("Learning Rate", default=str(defaults.get("learning_rate","0.0001")))
    batch = IntPrompt.ask("Batch Size", default=int(defaults.get("batch_size", 2)))
    grad_acc = IntPrompt.ask("Gradient Accumulation", default=int(defaults.get("gradient_accumulation", 8)))
    return {"action":"start_training","model_id":model_id,"max_steps":max_steps,"learning_rate":lr,"batch_size":batch,"gradient_accumulation":grad_acc}


def _prompt_step2_params() -> dict:
    return _fill_step2_params(None)


def _prompt_step3_params() -> dict:
    method = Prompt.ask("양자화 방식 (q4_0 / f16 / q8_0)", default="q4_0")
    return {"action":"export_model","auto_export":True,"method":method}


def start_new_task():
    from src.backend.api.pipeline_api import init_data
    from cli.views.monitor import watch_logs

    console.clear()
    console.print(Panel("[bold green]🚀 신규 학습 파이프라인 시작[/bold green]", expand=False))
    console.print("[dim]각 항목을 입력하세요. 엔터를 누르면 기본값 적용[/dim]\n")

    task_name = Prompt.ask("[cyan]1.[/cyan] 태스크 명", default="CLI_Project")
    source_type = Prompt.ask("[cyan]2.[/cyan] 데이터 소스 (youtube / local)", choices=["youtube","local"], default="youtube")

    if source_type == "youtube":
        url = Prompt.ask("[cyan]3.[/cyan] YouTube 채널 URL", default="https://www.youtube.com/@syukaworld/videos")
        count = IntPrompt.ask("[cyan]4.[/cyan] 수집할 최신 영상 개수", default=10)
        s1 = {"source_type":"youtube","url":url,"count":count}
    else:
        folder = Prompt.ask("[cyan]3.[/cyan] 로컬 폴더 경로")
        s1 = {"source_type":"local","folder":folder}

    model_id = Prompt.ask("[cyan]5.[/cyan] 베이스 모델 (openai/whisper-tiny / small / medium)", default="openai/whisper-tiny")
    max_steps = IntPrompt.ask("[cyan]6.[/cyan] Max Steps", default=400)
    lr = Prompt.ask("[cyan]7.[/cyan] Learning Rate", default="0.0001")
    batch = IntPrompt.ask("[cyan]8.[/cyan] Batch Size", default=2)
    grad_acc = IntPrompt.ask("[cyan]9.[/cyan] Gradient Accumulation", default=8)

    auto_export = Confirm.ask("[cyan]10.[/cyan] 학습 후 GGUF 자동 내보내기?", default=True)
    export_method = "q4_0"
    if auto_export:
        export_method = Prompt.ask("[cyan]11.[/cyan] 양자화 방식 (q4_0 / f16)", default="q4_0")

    step_limit = 3 if auto_export else 2
    body = {
        "name": task_name,
        "step_limit": step_limit,
        "step1_params": s1,
        "step2_params": {"action":"start_training","model_id":model_id,"max_steps":max_steps,"learning_rate":lr,"batch_size":batch,"gradient_accumulation":grad_acc},
        "step3_params": {"action":"export_model","auto_export":auto_export,"method":export_method}
    }

    console.print("\n[bold yellow]파이프라인 시작 요청 전송 중...[/bold yellow]")
    try:
        res = init_data(body)
        task_id = res.get("id")
        console.print(f"[bold green]✅ 파이프라인 시작! Task ID: {task_id}[/bold green]")
        if Confirm.ask("\n실시간 로그 모니터링 시작?", default=True):
            watch_logs(task_id)
    except Exception as e:
        console.print(f"[bold red]❌ 오류: {e}[/bold red]")
        Prompt.ask("\n[dim]엔터[/dim]")
