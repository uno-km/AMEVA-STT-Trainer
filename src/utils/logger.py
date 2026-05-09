"""
src/utils/logger.py
Rich 라이브러리를 활용한 프리미엄 대시보드 로거.
"""
import os
import psutil
from datetime import datetime
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from src.core.config import LOG_DIR

# Rich 콘솔 객체: 터미널에 색상·스타일 출력 담당
console = Console()
# 파이프라인 실행 로그를 저장할 파일 절대 경로
RUN_LOG_PATH = os.path.join(LOG_DIR, "pipeline_run.log")

# 대시보드에 표시할 전역 상태 값을 보관하는 클래스
class UIState:
    current_task = "대기 중"      # 현재 수행 중인 주 작업 이름
    total_progress = 0            # 전체 진행률 (현재 미사용, 확장 예비)
    sub_task = ""                 # 하위 작업 설명 (대시보드 우측 표시)
    start_time = datetime.now()   # 파이프라인 시작 시각 (경과 시간 계산용)

# 싱글톤처럼 사용하는 전역 상태 인스턴스
state = UIState()

def get_color_by_pct(pct: float) -> str:
    """RGB 보간을 이용해 초록->노랑->빨강으로 부드럽게 색상 반환 (1% 단위)"""
    # 0 미만이거나 100 초과인 값을 안전 범위로 고정
    pct = max(0, min(100, pct))  # 0~100 사이로 클램핑
    
    if pct < 50:
        # 0% (Green: 0, 255, 0) -> 50% (Yellow: 255, 255, 0)
        # R만 0에서 255로 증가
        r = int((pct / 50) * 255)
        g = 255
        b = 0
    else:
        # 50% (Yellow: 255, 255, 0) -> 100% (Red: 255, 0, 0)
        # G만 255에서 0으로 감소
        r = 255
        g = int(255 - ((pct - 50) / 50) * 255)
        b = 0
    
    # Rich의 헥사코드 포맷 (#RRGGBB) 반환
    return f"#{r:02x}{g:02x}{b:02x}"

def create_status_layout():
    """하단에 고정될 시스템 상태바 레이아웃 생성"""
    # psutil 로 현재 CPU 점유율(%) 수집
    cpu = psutil.cpu_percent()
    # psutil 로 현재 RAM 점유율(%) 수집
    ram = psutil.virtual_memory().percent
    # 파이프라인 시작 후 경과 시간 (초 단위 이하 절삭)
    elapsed = str(datetime.now() - state.start_time).split(".")[0]

    # CPU·RAM 점유율에 따라 동적으로 색상 결정
    cpu_color = get_color_by_pct(cpu)
    ram_color = get_color_by_pct(ram)

    # 2열 그리드 테이블: 왼쪽(작업 상태) / 오른쪽(시스템 자원)
    table = Table.grid(expand=True)
    table.add_column(justify="left", ratio=1)
    table.add_column(justify="right", ratio=1)

    # 왼쪽: 현재 작업 상태 + 구분선
    status_text = Text.assemble(
        (f" [TASK] {state.current_task} ", "bold magenta"),
        (f" | {state.sub_task}", "dim white") if state.sub_task else ""
    )
    
    # 오른쪽: 시스템 자원 정보 (동적 색상 적용)
    sys_info = Text.assemble(
        (" CPU ", "bold white"), (f"{cpu:>4}% ", cpu_color),
        (" RAM ", "bold white"), (f"{ram:>4}% ", ram_color),
        (" TIME ", "bold white"), (f"{elapsed} ", "yellow")
    )

    # 두 열에 상태 텍스트와 시스템 정보를 각각 배치
    table.add_row(status_text, sys_info)
    
    # 전체 테이블을 패널로 감싸 테두리와 제목 추가
    return Panel(
        table,
        title="[bold blue]AMEVA-STT 실시간 대시보드[/]",
        border_style="blue",
        padding=(0, 1)
    )

def _write_to_file(level: str, message: str):
    # 로그 디렉터리가 없으면 생성
    os.makedirs(LOG_DIR, exist_ok=True)
    # 현재 시각을 'YYYY-MM-DD HH:MM:SS' 형식으로 포맷팅
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 로그 파일에 타임스탬프·레벨·메시지를 한 줄로 추가 기록
    with open(RUN_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [{level}] {message}\n")

def info(message: str):
    # 파일에 INFO 레벨로 기록 후 터미널에 파란색으로 출력
    _write_to_file("INFO", message)
    console.print(f"[bold blue]INFO[/] {message}")

def warning(message: str):
    # 파일에 WARNING 레벨로 기록 후 터미널에 노란색으로 출력
    _write_to_file("WARNING", message)
    console.print(f"[bold yellow]WARN[/] [yellow]{message}[/]")

def error(message: str):
    # 파일에 ERROR 레벨로 기록 후 터미널에 빨간색 밑줄로 출력
    _write_to_file("ERROR", message)
    console.print(f"[bold red]ERR [/] [red]{message}[/]", style="underline")

def success(message: str):
    # 파일에 SUCCESS 레벨로 기록 후 터미널에 초록색으로 출력
    _write_to_file("SUCCESS", message)
    console.print(f"[bold green]OK  [/] [green]{message}[/]")

def dashboard_context():
    # 대시보드 시작 시각을 현재 시각으로 초기화
    state.start_time = datetime.now()
    # Live 컨텍스트 매니저 반환: with 블록 안에서 대시보드가 실시간 갱신됨
    return Live(create_status_layout(), refresh_per_second=4, get_renderable=create_status_layout)

def set_status(main_task: str = None, sub_task: str = None):
    # 주 작업 이름이 전달되면 전역 상태에 반영
    if main_task: state.current_task = main_task
    # 하위 작업 설명이 전달되면 전역 상태에 반영
    if sub_task: state.sub_task = sub_task
