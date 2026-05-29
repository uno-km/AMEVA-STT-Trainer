#!/usr/bin/env bash
# ======================================================================
# AMEVA-STT-Trainer Cross-Platform Environment Setup Script
# Supports: Linux, macOS (Unix Environments)
# ======================================================================

set -e

# ANSI Color Codes for Premium Aesthetics
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}======================================================${NC}"
echo -e "${CYAN}   AMEVA-STT-Trainer Unix Environment Setup (setup_env)${NC}"
echo -e "${CYAN}======================================================${NC}"

# 1. Verify Python Installation
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python3 is not installed or not found in PATH.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo -e "${GREEN}[✓] 파이썬 버전 확인 완료: ${PYTHON_VERSION}${NC}"

# 2. Create Virtual Environment
if [ ! -d "venv" ]; then
    echo -e "${CYAN}[2/5] 가상 환경(venv) 생성 중...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}[✓] 가상 환경 생성 완료!${NC}"
else
    echo -e "${GREEN}[✓] 가상 환경이 이미 존재합니다.${NC}"
fi

# 3. Activate Virtual Environment
echo -e "${CYAN}[3/5] 가상 환경 활성화 중...${NC}"
source venv/bin/activate
echo -e "${GREEN}[✓] 가상 환경 활성화 완료!${NC}"

# Upgrade pip
echo -e "${CYAN}pip 업그레이드 중...${NC}"
python3 -m pip install --upgrade pip
echo -e "${GREEN}[✓] pip 업그레이드 완료!${NC}"

# Install dependencies
echo -e "${CYAN}requirements.txt 패키지 의존성 설치 중...${NC}"
pip install -r requirements.txt
echo -e "${GREEN}[✓] 패키지 설치 완료!${NC}"

# Verify Installations
echo -e "${CYAN}설치 라이브러리 검증 및 확인 중...${NC}"
python3 -c "import wandb; print(f'  [✓] WandB 확인 완료 (버전: {wandb.__version__})')"
python3 -c "import gguf; print('  [✓] GGUF-Py 확인 완료')"

# Interactive Model Download
python3 setup/download_models_interactive.py

# 4. Setup whisper.cpp & Quantization Utilities
THIRD_PARTY_DIR="third_party"
WHISPER_CPP_DIR="${THIRD_PARTY_DIR}/whisper.cpp"

if [ ! -d "${THIRD_PARTY_DIR}" ]; then
    mkdir -p "${THIRD_PARTY_DIR}"
fi

if [ ! -d "${WHISPER_CPP_DIR}" ]; then
    echo -e "${CYAN}[4/5] whisper.cpp 리포지토리 클론 중...${NC}"
    git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git "${WHISPER_CPP_DIR}"
    echo -e "${GREEN}[✓] whisper.cpp 클론 완료!${NC}"
else
    echo -e "${GREEN}[✓] whisper.cpp가 이미 존재합니다: ${WHISPER_CPP_DIR}${NC}"
fi

# 5. Compile whisper.cpp & Quantize Tool
echo -e "${CYAN}[5/5] whisper.cpp 및 양자화 유틸리티 컴파일 중...${NC}"
if command -v make &> /dev/null; then
    cd "${WHISPER_CPP_DIR}"
    
    # Check OS type for GPU build hints
    OS_TYPE=$(uname -s)
    echo -e "${CYAN}감지된 운영체제: ${OS_TYPE}${NC}"
    
    if [ "${OS_TYPE}" == "Darwin" ]; then
        echo -e "${YELLOW}[macOS Metal 가속 설정] whisper.cpp 빌드 중...${NC}"
        make -j
        make quantize -j
    else
        echo -e "${YELLOW}[Linux CPU OpenMP 설정] whisper.cpp 빌드 중...${NC}"
        echo -e "${YELLOW}To compile with CUDA, run: WHISPER_CUDA=1 make -j${NC}"
        make -j
        make quantize -j
    fi
    
    if [ -f "./quantize" ]; then
        echo -e "${GREEN}[✓] whisper.cpp 및 'quantize' 빌드 완료!${NC}"
    else
        echo -e "${RED}[!] 빌드는 완료되었으나 'quantize' 바이너리를 찾을 수 없습니다.${NC}"
    fi
    cd - > /dev/null
else
    echo -e "${YELLOW}[!] 'make' 명령어를 찾을 수 없어 컴파일을 생략합니다.${NC}"
    echo -e "${YELLOW}수동 빌드가 필요하다면 third_party/whisper.cpp 경로에서 make를 실행하십시오.${NC}"
    echo -e "${YELLOW}Please install build essentials (gcc, make) and run 'make' inside third_party/whisper.cpp manually.${NC}"
fi

echo -e "${CYAN}======================================================${NC}"
echo -e "${GREEN}   AMEVA-STT-Trainer Environment Setup Complete!${NC}"
echo -e "${CYAN}======================================================${NC}"
echo -e "${YELLOW}To activate this environment in the future, run:${NC}"
echo -e "   source venv/bin/activate"
echo -e "${YELLOW}To run Whisper quantization guide:${NC}"
echo -e "   python scripts/export_gguf.py"
echo -e "${CYAN}======================================================${NC}"
