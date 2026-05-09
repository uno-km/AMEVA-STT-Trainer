"""
scripts/merge_lora.py
LoRA 어댑터 가중치를 베이스 모델에 병합하는 독립 스크립트.
"""
import os
from transformers import WhisperForConditionalGeneration, WhisperProcessor
from peft import PeftModel

# --- 기본 설정 ---
BASE_MODEL_ID = "openai/whisper-tiny"  # 원본 베이스 모델 이름
LORA_ADAPTER_DIR = "outputs/lora_adapter" # 학습된 LoRA 가중치 위치
MERGED_MODEL_DIR = "outputs/merged_model" # 최종 병합 결과 저장 위치

def main():
    # 병합할 LoRA 어댑터 폴더가 존재하는지 사전 확인
    if not os.path.exists(LORA_ADAPTER_DIR):
        print(f"[ERROR] LoRA adapter not found at {LORA_ADAPTER_DIR}.")
        return

    # 1. 원본 베이스 모델 로드
    print("[*] Loading Base Model...")
    base_model = WhisperForConditionalGeneration.from_pretrained(BASE_MODEL_ID)
    
    # 2. LoRA 어댑터 로드 및 모델 결합
    print("[*] Loading LoRA Adapter & Merging...")
    # 베이스 모델 위에 LoRA 레이어를 덧씌움
    model = PeftModel.from_pretrained(base_model, LORA_ADAPTER_DIR)
    
    # 3. 가중치 병합 실행
    # merge_and_unload: LoRA 가중치를 베이스 가중치 행렬에 직접 합산하고 어댑터 레이어를 제거함
    # 이 과정을 거쳐야 표준 Whisper 모델 포맷으로 사용 가능
    merged_model = model.merge_and_unload()
    
    # 4. 최종 결과물 저장
    print(f"[*] Saving Merged Model to {MERGED_MODEL_DIR}...")
    # 병합된 가중치 및 설정 파일 저장
    merged_model.save_pretrained(MERGED_MODEL_DIR)
    
    # 5. 프로세서 정보 저장
    # 추론 시 텍스트 복원을 위해 필요한 프로세서(토크나이저 등)를 함께 저장
    processor = WhisperProcessor.from_pretrained(BASE_MODEL_ID)
    processor.save_pretrained(MERGED_MODEL_DIR)
    
    print("[*] Done! You can now use this model as a standard Whisper model.")

if __name__ == "__main__":
    # 스크립트 실행
    main()
