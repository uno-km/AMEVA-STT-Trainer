"""
src/models/quantizer.py
학습 및 병합이 완료된 Whisper 모델을 GGUF 포맷으로 변환하고 4비트 양자화를 수행하는 모듈.
"""
import os
import sys
import subprocess
import shutil
from src.utils import logger
from src.core.config import DATASET_DIR, GGUF_DIR

class WhisperQuantizer:
    def __init__(self, whisper_cpp_dir: str):
        self.whisper_cpp_dir = os.path.abspath(whisper_cpp_dir)
        self.third_party_dir = os.path.dirname(self.whisper_cpp_dir)
        self.converter_script = os.path.join(self.whisper_cpp_dir, "models", "convert-h5-to-ggml.py")
        self.quantize_bin = os.path.join(self.whisper_cpp_dir, "quantize")
        if os.name == 'nt':
            self.quantize_bin += ".exe"

    def ensure_tool(self):
        """whisper.cpp 도구가 없으면 클론하고 빌드 준비를 한다."""
        if not os.path.exists(self.whisper_cpp_dir):
            logger.info("whisper.cpp 도구가 없습니다. 자동으로 클론을 시작합니다...")
            os.makedirs(self.third_party_dir, exist_ok=True)
            subprocess.run([
                "git", "clone", "--depth", "1", 
                "https://github.com/ggerganov/whisper.cpp.git", 
                self.whisper_cpp_dir
            ], check=True)
            logger.info("✅ whisper.cpp 클론 완료")

        # 필수 에셋(mel_filters.npz) 다운로드 로직
        assets_dir = os.path.join(self.third_party_dir, "whisper_assets", "whisper", "assets")
        asset_file = os.path.join(assets_dir, "mel_filters.npz")
        if not os.path.exists(asset_file):
            logger.info("필수 오디오 에셋(mel_filters.npz)이 없습니다. 다운로드를 시도합니다...")
            os.makedirs(assets_dir, exist_ok=True)
            asset_url = "https://raw.githubusercontent.com/openai/whisper/main/whisper/assets/mel_filters.npz"
            if os.name == 'nt':
                subprocess.run(["powershell", "-Command", f"Invoke-WebRequest -Uri {asset_url} -OutFile {asset_file}"], check=True)
            else:
                subprocess.run(["wget", "-O", asset_file, asset_url], check=True)
            logger.info("✅ 에셋 다운로드 완료")
        
        return assets_dir

    def build_quantizer(self):
        """quantize 도구가 없으면 컴파일(make)을 시도한다."""
        if not os.path.exists(self.quantize_bin):
            logger.info("양자화 도구(quantize)가 없습니다. 컴파일을 시도합니다...")
            try:
                # Windows의 경우 make가 설치되어 있어야 함 (w64devkit 등)
                subprocess.run(["make", "-C", self.whisper_cpp_dir, "quantize"], check=True)
                logger.info("✅ quantize 도구 빌드 성공")
            except Exception as e:
                logger.warning(f"⚠️ 빌드 실패: {e}. 컴파일러(make/gcc) 환경이 필요합니다.")
        return os.path.exists(self.quantize_bin)

    def quantize_existing_bin(self, source_bin: str, final_name: str, method: str = "q4_0"):
        """이미 존재하는 GGML 바이너리를 지정된 방식으로 양자화한다."""
        self.ensure_tool()
        self.build_quantizer()

        if not os.path.exists(source_bin):
            logger.error(f"원본 파일을 찾을 수 없습니다: {source_bin}")
            return None

        if os.path.exists(self.quantize_bin):
            logger.info(f"단독 양자화 실행 중 ({method}) -> {final_name}")
            subprocess.run([self.quantize_bin, source_bin, final_name, method], check=True)
            return final_name
        else:
            logger.warning("양자화 도구가 준비되지 않았습니다.")
            return None

    def run_post_process(self, merged_model_path: str, final_name: str = "ggml-model-q4_0.bin", skip_quantize: bool = False):
        """
        병합된 모델 -> GGUF 변환 -> (선택적) 4비트 양자화 과정을 수행한다.
        """
        assets_dir = self.ensure_tool()
        
        # 1. GGML 포맷으로 변환 (FP16/32)
        logger.info("1단계: GGUF(GGML) 포맷 변환 중...")
        subprocess.run([
            sys.executable, self.converter_script, 
            merged_model_path, 
            os.path.dirname(os.path.dirname(assets_dir)),
            "." 
        ], check=True)

        source_bin = "ggml-model.bin"

        # 양자화 스킵 옵션 처리
        if skip_quantize:
            logger.info("양자화 단계를 건너뛰고 원본 FP 모델을 배포합니다.")
            if os.path.exists(source_bin):
                shutil.move(source_bin, final_name)
                return final_name
            return None

        # 2. 4비트 양자화 실행
        return self.quantize_existing_bin(source_bin, final_name)
