"""
scripts/check_hardware.py
AMEVA-STT-Trainer 하드웨어 환경 진단 및 Rich 대시보드

실행 시 자동으로:
  1. CPU / GPU / VRAM / CUDA / PyTorch 환경을 진단합니다.
  2. GPU Tier를 결정하고 적용될 학습 파라미터를 안내합니다.
  3. Rich 패널로 현재 환경 상태를 시각적으로 출력합니다.
  4. PyTorch가 CPU 빌드인데 NVIDIA GPU가 있다면 복구 가이드를 제공합니다.

단독 실행:
    python scripts/check_hardware.py

다른 스크립트에서 임포트:
    from scripts.check_hardware import run_preflight
    hw = run_preflight()
"""
import os
import sys
import time

# 프로젝트 루트 등록
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 윈도우 한글 깨짐 방지
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich import box

console = Console()

# ---------------------------------------------------------------------------- #
#  색상 테마                                                                    #
# ---------------------------------------------------------------------------- #
_COLOR_OK      = "bold green"
_COLOR_WARN    = "bold yellow"
_COLOR_ERR     = "bold red"
_COLOR_INFO    = "bold cyan"
_COLOR_DIM     = "dim"
_COLOR_HEADING = "bold white"
_COLOR_TITLE   = "bold magenta"

# ---------------------------------------------------------------------------- #
#  아이콘 매핑                                                                  #
# ---------------------------------------------------------------------------- #
_TIER_ICONS = {
    0: "🖥️ ",
    1: "🎮",
    2: "⚡",
    3: "🚀",
}
_TIER_COLORS = {
    0: "white",
    1: "yellow",
    2: "green",
    3: "bold green",
}
_TIER_LABELS = {
    0: "CPU 전용 모드",
    1: "구형 GPU 모드 (Pascal/Turing Entry)",
    2: "보급형 GPU 가속 모드",
    3: "고사양 GPU 풀 가속 모드",
}


def _make_status(ok: bool, text_ok: str, text_fail: str) -> Text:
    if ok:
        return Text(f"✅  {text_ok}", style=_COLOR_OK)
    else:
        return Text(f"❌  {text_fail}", style=_COLOR_ERR)


def _make_row(label: str, value: str, style: str = "") -> tuple:
    return (f"  {label}", Text(value, style=style) if style else value)


def run_preflight(silent: bool = False) -> "HWProfile":  # noqa: F821
    """
    하드웨어 진단을 실행하고 Rich 대시보드를 출력합니다.
    
    Args:
        silent: True이면 Rich 출력을 억제하고 HWProfile만 반환합니다.
    
    Returns:
        HWProfile: 감지된 하드웨어 프로파일
    """
    from src.core.hardware_profile import get_profile, HWProfile

    if not silent:
        console.print()
        console.print(Rule(
            title="[bold magenta]AMEVA-STT-Trainer · System Preflight Check[/bold magenta]",
            style="magenta"
        ))
        console.print()

    # --- 진단 스피너 ---
    hw: HWProfile = None
    if not silent:
        with Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("[cyan]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("하드웨어 환경 스캔 중...", total=None)
            time.sleep(0.3)
            progress.update(task, description="CPU 정보 수집 중...")
            time.sleep(0.2)
            progress.update(task, description="GPU 및 CUDA 환경 탐지 중...")
            hw = get_profile(force_refresh=True)
            time.sleep(0.2)
            progress.update(task, description="PyTorch 빌드 정합성 검증 중...")
            time.sleep(0.2)
    else:
        hw = get_profile(force_refresh=True)

    if silent:
        return hw

    # ─────────────────────────────────────────────
    # [1] 하드웨어 요약 테이블
    # ─────────────────────────────────────────────
    hw_table = Table(
        box=box.SIMPLE,
        show_header=False,
        expand=True,
        padding=(0, 1),
    )
    hw_table.add_column("항목", style="dim cyan", width=18)
    hw_table.add_column("값", style="white")

    # CPU
    hw_table.add_row("🖥️   CPU", f"[bold white]{hw.cpu_name}[/bold white]  [{hw.cpu_threads} Threads]")

    # GPU
    if hw.tier > 0:
        tier_color = _TIER_COLORS[hw.tier]
        tier_label = _TIER_LABELS[hw.tier]
        gpu_text = (
            f"[{tier_color}]{hw.gpu_name}[/{tier_color}]  "
            f"[dim]▸ Tier {hw.tier}: {tier_label}[/dim]"
        )
        hw_table.add_row(f"{_TIER_ICONS[hw.tier]}  GPU", gpu_text)

        # VRAM
        vram_color = "green" if hw.vram_mb >= 8192 else "yellow"
        hw_table.add_row(
            "💾  VRAM",
            f"[{vram_color}]{hw.vram_mb:,} MB ({hw.vram_mb / 1024:.1f} GB)[/{vram_color}]"
        )

        # Compute Capability
        cc = hw.compute_cap
        cc_str = f"{cc[0]}.{cc[1]}"
        arch_map = {
            (5, 0): "Maxwell", (5, 2): "Maxwell",
            (6, 0): "Pascal", (6, 1): "Pascal", (6, 2): "Pascal",
            (7, 0): "Volta", (7, 2): "Volta", (7, 5): "Turing",
            (8, 0): "Ampere", (8, 6): "Ampere", (8, 9): "Ada Lovelace",
            (9, 0): "Hopper",
        }
        arch_name = arch_map.get(cc, f"SM_{cc_str}")
        has_tensor_core = cc >= (7, 0)
        tc_badge = "[green]Tensor Core ✓[/green]" if has_tensor_core else "[yellow]Tensor Core ✗ (CUDA Core FP16)[/yellow]"
        hw_table.add_row(
            "⚡  Compute Cap",
            f"[bold]{cc_str}[/bold]  [{arch_name}]  {tc_badge}"
        )

        # CUDA 버전
        hw_table.add_row(
            "🔧  CUDA",
            f"[cyan]{hw.cuda_version}[/cyan]  [dim](torch build: {hw.torch_build_cuda})[/dim]"
        )
    else:
        hw_table.add_row("🖥️   GPU", "[dim]NVIDIA GPU 미감지 (CPU 전용 모드)[/dim]")

    # PyTorch
    pt_status = "✅  GPU 가속 활성" if hw.torch_cuda_available else "🖥️   CPU 전용"
    pt_color = "green" if hw.torch_cuda_available else "white"
    hw_table.add_row(
        "🔥  PyTorch",
        f"[{pt_color}]{hw.torch_version}[/{pt_color}]  [dim]▸ {pt_status}[/dim]"
    )

    console.print(Panel(
        hw_table,
        title="[bold cyan]🔍 하드웨어 환경[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))

    # ─────────────────────────────────────────────
    # [2] 학습 프로파일 테이블
    # ─────────────────────────────────────────────
    profile_table = Table(
        box=box.SIMPLE,
        show_header=True,
        expand=True,
        padding=(0, 1),
    )
    profile_table.add_column("파라미터", style="dim cyan", width=22)
    profile_table.add_column("적용 값", style="bold yellow")
    profile_table.add_column("설명", style="dim")

    tier_icon = _TIER_ICONS.get(hw.tier, "")
    tier_color = _TIER_COLORS.get(hw.tier, "white")

    profile_table.add_row(
        "학습 모드",
        Text(f"{tier_icon} {hw.profile_name}", style=tier_color),
        f"Tier {hw.tier}"
    )
    profile_table.add_row(
        "batch_size",
        str(hw.batch_size),
        "GPU당 샘플 수"
    )
    profile_table.add_row(
        "gradient_accumulation",
        str(hw.gradient_accumulation),
        f"실질 배치 = {hw.batch_size * hw.gradient_accumulation}"
    )
    profile_table.add_row(
        "fp16",
        "[green]ON[/green]" if hw.fp16 else "[dim]OFF (FP32)[/dim]",
        "Half-precision GPU 가속" if hw.fp16 else "Full-precision CPU 안정 모드"
    )
    profile_table.add_row(
        "gradient_checkpointing",
        "[yellow]ON[/yellow]" if hw.gradient_checkpointing else "[dim]OFF[/dim]",
        "VRAM ↔ 연산 트레이드오프" if hw.gradient_checkpointing else "비활성 (VRAM 충분)"
    )
    profile_table.add_row(
        "dataloader_pin_memory",
        "[green]ON[/green]" if hw.tier > 0 else "[dim]OFF[/dim]",
        "DMA 전송 가속" if hw.tier > 0 else "CPU 모드 비활성"
    )

    console.print(Panel(
        profile_table,
        title="[bold yellow]⚙️  자동 학습 프로파일[/bold yellow]",
        border_style="yellow",
        padding=(1, 2),
    ))

    # ─────────────────────────────────────────────
    # [3] 경고 및 Self-Healing 가이드
    # ─────────────────────────────────────────────
    if hw.warnings or hw.heal_actions:
        warn_text = Text()
        for w in hw.warnings:
            warn_text.append(f"{w}\n", style="yellow")
        if hw.heal_actions:
            warn_text.append("\n💊 복구 명령어:\n", style="bold yellow")
            for action in hw.heal_actions:
                warn_text.append(f"  {action}\n", style="bold white on dark_red")
        console.print(Panel(
            warn_text,
            title="[bold yellow]⚠️  경고[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        ))

    # ─────────────────────────────────────────────
    # [4] 최종 상태 배너
    # ─────────────────────────────────────────────
    if hw.tier > 0:
        status_color = "green"
        status_icon = "✅"
        status_msg = f"GPU 가속 학습 준비 완료  [{hw.gpu_name}  /  Tier {hw.tier}]"
    else:
        status_color = "white"
        status_icon = "🖥️ "
        if hw.warnings:
            status_color = "yellow"
            status_icon = "⚠️ "
            status_msg = "CPU 모드로 시작합니다 (NVIDIA GPU 감지됨 → 복구 가이드 참고)"
        else:
            status_msg = "CPU 전용 모드로 학습 준비 완료"

    status_line = Text(justify="center")
    status_line.append(f" {status_icon}  Status:  ", style="bold")
    status_line.append(status_msg, style=f"bold {status_color}")

    console.print(Panel(
        status_line,
        border_style=status_color,
        padding=(0, 2),
    ))
    console.print()

    return hw


# ---------------------------------------------------------------------------- #
#  단독 실행                                                                    #
# ---------------------------------------------------------------------------- #
if __name__ == "__main__":
    try:
        profile = run_preflight()
        sys.exit(0)
    except KeyboardInterrupt:
        console.print("\n[red]진단이 취소되었습니다.[/red]")
        sys.exit(1)
    except Exception as e:
        console.print_exception()
        console.print(f"\n[bold red]진단 중 예기치 않은 오류가 발생했습니다: {e}[/bold red]")
        sys.exit(1)
