"""
setup.py
AMEVA-STT-Trainer 통합 설치 스크립트 (Windows 전용)

기존 setup/setup_env.ps1 과 setup/download_models_interactive.py 를 단일 파일로 통합.
더 이상 setup/ 폴더의 스크립트를 직접 실행할 필요 없이 이 파일 하나로 전체 환경이 구성됩니다.

실행 방법:
    python setup.py

수행 작업 순서:
    1. 가상환경(venv) 생성
    2. pip 최신 버전으로 업그레이드
    3. GPU/CUDA 환경 감지 후 적합한 PyTorch 설치
    4. 나머지 requirements.txt 패키지 설치
    5. 핵심 라이브러리 설치 검증
    6. Whisper 모델 파일 대화형 다운로드
    7. whisper.cpp 리포지토리 복제 (GGUF 양자화용)
"""

import os
import sys
import platform
import subprocess
import venv as venv_module


# ============================================================
# 설정 상수
# HF_HOME: Hugging Face 모델 캐시 저장 경로 (외부 공통 폴더)
# VENV_DIR: 가상환경 디렉터리 이름
# WHISPER_CPP_DIR: whisper.cpp 클론 대상 경로
# ============================================================
HF_HOME_PATH    = r"C:\ameva\models\stt"
VENV_DIR        = "venv"
WHISPER_CPP_DIR = os.path.join("third_party", "whisper.cpp")
REQUIREMENTS    = "requirements.txt"


# ============================================================
# 유틸리티 함수
# ============================================================

def banner(text: str):
    """
    구분선과 함께 섹션 제목을 출력한다.
    이모지/특수문자 없이 순수 ASCII 로 출력한다.
    """
    line = "=" * 60
    print(f"\n{line}")
    print(f"  {text}")
    print(f"{line}")


def step(num: int, total: int, text: str):
    """
    단계 번호와 설명을 출력한다.
    예: [1/7] Creating virtual environment...
    """
    print(f"\n[{num}/{total}] {text}")


def ok(text: str):
    """성공 메시지 출력"""
    print(f"  [OK] {text}")


def info(text: str):
    """일반 정보 메시지 출력"""
    print(f"  [INFO] {text}")


def warn(text: str):
    """경고 메시지 출력"""
    print(f"  [WARN] {text}")


def error_exit(text: str):
    """오류 메시지 출력 후 종료"""
    print(f"\n  [ERROR] {text}")
    sys.exit(1)


def ask_yes_no(question: str, default: str = "y") -> bool:
    """
    사용자에게 Y/N 질문을 하고 결과를 bool 로 반환한다.
    기본값(default)이 'y' 이면 엔터만 눌러도 Yes 로 처리된다.
    """
    # 기본값에 따라 힌트 괄호 표시 변경
    hint = "[Y/n]" if default.lower() == "y" else "[y/N]"
    try:
        val = input(f"  {question} {hint}: ").strip().lower()
        if not val:
            val = default.lower()
        return val.startswith("y")
    except KeyboardInterrupt:
        # Ctrl+C 시 기본값으로 처리
        print()
        return default.lower() == "y"


def run(cmd: list, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    """
    외부 명령을 실행하고 결과를 반환한다.
    실패 시 CalledProcessError 를 그대로 올려보낸다.
    """
    return subprocess.run(cmd, check=check, **kwargs)


# ============================================================
# 가상환경 내부 Python / pip 경로 계산
# ============================================================

def get_venv_python() -> str:
    """
    운영체제에 맞는 가상환경 내부 python 실행 파일 경로를 반환한다.
    Windows: venv/Scripts/python.exe
    Unix:    venv/bin/python
    """
    if platform.system() == "Windows":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def get_venv_pip() -> str:
    """
    운영체제에 맞는 가상환경 내부 pip 실행 파일 경로를 반환한다.
    Windows: venv/Scripts/pip.exe
    Unix:    venv/bin/pip
    """
    if platform.system() == "Windows":
        return os.path.join(VENV_DIR, "Scripts", "pip.exe")
    return os.path.join(VENV_DIR, "bin", "pip")


# ============================================================
# Step 1: 가상환경 생성
# ============================================================

def create_venv():
    """
    venv 디렉터리가 없으면 새로 생성한다.
    이미 있으면 건너뛴다.
    """
    step(1, 7, "Creating virtual environment (venv)...")
    if os.path.isdir(VENV_DIR):
        ok("Virtual environment already exists. Skipping creation.")
        return
    # 표준 라이브러리의 venv 모듈로 가상환경 생성
    venv_module.create(VENV_DIR, with_pip=True)
    ok("Virtual environment created successfully.")


# ============================================================
# Step 2: pip 업그레이드
# ============================================================

def upgrade_pip():
    """
    가상환경 내부의 pip 를 최신 버전으로 업그레이드한다.
    네트워크 연결이 필요하다.
    """
    step(2, 7, "Upgrading pip to the latest version...")
    python = get_venv_python()
    run([python, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
    ok("pip upgraded successfully.")


# ============================================================
# Step 3: GPU/CUDA 환경 감지 후 PyTorch 설치
# ============================================================

def detect_cuda_version() -> str:
    """
    Windows 레지스트리 또는 CUDA_PATH 환경변수에서 CUDA Toolkit 버전을 탐지한다.
    감지 성공 시 '12.1' 형식의 버전 문자열을 반환하고, 실패 시 빈 문자열을 반환한다.

    탐지 순서:
      1. CUDA_PATH 환경변수 확인
      2. 레지스트리(HKLM\...\GPU Computing Toolkit\CUDA) 조회
    """
    # 1차: 환경변수 CUDA_PATH 에서 버전 추출
    cuda_path = os.environ.get("CUDA_PATH", "")
    if cuda_path and os.path.isdir(cuda_path):
        # 경로 마지막 폴더명이 'v12.1' 같은 형식인 경우 파싱
        base = os.path.basename(cuda_path.rstrip("/\\"))
        if base.startswith("v") and "." in base:
            return base[1:]  # 'v12.1' -> '12.1'
        # version.txt 파일 읽기 시도
        ver_file = os.path.join(cuda_path, "version.txt")
        if os.path.exists(ver_file):
            try:
                with open(ver_file) as f:
                    parts = f.read().strip().split()
                    if parts:
                        # 'CUDA Version 12.1.105' 마지막 토큰에서 앞 두 자리만 추출
                        return ".".join(parts[-1].split(".")[:2])
            except Exception:
                pass

    # 2차: 레지스트리에서 CUDA 버전 조회 (Windows 전용)
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    r"(Get-ItemProperty 'HKLM:\SOFTWARE\NVIDIA Corporation\GPU Computing Toolkit\CUDA'"
                    r" -ErrorAction SilentlyContinue).Version"
                ],
                capture_output=True, text=True, timeout=6
            )
            ver = result.stdout.strip()
            if ver:
                return ".".join(ver.split(".")[:2])  # '12.1.105' -> '12.1'
        except Exception:
            pass

    return ""


def install_pytorch():
    """
    CUDA 버전을 감지하여 GPU 가속 PyTorch 또는 CPU 전용 PyTorch 를 설치한다.

    CUDA 12.1 이상: cu121 wheel index 사용
    CUDA 11.8:      cu118 wheel index 사용
    CUDA 없음:      CPU-only wheel index 사용

    이미 적합한 버전이 설치되어 있어도 --force-reinstall 없이 실행하므로
    이미 설치된 경우 pip 가 자동으로 스킵한다.
    """
    step(3, 7, "Detecting GPU/CUDA and installing PyTorch...")

    pip = get_venv_pip()
    cuda_ver = detect_cuda_version()

    # CUDA 버전 주요 숫자 추출 (예: '12.1' -> 12, '11.8' -> 11)
    cuda_major = 0
    cuda_minor = 0
    if cuda_ver:
        parts = cuda_ver.split(".")
        try:
            cuda_major = int(parts[0])
            cuda_minor = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            pass

    if cuda_major >= 12:
        # CUDA 12.x 계열: cu121 인덱스 사용 (12.0, 12.1, 12.4 모두 호환)
        index_url = "https://download.pytorch.org/whl/cu121"
        label = f"CUDA {cuda_ver} detected -> PyTorch cu121 (GPU)"
    elif cuda_major == 11:
        # CUDA 11.x 계열: cu118 인덱스 사용 (GTX 1070 Ti / CUDA 11.8 등)
        index_url = "https://download.pytorch.org/whl/cu118"
        label = f"CUDA {cuda_ver} detected -> PyTorch cu118 (GPU)"
    else:
        # CUDA 없음: CPU 전용 PyTorch 설치
        index_url = "https://download.pytorch.org/whl/cpu"
        label = "No CUDA detected -> PyTorch CPU-only"

    info(label)
    info(f"Index URL: {index_url}")

    # torch 와 torchaudio 를 지정된 wheel 인덱스에서 설치
    run([
        pip, "install",
        "torch", "torchaudio",
        "--index-url", index_url,
        "--quiet"
    ])
    ok("PyTorch installed successfully.")


# ============================================================
# Step 4: 나머지 패키지 설치 (requirements.txt)
# ============================================================

def install_requirements():
    """
    requirements.txt 에 명시된 나머지 패키지를 설치한다.
    torch/torchaudio 는 Step 3 에서 이미 설치했으므로 중복 설치 없이 pip 가 처리한다.
    """
    step(4, 7, f"Installing packages from {REQUIREMENTS}...")
    if not os.path.exists(REQUIREMENTS):
        error_exit(f"{REQUIREMENTS} not found. Cannot install dependencies.")
    pip = get_venv_pip()
    run([pip, "install", "-r", REQUIREMENTS, "--quiet"])
    ok("All packages installed successfully.")


# ============================================================
# Step 5: 핵심 라이브러리 설치 검증
# ============================================================

def verify_installations():
    """
    핵심 라이브러리들이 정상적으로 설치되었는지 import 로 검증한다.
    실패해도 전체 설치를 중단하지 않고 경고만 출력한다.
    """
    step(5, 7, "Verifying key library installations...")
    python = get_venv_python()

    # 검증 대상: (import 명, 출력할 이름)
    checks = [
        ("torch",          "PyTorch"),
        ("transformers",   "Transformers"),
        ("peft",           "PEFT (LoRA)"),
        ("datasets",       "Datasets"),
        ("librosa",        "Librosa (Audio)"),
        ("rich",           "Rich (CLI UI)"),
        ("fastapi",        "FastAPI (Backend)"),
        ("wandb",          "WandB (Telemetry)"),
        ("gguf",           "GGUF-Py (Quantization)"),
    ]

    all_ok = True
    for module, name in checks:
        result = subprocess.run(
            [python, "-c", f"import {module}; print({module}.__version__ if hasattr({module}, '__version__') else 'ok')"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ver = result.stdout.strip()
            print(f"  [OK] {name:<25} {ver}")
        else:
            warn(f"{name} - import failed. Check installation.")
            all_ok = False

    if all_ok:
        ok("All core libraries verified.")
    else:
        warn("Some libraries failed verification. Review warnings above.")


# ============================================================
# Step 6: Whisper 모델 대화형 다운로드
# ============================================================

def download_whisper_model(model_id: str):
    """
    지정된 Whisper 모델 ID 를 Hugging Face 에서 로컬 캐시로 다운로드한다.
    이미 다운로드된 경우 Hugging Face transformers 가 자동으로 캐시에서 로드하므로
    재다운로드 없이 빠르게 완료된다.

    Args:
        model_id: Hugging Face 모델 식별자 (예: 'openai/whisper-tiny')
    """
    python = get_venv_python()

    # 모델 가중치 다운로드
    info(f"Downloading model weights: {model_id}")
    code_model = (
        f"import os; os.environ['HF_HOME'] = r'{HF_HOME_PATH}'; "
        f"from transformers import WhisperForConditionalGeneration; "
        f"WhisperForConditionalGeneration.from_pretrained('{model_id}', local_files_only=False)"
    )
    result = subprocess.run([python, "-c", code_model], capture_output=True, text=True)
    if result.returncode != 0:
        warn(f"Model weight download failed: {result.stderr.strip()[:200]}")
        return

    # 프로세서 / 토크나이저 다운로드
    info(f"Downloading tokenizer and processor: {model_id}")
    code_proc = (
        f"import os; os.environ['HF_HOME'] = r'{HF_HOME_PATH}'; "
        f"from transformers import WhisperProcessor; "
        f"WhisperProcessor.from_pretrained('{model_id}', local_files_only=False)"
    )
    result = subprocess.run([python, "-c", code_proc], capture_output=True, text=True)
    if result.returncode != 0:
        warn(f"Processor download failed: {result.stderr.strip()[:200]}")
        return

    ok(f"{model_id} - Download complete.")


def download_models():
    """
    사용자에게 Whisper Tiny / Small 모델 다운로드 여부를 대화형으로 묻고
    선택에 따라 다운로드를 수행한다.

    모델 저장 위치는 HF_HOME_PATH 로 지정된 공통 캐시 폴더다.
    인터넷 연결 없이 실행하려면 이 단계에서 미리 다운로드해 두어야 한다.
    """
    step(6, 7, "Downloading Whisper model files (interactive)...")
    print()
    print("  These model files are needed for training.")
    print(f"  Storage location: {HF_HOME_PATH}")
    print("  If already downloaded, this step will be instant (uses cache).")
    print()

    # Tiny 모델 (~150 MB): 빠른 테스트 및 저사양 환경용
    if ask_yes_no("Download Whisper Tiny model? (openai/whisper-tiny, ~150 MB)", default="y"):
        download_whisper_model("openai/whisper-tiny")
    else:
        info("Whisper Tiny model download skipped.")

    # Small 모델 (~967 MB): 품질과 속도의 균형이 좋은 기본 모델
    if ask_yes_no("Download Whisper Small model? (openai/whisper-small, ~967 MB)", default="y"):
        download_whisper_model("openai/whisper-small")
    else:
        info("Whisper Small model download skipped.")


# ============================================================
# Step 7: whisper.cpp 리포지토리 복제 (GGUF 양자화 툴)
# ============================================================

def clone_whisper_cpp():
    """
    GGUF 양자화 변환에 사용되는 whisper.cpp 소스코드를 third_party/ 에 복제한다.
    이미 존재하는 경우 건너뛴다.

    whisper.cpp 는 학습된 LoRA 어댑터를 병합하고 경량 GGUF 형식으로 변환할 때 필요하다.
    Windows 에서는 quantize.exe 를 별도로 빌드하거나 사전 컴파일 바이너리를 배치해야 한다.
    """
    step(7, 7, "Cloning whisper.cpp repository for GGUF quantization...")

    third_party = os.path.dirname(WHISPER_CPP_DIR)
    os.makedirs(third_party, exist_ok=True)

    if os.path.isdir(WHISPER_CPP_DIR):
        ok(f"whisper.cpp already exists at: {WHISPER_CPP_DIR}")
    else:
        info("Cloning whisper.cpp from GitHub (shallow clone)...")
        result = subprocess.run(
            ["git", "clone", "--depth", "1",
             "https://github.com/ggerganov/whisper.cpp.git",
             WHISPER_CPP_DIR],
            capture_output=False
        )
        if result.returncode == 0:
            ok("whisper.cpp cloned successfully.")
        else:
            warn("whisper.cpp clone failed. GGUF export will not be available.")
            warn("Make sure 'git' is installed and you have internet access.")
            return

    # quantize.exe 존재 여부 확인 (Windows 사전 빌드 바이너리 체크)
    quantize_exe = os.path.join(WHISPER_CPP_DIR, "quantize.exe")
    if os.path.exists(quantize_exe):
        ok("quantize.exe found. GGUF quantization is ready.")
    else:
        warn("quantize.exe not found in whisper.cpp folder.")
        warn("To use GGUF export, you need to compile whisper.cpp or place a pre-built binary there.")
        warn("See: https://github.com/ggerganov/whisper.cpp")


# ============================================================
# 완료 메시지
# ============================================================

def print_done():
    """
    설치 완료 후 다음 단계 안내 메시지를 출력한다.
    """
    print()
    print("=" * 60)
    print("  Setup Complete!")
    print("=" * 60)
    print()
    print("  Next steps:")
    print()
    print("  1. Collect audio data and build dataset:")
    print("       python scripts/01_build_dataset.py")
    print()
    print("  2. Start training:")
    print("       python scripts/02_start_training.py")
    print()
    print("  3. Launch the full CLI interface:")
    print("       run_cli.bat")
    print()
    print("  4. View training from another device (browser):")
    print("       run_web_cli.bat")
    print()
    print("=" * 60)
    print()


# ============================================================
# 메인 진입점
# ============================================================

def main():
    """
    설치 스크립트의 메인 진입점.
    Windows 외 운영체제는 지원하지 않는다.
    (리눅스/macOS 는 setup/setup_env.sh 를 직접 실행할 것)
    """
    banner("AMEVA-STT-Trainer Unified Setup")

    # Windows 외 환경 경고
    if platform.system() != "Windows":
        warn("This setup.py is optimized for Windows.")
        warn("For Linux/macOS, run: bash setup/setup_env.sh")
        # 경고만 하고 계속 진행 (venv/pip 는 크로스플랫폼 동작)

    print()
    print("  This installer will:")
    print("  - Create a Python virtual environment (venv/)")
    print("  - Install the correct version of PyTorch for your GPU")
    print("  - Install all required Python packages")
    print("  - Download Whisper AI model files (optional)")
    print("  - Clone whisper.cpp for GGUF export (optional)")
    print()
    print("  Requirements: Python 3.10+, pip, git, internet connection")
    print()

    try:
        create_venv()           # Step 1
        upgrade_pip()           # Step 2
        install_pytorch()       # Step 3: GPU/CUDA 자동 감지 후 적합한 wheel 설치
        install_requirements()  # Step 4: 나머지 패키지
        verify_installations()  # Step 5: 설치 검증
        download_models()       # Step 6: Whisper 모델 다운로드
        clone_whisper_cpp()     # Step 7: GGUF 변환 도구
    except subprocess.CalledProcessError as e:
        error_exit(f"A command failed during setup: {e}")
    except KeyboardInterrupt:
        print("\n\n  [INFO] Setup cancelled by user.")
        sys.exit(0)

    print_done()


if __name__ == "__main__":
    main()
