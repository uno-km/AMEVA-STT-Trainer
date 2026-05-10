"""
scripts/quick_test.py
병합된 모델의 성능을 실전 테스트하는 스크립트.
"""
import torch
from transformers import WhisperProcessor, WhisperForConditionalGeneration
import librosa
import os
import sys

# 출력 인코딩을 UTF-8로 설정 (한글 깨짐 방지)
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python 3.7 미만 대응
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.core.config import MERGED_DIR, DATASET_DIR

def run_test(audio_rel_path):
    # 1. 경로 설정
    model_path = MERGED_DIR
    audio_path = os.path.join(DATASET_DIR, audio_rel_path)
    
    if not os.path.exists(audio_path):
        print(f"[!] Audio file not found: {audio_path}")
        return

    print(f"[*] Loading model from: {model_path}...")
    # 2. 모델 및 프로세서 로드
    processor = WhisperProcessor.from_pretrained(model_path)
    model = WhisperForConditionalGeneration.from_pretrained(model_path)
    
    # 디바이스 설정 (GPU 있으면 사용)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    print(f"[*] Processing audio: {audio_rel_path}...")
    # 3. 오디오 로드 (Whisper는 16kHz 요구)
    audio, sr = librosa.load(audio_path, sr=16000)
    input_features = processor(audio, sampling_rate=sr, return_tensors="pt").input_features.to(device)

    print("[*] Shuka AI is thinking...")
    # 4. 전사(Transcribe) 실행
    with torch.no_grad():
        predicted_ids = model.generate(input_features)
    
    transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]

    print("\n" + "="*50)
    print(f"[TEST RESULT]")
    print("="*50)
    print(f"입력 파일: {audio_rel_path}")
    print(f"Result: {transcription}")
    print("="*50 + "\n")

if __name__ == "__main__":
    # 테스트할 샘플 경로 (metadata.csv에서 확인한 경로)
    target_sample = r"2026\05\09\NuPa3gcdn1c\chunks\chunk_0000.wav"
    run_test(target_sample)
