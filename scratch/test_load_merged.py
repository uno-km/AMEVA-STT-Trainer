import torch
from transformers import WhisperForConditionalGeneration
try:
    model = WhisperForConditionalGeneration.from_pretrained("c:/ameva/AMEVA-STT-Trainer/outputs/merged_model")
    print("Success: Model loaded")
except Exception as e:
    print(f"Error: {e}")
