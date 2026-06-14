"""
src/core/hardware_profile.py
AMEVA-STT-Trainer 하드웨어 프로파일러

실행 시 CPU / GPU / VRAM / CUDA 버전을 자동 감지하고,
학습 파라미터 자동 보정을 위한 GPU Tier를 결정합니다.

GPU Tier 분류:
  Tier 0: CPU Only (CUDA 없음)
  Tier 1: 구형 GPU  — Pascal/Turing Entry (VRAM < 8GB or CC < 7.0) → GTX 1060, 1070 Ti 등
  Tier 2: 보급형 GPU — Turing/Ampere mid (VRAM 8~12GB, CC >= 7.0) → RTX 2080, 3070 등
  Tier 3: 고사양 GPU — Ampere/Ada high (VRAM > 12GB) → RTX 3090, 4090 등
"""
import os
import sys
import subprocess
from dataclasses import dataclass, field
from typing import Optional, Tuple


# ---------------------------------------------------------------------------- #
#  HWProfile 데이터 클래스                                                      #
# ---------------------------------------------------------------------------- #

@dataclass
class HWProfile:
    """하드웨어 진단 결과를 담는 데이터 클래스."""
    # --- 기본 모드 ---
    mode: str = "cpu"                  # "cpu" | "cuda_legacy" | "cuda_modern"
    tier: int = 0                      # 0=CPU, 1=구형GPU, 2=보급형GPU, 3=고사양GPU

    # --- CPU 정보 ---
    cpu_name: str = "Unknown CPU"
    cpu_threads: int = 1

    # --- GPU 정보 ---
    gpu_name: str = "N/A"
    vram_mb: int = 0
    cuda_version: str = "N/A"
    compute_cap: Tuple[int, int] = field(default_factory=lambda: (0, 0))

    # --- PyTorch 정보 ---
    torch_version: str = "N/A"
    torch_cuda_available: bool = False
    torch_build_cuda: str = "N/A"     # torch.version.cuda 빌드 버전

    # --- 학습 프로파일 (Tier에 의해 결정됨) ---
    profile_name: str = "CPU 안정화 모드"
    batch_size: int = 2
    gradient_accumulation: int = 8
    fp16: bool = False
    gradient_checkpointing: bool = False

    # --- 진단 메시지 ---
    warnings: list = field(default_factory=list)
    heal_actions: list = field(default_factory=list)


# ---------------------------------------------------------------------------- #
#  Tier 판단 기준                                                               #
# ---------------------------------------------------------------------------- #

# VRAM 임계값 (MB 단위)
_VRAM_TIER1_MAX = 8192    # 8GB 미만 → Tier 1 (단, CC < (7,0) 도 Tier 1)
_VRAM_TIER2_MAX = 12288   # 12GB 이하 → Tier 2
# 12GB 초과 → Tier 3

# Compute Capability 임계값
_CC_MODERN = (7, 0)       # Turing 이상부터 Tensor Core FP16 지원 (CC >= 7.0)


# Tier별 학습 파라미터 매핑
_TIER_PROFILES = {
    0: {
        "name":                    "CPU 안정화 모드",
        "batch_size":              2,
        "gradient_accumulation":   8,
        "fp16":                    False,
        "gradient_checkpointing":  False,
    },
    1: {
        "name":                    "구형 GPU 안정화 모드 (Pascal/Turing Entry)",
        "batch_size":              4,
        "gradient_accumulation":   4,
        "fp16":                    True,   # Pascal CC6.1: CUDA FP16 지원하나 Tensor Core 없음 → 단순 CUDA Core FP16
        "gradient_checkpointing":  True,   # VRAM 8GB 내 안전 학습을 위해 메모리 ↔ 연산 트레이드오프 활성화
    },
    2: {
        "name":                    "보급형 GPU 가속 모드 (Turing/Ampere Mid)",
        "batch_size":              8,
        "gradient_accumulation":   2,
        "fp16":                    True,
        "gradient_checkpointing":  False,
    },
    3: {
        "name":                    "고사양 GPU 풀 가속 모드 (Ampere/Ada High)",
        "batch_size":              16,
        "gradient_accumulation":   1,
        "fp16":                    True,
        "gradient_checkpointing":  False,
    },
}


# ---------------------------------------------------------------------------- #
#  CPU 정보 수집                                                                #
# ---------------------------------------------------------------------------- #

def _get_cpu_info() -> Tuple[str, int]:
    """
    Windows WMI 또는 os.cpu_count()를 활용하여 CPU 이름 및 스레드 수 반환.
    실패 시 fallback 처리.
    """
    cpu_name = "Unknown CPU"
    cpu_threads = os.cpu_count() or 1

    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_Processor).Name"],
                capture_output=True, text=True, timeout=5
            )
            raw = result.stdout.strip()
            if raw:
                cpu_name = raw.splitlines()[0].strip()
        except Exception:
            pass

    return cpu_name, cpu_threads


# ---------------------------------------------------------------------------- #
#  GPU 정보 수집                                                                #
# ---------------------------------------------------------------------------- #

def _get_gpu_name_from_wmi() -> str:
    """
    PowerShell WMI로 NVIDIA GPU 모델명 조회.
    실패 시 "Unknown NVIDIA GPU" 반환.
    """
    if sys.platform != "win32":
        return "Unknown GPU"
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'NVIDIA' }).Name"],
            capture_output=True, text=True, timeout=6
        )
        raw = result.stdout.strip()
        if raw:
            return raw.splitlines()[0].strip()
    except Exception:
        pass
    return "Unknown NVIDIA GPU"


def _detect_cuda_from_registry() -> str:
    """
    Windows 레지스트리에서 CUDA Toolkit 버전을 탐색.
    CUDA_PATH 환경변수 주입 및 PATH 바인딩도 수행.
    반환값: "12.1" 형식의 버전 문자열, 없으면 ""
    """
    if sys.platform != "win32":
        return ""

    # 1) 환경변수 우선 확인
    cuda_path = os.environ.get("CUDA_PATH", "")
    if cuda_path and os.path.isdir(cuda_path):
        # PATH에 bin 추가
        bin_path = os.path.join(cuda_path, "bin")
        if bin_path not in os.environ.get("PATH", ""):
            os.environ["PATH"] = bin_path + ";" + os.environ.get("PATH", "")
        # 버전 파싱 시도
        try:
            ver_file = os.path.join(cuda_path, "version.txt")
            if os.path.exists(ver_file):
                with open(ver_file) as f:
                    content = f.read().strip()
                    parts = content.split()
                    if parts:
                        raw_ver = parts[-1]   # 예: "12.1.105"
                        return ".".join(raw_ver.split(".")[:2])  # "12.1"
        except Exception:
            pass
        # 경로 이름에서 버전 추출 시도 (예: C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1)
        base = os.path.basename(cuda_path.rstrip("/\\"))
        if base.startswith("v"):
            return base[1:]
        return "detected"

    # 2) 레지스트리 탐색
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             r"(Get-ItemProperty 'HKLM:\SOFTWARE\NVIDIA Corporation\GPU Computing Toolkit\CUDA' -ErrorAction SilentlyContinue).Version"],
            capture_output=True, text=True, timeout=5
        )
        raw = result.stdout.strip()
        if raw and raw != "":
            # 환경변수로 주입
            cuda_path_candidate = rf"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v{raw}"
            if os.path.isdir(cuda_path_candidate):
                os.environ["CUDA_PATH"] = cuda_path_candidate
                bin_path = os.path.join(cuda_path_candidate, "bin")
                if bin_path not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = bin_path + ";" + os.environ.get("PATH", "")
            return ".".join(raw.split(".")[:2])
    except Exception:
        pass

    return ""


# ---------------------------------------------------------------------------- #
#  메인 감지 함수                                                               #
# ---------------------------------------------------------------------------- #

def detect() -> HWProfile:
    """
    시스템 하드웨어를 전면 진단하여 HWProfile을 반환합니다.
    
    실행 순서:
      1. CPU 정보 수집
      2. CUDA 환경변수 복구 시도
      3. PyTorch CUDA 가용성 체크
      4. GPU 정보 (모델명, VRAM, Compute Capability) 수집
      5. Tier 결정 및 학습 파라미터 매핑
    """
    profile = HWProfile()

    # [1] CPU 정보
    profile.cpu_name, profile.cpu_threads = _get_cpu_info()

    # [2] CUDA 환경변수 복구 시도 (CUDA_PATH 누락 시 레지스트리에서 찾아 주입)
    registry_cuda_ver = _detect_cuda_from_registry()
    if registry_cuda_ver:
        profile.cuda_version = registry_cuda_ver

    # [3] PyTorch 임포트 및 CUDA 가용성 체크
    try:
        import torch
        profile.torch_version = torch.__version__
        profile.torch_build_cuda = torch.version.cuda or "N/A"
        profile.torch_cuda_available = torch.cuda.is_available()
    except ImportError:
        profile.warnings.append("⚠️  PyTorch가 설치되어 있지 않습니다. 먼저 설치가 필요합니다.")
        profile.mode = "cpu"
        profile.tier = 0
        _apply_tier_profile(profile)
        return profile

    # [4] CUDA 없는 경우 → Tier 0
    if not profile.torch_cuda_available:
        # PyTorch가 CPU 빌드이거나 CUDA 드라이버 없는 경우
        # 실제 NVIDIA GPU가 있는지 WMI로 확인하여 경고 제공
        gpu_wmi = _get_gpu_name_from_wmi()
        if "NVIDIA" in gpu_wmi.upper():
            profile.gpu_name = gpu_wmi
            profile.warnings.append(
                f"⚠️  NVIDIA GPU({gpu_wmi})가 감지되었으나 PyTorch CUDA를 사용할 수 없습니다."
            )
            if profile.torch_build_cuda == "N/A":
                profile.warnings.append(
                    "   → 현재 PyTorch가 CPU-only 빌드입니다. "
                    "GPU 가속을 원하면 CUDA 버전의 PyTorch를 설치하세요."
                )
                profile.heal_actions.append(
                    "pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121 --force-reinstall"
                )
            else:
                profile.warnings.append(
                    f"   → CUDA 드라이버가 오래되었거나 호환되지 않을 수 있습니다. (빌드: CUDA {profile.torch_build_cuda})"
                )
        profile.mode = "cpu"
        profile.tier = 0
        _apply_tier_profile(profile)
        return profile

    # [5] CUDA 사용 가능 → GPU 정보 수집
    import torch

    try:
        profile.gpu_name = torch.cuda.get_device_name(0)
    except Exception:
        profile.gpu_name = _get_gpu_name_from_wmi()

    try:
        props = torch.cuda.get_device_properties(0)
        profile.vram_mb = props.total_memory // (1024 * 1024)
        profile.compute_cap = (props.major, props.minor)
    except Exception:
        profile.warnings.append("⚠️  GPU 속성 조회에 실패했습니다. 기본값(Tier 1)을 사용합니다.")
        profile.compute_cap = (6, 1)
        profile.vram_mb = 0

    # torch.version.cuda가 더 정확함 (빌드 시 CUDA 버전)
    if profile.torch_build_cuda and profile.torch_build_cuda != "N/A":
        profile.cuda_version = profile.torch_build_cuda

    # [6] Tier 결정
    cc = profile.compute_cap
    vram = profile.vram_mb

    if cc < _CC_MODERN:
        # Pascal (6.x), Maxwell (5.x) 등 → Tensor Core 없음 → 무조건 Tier 1
        profile.tier = 1
        profile.mode = "cuda_legacy"
    elif vram > _VRAM_TIER2_MAX:
        profile.tier = 3
        profile.mode = "cuda_modern"
    elif vram >= _VRAM_TIER1_MAX:
        # VRAM 8~12GB, CC >= 7.0 → Tier 2
        profile.tier = 2
        profile.mode = "cuda_modern"
    else:
        # VRAM < 8GB, CC >= 7.0 (예: RTX 3060 6GB) → Tier 1로 처리
        profile.tier = 1
        profile.mode = "cuda_legacy"

    # [7] Tier 학습 파라미터 적용
    _apply_tier_profile(profile)
    return profile


def _apply_tier_profile(profile: HWProfile):
    """Tier 번호에 따라 HWProfile에 학습 파라미터를 주입합니다."""
    p = _TIER_PROFILES.get(profile.tier, _TIER_PROFILES[0])
    profile.profile_name = p["name"]
    profile.batch_size = p["batch_size"]
    profile.gradient_accumulation = p["gradient_accumulation"]
    profile.fp16 = p["fp16"]
    profile.gradient_checkpointing = p["gradient_checkpointing"]


# ---------------------------------------------------------------------------- #
#  싱글톤 캐시 (프로세스 내 1회 감지 후 재사용)                                   #
# ---------------------------------------------------------------------------- #

_cached_profile: Optional[HWProfile] = None


def get_profile(force_refresh: bool = False) -> HWProfile:
    """
    캐시된 HWProfile을 반환합니다.
    최초 호출 시 detect()를 실행하여 결과를 캐싱합니다.
    
    Args:
        force_refresh: True이면 캐시를 무시하고 재진단합니다.
    """
    global _cached_profile
    if _cached_profile is None or force_refresh:
        _cached_profile = detect()
    return _cached_profile
