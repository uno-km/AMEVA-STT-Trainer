"""
cli/views/tasks.py
태스크 목록, 액션 다이얼로그, 신규 태스크 시작 (API-First 구조)
"""
import os, sys, json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.text import Text
from rich import box

from cli.client.api_client import api_client

console = Console()

def _get_status_style(status: str) -> str:
    return {"SUCCESS": "bold green", "RUNNING": "bold yellow", "FAILED": "bold red", "CANCELED": "bold magenta"}.get(status, "dim")

def _get_level_label(level: int) -> str:
    return {1: "1단계 데이터 수집", 2: "2단계 학습", 3: "3단계 내보내기"}.get(level, f"Lv.{level}")

def show_task_list():
    while True:
        console.clear()
        console.print(Panel("[bold cyan]📋 태스크 관리 (원격 서버 연결됨)[/bold cyan]", expand=False))

        res = api_client.get("/api/v1/tasks/list")
        if "error" in res:
            console.print(f"[red]서버 통신 오류: {res['error']}[/red]")
            Prompt.ask("\n[dim]엔터를 눌러 돌아가기[/dim]")
            return

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
                str(i), t['tsk_nm'], t['id'][:8], _get_level_label(t.get('level', 1)),
                status_text, t.get('create_dt', 'N/A')
            )

        console.print(table)
        console.print("\n[dim]태스크 번호를 입력하면 액션을 선택합니다. [bold]0[/bold] = 메인으로[/dim]")

        choices = [str(i) for i in range(len(tasks) + 1)]
        pick = Prompt.ask("번호 선택", choices=choices, default="0")
        if pick == "0":
            return

        task = tasks[int(pick) - 1]
        _show_task_action_menu(task)


def _show_task_action_menu(task: dict):
    from cli.views.monitor import watch_logs

    task_id = task['id']
    level = task.get('level', 1)
    status = task.get('status', 'FAILED')
    name = task['tsk_nm']

    while True:
        console.clear()
        status_style = _get_status_style(status)
        
        console.print(Panel(
            f"[bold]{name}[/bold]\n"
            f"ID: [dim]{task_id}[/dim]\n"
            f"상태: [{status_style}]{status}[/{status_style}]  |  {_get_level_label(level)}",
            title="🎯 태스크 액션 (API)", expand=False, border_style="cyan"
        ))

        options = []
        if level == 1:
            if status == "SUCCESS":
                options.append(("1", "➡️  2단계 모델 학습 설정으로 이동 (next_stage)", "next_stage"))
                options.append(("2", "🔄  1단계 처음부터 재수행", "retry_stage"))
            elif status in ("FAILED", "CANCELED", "STOPPED"):
                options.append(("1", "🛠️  1단계 이어서 수집 재개 (resume)", "resume_stage", "bold yellow"))
                options.append(("2", "➡️  2단계 모델 학습 설정으로 강제 이동", "next_stage", "bold green"))
                options.append(("3", "🔄  1단계 처음부터 재수행", "retry_stage"))
        elif level == 2:
            if status == "SUCCESS":
                options.append(("1", "➡️  3단계 내보내기로 이동 (next_stage)", "next_stage"))
            if status in ("FAILED", "CANCELED", "STOPPED"):
                options.append(("1", "🛠️  직전 체크포인트부터 자동 이어서 학습 (resume)", "resume_stage", "bold yellow"))
                options.append(("2", "➡️  3단계 내보내기로 이동", "next_stage"))
                options.append(("3", "🔄  2단계 처음부터 재수행", "retry_stage"))
        elif level == 3:
            options.append(("1", "🔄  3단계 재수행", "retry_stage"))

        options.append(("r", "🔍  서버 원격 리포트/로그 확인", "view_report", "bold green"))

        if status == "RUNNING":
            options.append(("s", "⛔  강제 종료 (서버 킬)", "stop"))

        options.append(("l", "📡  실시간 로그/차트 모니터링", "logs"))
        options.append(("0", "◀  돌아가기", "back"))

        for key, label, *_ in options:
            style = _[1] if len(_) > 1 else "white"
            console.print(f"  [{style}]{key}[/{style}]  {label}")

        action_map = {o[0]: o[2] for o in options}
        pick = Prompt.ask("\n선택", choices=list(action_map.keys()), default="0")
        action = action_map[pick]

        if action == "back": return
        elif action == "logs": watch_logs(task_id)
        elif action == "stop":
            if Confirm.ask("[bold red]서버에서 프로세스를 강제 종료할까요?[/bold red]", default=False):
                res = api_client.post("/api/v1/tasks/stop", {"task_id": task_id})
                console.print(f"[yellow]종료 요청 결과: {res}[/yellow]")
                Prompt.ask("\n[dim]엔터[/dim]")
                return
        elif action == "view_report":
            _show_report(task_id)
        elif action in ("next_stage", "retry_stage", "resume_stage"):
            _launch_action(action, task)
            return

def _show_report(task_id: str):
    console.clear()
    console.print(Panel("[bold]📜 원격 리포트 요청 중...[/bold]", expand=False))

    res = api_client.get(f"/api/v1/tasks/report?task_id={task_id}")
    if "error" in res:
        console.print(f"[red]오류: {res['error']}[/red]")
        Prompt.ask("\n[dim]엔터[/dim]")
        return

    task = res.get("task_info", {})
    logs = res.get("logs", [])

    table = Table(title=f"원격 태스크 요약: {task.get('tsk_nm')}", box=box.ROUNDED)
    table.add_column("항목", style="cyan", width=20)
    table.add_column("값", style="white")
    table.add_row("상태", task.get('status', 'N/A'))
    table.add_row("생성일시", task.get('create_dt', 'N/A'))
    console.print(table)

    console.print(f"\n[dim]최근 로그 (최대 10개):[/dim]")
    for log in logs[-10:]:
        console.print(f"[{log.get('level', 'INFO')}] {log.get('message', '')}")

    Prompt.ask("\n[dim]엔터를 눌러 돌아가기[/dim]")

def _launch_action(action: str, task: dict):
    task_id = task['id']
    level = task.get('level', 1)
    console.clear()

    if action == "resume_stage":
        console.print(Panel(f"[bold yellow]🛠️ {level}단계 이어서 재개 (서버 자동 구성)[/bold yellow]", expand=False))
        step_limit = level
        if Confirm.ask("다음 단계까지 연쇄(체이닝)로 가동할까요?", default=True):
            step_limit = 3 if level >= 2 else 2
        payload = {"task_id": task_id, "step_limit": step_limit}
        res = api_client.post("/api/v1/tasks/start_train", payload)
        console.print(f"[bold green]✅ 서버 응답: {res}[/bold green]")

    elif action == "retry_stage":
        console.print(Panel(f"[bold]🔄 {level}단계 처음부터 재시작[/bold]", expand=False))
        payload = {"task_id": task_id, "step_limit": level}
        res = api_client.post("/api/v1/tasks/start_train", payload)
        console.print(f"[bold green]✅ 서버 응답: {res}[/bold green]")

    elif action == "next_stage":
        next_step = level + 1
        console.print(Panel(f"[bold cyan]➡️ {next_step}단계로 이동[/bold cyan]", expand=False))
        
        step2_params = {}
        step3_params = {}
        if next_step == 2:
            model_id = Prompt.ask("학습 모델", default="openai/whisper-tiny")
            max_steps = IntPrompt.ask("Max Steps", default=400)
            learning_rate = Prompt.ask("Learning Rate", default="1e-4")
            batch = IntPrompt.ask("Batch Size", default=2)
            try:
                lr_val = float(learning_rate)
            except ValueError:
                lr_val = 1e-4
            step2_params = {
                "action": "start_training",
                "model_id": model_id,
                "max_steps": max_steps,
                "learning_rate": lr_val,
                "batch_size": batch
            }
        elif next_step == 3:
            quantize = Confirm.ask("모델 양자화를 진행합니까?", default=True)
            method = "q4_0"
            if quantize:
                method = Prompt.ask("양자화 방식", choices=["q4_0", "q4_1", "q5_0", "q5_1", "q8_0", "f16"], default="q4_0")
            step3_params = {
                "action": "export_model",
                "auto_export": True,
                "no_quantize": not quantize,
                "method": method
            }
            
        payload = {"task_id": task_id, "step_limit": next_step, "step2_params": step2_params, "step3_params": step3_params}
        res = api_client.post("/api/v1/tasks/start_train", payload)
        console.print(f"[bold green]✅ 서버 응답: {res}[/bold green]")

    from cli.views.monitor import watch_logs
    if Confirm.ask("\n실시간 로그 모니터링을 시작하시겠습니까?", default=True):
        watch_logs(task_id)

def start_new_task():
    from cli.views.monitor import watch_logs

    console.clear()
    console.print(Panel("[bold green]🚀 신규 학습 파이프라인 (원격 기동)[/bold green]", expand=False))

    task_name = Prompt.ask("[cyan]1.[/cyan] 태스크 명", default="Remote_Task")
    step_limit = IntPrompt.ask("[cyan]2.[/cyan] 파이프라인 진행 범위 (1: 수집만, 2: 학습까지, 3: 양자화/내보내기까지)", choices=[1, 2, 3], default=3)
    source_type = Prompt.ask("[cyan]3.[/cyan] 데이터 소스", choices=["youtube","local"], default="youtube")
    
    s1 = {"source_type": source_type}
    if source_type == "youtube":
        yt_url = Prompt.ask("[cyan]4.[/cyan] 유튜브 채널/영상 URL", default="https://www.youtube.com/@syukaworld/videos")
        yt_count = IntPrompt.ask("[cyan]5.[/cyan] 수집할 영상 개수", default=5)
        s1["url"] = yt_url
        s1["count"] = yt_count
    else:
        local_folder = Prompt.ask("[cyan]4.[/cyan] 로컬 데이터셋 폴더 경로", default="dataset/raw")
        s1["folder"] = local_folder

    prep_mode = Prompt.ask("[cyan]6.[/cyan] 데이터 전처리 모드", choices=["basic", "advanced"], default="basic")
    s1["mode"] = prep_mode

    step2_params = {}
    if step_limit >= 2:
        model_id = Prompt.ask("[cyan]7.[/cyan] 학습 모델", default="openai/whisper-tiny")
        max_steps = IntPrompt.ask("[cyan]8.[/cyan] Max Steps", default=400)
        learning_rate = Prompt.ask("[cyan]9.[/cyan] Learning Rate", default="1e-4")
        batch = IntPrompt.ask("[cyan]10.[/cyan] Batch Size", default=2)
        try:
            lr_val = float(learning_rate)
        except ValueError:
            lr_val = 1e-4
        step2_params = {
            "action": "start_training",
            "model_id": model_id,
            "max_steps": max_steps,
            "learning_rate": lr_val,
            "batch_size": batch
        }

    step3_params = {}
    if step_limit == 3:
        quantize = Confirm.ask("[cyan]11.[/cyan] 3단계 모델 양자화 진행 여부", default=True)
        method = "q4_0"
        if quantize:
            method = Prompt.ask("[cyan]12.[/cyan] 양자화 방식", choices=["q4_0", "q4_1", "q5_0", "q5_1", "q8_0", "f16"], default="q4_0")
        step3_params = {
            "action": "export_model",
            "auto_export": True,
            "no_quantize": not quantize,
            "method": method
        }

    body = {
        "name": task_name,
        "step_limit": step_limit,
        "step1_params": s1,
        "step2_params": step2_params,
        "step3_params": step3_params
    }

    console.print("\n[bold yellow]원격 서버로 파이프라인 기동 요청 중...[/bold yellow]")
    res = api_client.post("/api/v1/tasks/init_data", body)
    if "error" in res:
        console.print(f"[red]오류: {res['error']}[/red]")
    else:
        task_id = res.get("id")
        console.print(f"[bold green]✅ 기동 성공! Task ID: {task_id}[/bold green]")
        if Confirm.ask("\n실시간 로그 모니터링 시작?", default=True):
            watch_logs(task_id)
    Prompt.ask("\n[dim]엔터[/dim]")
