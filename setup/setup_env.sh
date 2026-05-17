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
echo -e "${CYAN}[1/5] Verified Python Version: ${PYTHON_VERSION}${NC}"

# 2. Create Virtual Environment
if [ ! -d "venv" ]; then
    echo -e "${CYAN}[2/5] Creating Virtual Environment (venv)...${NC}"
    python3 -m venv venv
else
    echo -e "${CYAN}[2/5] Virtual Environment already exists.${NC}"
fi

# 3. Activate Virtual Environment
echo -e "${CYAN}[3/5] Activating Virtual Environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${CYAN}Upgrading pip...${NC}"
python3 -m pip install --upgrade pip

# Install dependencies
echo -e "${CYAN}Installing dependencies from requirements.txt...${NC}"
pip install -r requirements.txt

# Verify Installations
echo -e "${CYAN}Verifying installations...${NC}"
python3 -c "import wandb; print(f'  WandB Version: {wandb.__version__}')"
python3 -c "import gguf; print('  GGUF-Py: Fully Verified')"

# 4. Setup whisper.cpp & Quantization Utilities
THIRD_PARTY_DIR="third_party"
WHISPER_CPP_DIR="${THIRD_PARTY_DIR}/whisper.cpp"

if [ ! -d "${THIRD_PARTY_DIR}" ]; then
    mkdir -p "${THIRD_PARTY_DIR}"
fi

if [ ! -d "${WHISPER_CPP_DIR}" ]; then
    echo -e "${CYAN}[4/5] Cloning whisper.cpp for conversion and quantization tools...${NC}"
    git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git "${WHISPER_CPP_DIR}"
else
    echo -e "${CYAN}[4/5] whisper.cpp directory already exists at ${WHISPER_CPP_DIR}${NC}"
fi

# 5. Compile whisper.cpp & Quantize Tool
echo -e "${CYAN}[5/5] Compiling whisper.cpp and quantization utility...${NC}"
if command -v make &> /dev/null; then
    cd "${WHISPER_CPP_DIR}"
    
    # Check OS type for GPU build hints
    OS_TYPE=$(uname -s)
    echo -e "${CYAN}Detected Operating System: ${OS_TYPE}${NC}"
    
    if [ "${OS_TYPE}" == "Darwin" ]; then
        echo -e "${YELLOW}[macOS Hint] Building whisper.cpp with Metal acceleration...${NC}"
        make -j
        make quantize -j
    else
        echo -e "${YELLOW}[Linux Hint] Building whisper.cpp with standard CPU/OpenMP...${NC}"
        echo -e "${YELLOW}To compile with CUDA, run: WHISPER_CUDA=1 make -j${NC}"
        make -j
        make quantize -j
    fi
    
    if [ -f "./quantize" ]; then
        echo -e "${GREEN}[SUCCESS] whisper.cpp and 'quantize' tool built successfully!${NC}"
    else
        echo -e "${RED}[WARNING] whisper.cpp built, but 'quantize' binary was not found.${NC}"
    fi
    cd - > /dev/null
else
    echo -e "${YELLOW}[WARNING] 'make' command not found. Skipping automatic compilation.${NC}"
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
