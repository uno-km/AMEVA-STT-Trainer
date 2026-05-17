"""
scripts/legacy/merge_lora_raw.py
[백업] LoRA 어댑터 가중치를 베이스 모델에 병합하는 레거시 독립 스크립트.
"""
import os
from transformers import WhisperForConditionalGeneration, WhisperProcessor
from peft import PeftModel

BASE_MODEL_ID = "openai/whisper-tiny"
LORA_ADAPTER_DIR = "outputs/lora_adapter"
MERGED_MODEL_DIR = "outputs/merged_model"

def main():
    if not os.path.exists(LORA_ADAPTER_DIR):
        print(f"[ERROR] LoRA adapter not found at {LORA_ADAPTER_DIR}.")
        return

    print("[*] Loading Base Model...")
    base_model = WhisperForConditionalGeneration.from_pretrained(BASE_MODEL_ID)
    
    print("[*] Loading LoRA Adapter & Merging...")
    model = PeftModel.from_pretrained(base_model, LORA_ADAPTER_DIR)
    
    merged_model = model.merge_and_unload()
    
    print(f"[*] Saving Merged Model to {MERGED_MODEL_DIR}...")
    merged_model.save_pretrained(MERGED_MODEL_DIR)
    
    processor = WhisperProcessor.from_pretrained(BASE_MODEL_ID)
    processor.save_pretrained(MERGED_MODEL_DIR)
    
    print("[*] Done! You can now use this model as a standard Whisper model.")

if __name__ == "__main__":
    main()
