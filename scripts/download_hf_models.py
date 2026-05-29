"""
scripts/download_hf_models.py
HuggingFace Hub에서 openai/whisper-tiny 및 openai/whisper-small 모델과 토크나이저/프로세서를 다운로드합니다.
local_files_only=False로 다운로드하여 로컬 캐시에 저장되게 함으로써 오프라인 모드(local_files_only=True)에서 바로 로드할 수 있도록 합니다.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from transformers import WhisperForConditionalGeneration, WhisperProcessor, WhisperTokenizer, WhisperFeatureExtractor
from src.utils import logger

def download_model(model_id: str):
    logger.info(f"HuggingFace에서 모델 다운로드 시작: {model_id}")
    try:
        # 모델 다운로드
        logger.info(f"[{model_id}] 가중치 다운로드 중...")
        model = WhisperForConditionalGeneration.from_pretrained(
            model_id, 
            local_files_only=False
        )
        
        # 프로세서/토크나이저/특징 추출기 다운로드
        logger.info(f"[{model_id}] 프로세서 및 토크나이저 다운로드 중...")
        processor = WhisperProcessor.from_pretrained(model_id, local_files_only=False)
        tokenizer = WhisperTokenizer.from_pretrained(model_id, local_files_only=False)
        feature_extractor = WhisperFeatureExtractor.from_pretrained(model_id, local_files_only=False)
        
        logger.success(f"[{model_id}] 다운로드 및 로컬 캐싱 완료!")
    except Exception as e:
        logger.error(f"[{model_id}] 다운로드 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())

def main():
    models = ["openai/whisper-tiny", "openai/whisper-small"]
    for m in models:
        download_model(m)

if __name__ == "__main__":
    main()
