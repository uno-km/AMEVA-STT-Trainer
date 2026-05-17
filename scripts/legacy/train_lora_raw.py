"""
scripts/legacy/train_lora_raw.py
[백업] 단일 파일 형태의 LoRA 학습 레거시 스크립트.
주로 빠른 실험이나 환경 테스트용으로 사용된다.
"""
import os
import torch
import pandas as pd
from datasets import Dataset, Audio
from transformers import (
    WhisperProcessor,
    WhisperForConditionalGeneration,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
    WhisperTokenizer,
    WhisperFeatureExtractor
)
from peft import LoraConfig, get_peft_model
from dataclasses import dataclass
from typing import Any, Dict, List, Union

MODEL_ID = "openai/whisper-tiny"
LANGUAGE = "Korean"
TASK = "transcribe"
DATASET_CSV = "dataset/metadata.csv"
AUDIO_DIR = "dataset/wav"
OUTPUT_DIR = "outputs/lora_adapter"

BATCH_SIZE = 2
GRADIENT_ACCUMULATION_STEPS = 8
LEARNING_RATE = 1e-3
MAX_STEPS = 500  
SAVE_STEPS = 100
LOGGING_STEPS = 10

processor = WhisperProcessor.from_pretrained(MODEL_ID, language=LANGUAGE, task=TASK)
tokenizer = WhisperTokenizer.from_pretrained(MODEL_ID, language=LANGUAGE, task=TASK)
feature_extractor = WhisperFeatureExtractor.from_pretrained(MODEL_ID)

def prepare_dataset(batch):
    audio = batch["audio"]
    batch["input_features"] = feature_extractor(audio["array"], sampling_rate=audio["sampling_rate"]).input_features[0]
    batch["labels"] = tokenizer(batch["transcription"]).input_ids
    return batch

@dataclass
class DataCollatorSpeechSeq2SeqWithPadding:
    processor: Any

    def __call__(self, features: List[Dict[str, Union[List[int], torch.Tensor]]]) -> Dict[str, torch.Tensor]:
        input_features = [{"input_features": feature["input_features"]} for feature in features]
        batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")

        label_features = [{"input_ids": feature["labels"]} for feature in features]
        labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")

        labels = labels_batch["input_ids"].masked_fill(labels_batch.attention_mask.ne(1), -100)
        if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all().cpu().item():
            labels = labels[:, 1:]

        batch["labels"] = labels
        return batch

def main():
    if not os.path.exists(DATASET_CSV):
        print(f"[ERROR] Metadata file not found at {DATASET_CSV}. Run make_dataset.py first.")
        return

    df = pd.read_csv(DATASET_CSV)
    df["audio"] = df["file_name"].apply(lambda x: os.path.join(AUDIO_DIR, x))
    
    dataset = Dataset.from_pandas(df)
    dataset = dataset.cast_column("audio", Audio(sampling_rate=16000))
    
    print(f"[*] Total samples: {len(dataset)}")
    dataset = dataset.map(prepare_dataset, remove_columns=dataset.column_names, num_proc=1)

    model = WhisperForConditionalGeneration.from_pretrained(MODEL_ID)
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []

    config = LoraConfig(
        r=32,
        lora_alpha=64,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none"
    )
    model = get_peft_model(model, config)
    model.print_trainable_parameters()

    training_args = Seq2SeqTrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        learning_rate=LEARNING_RATE,
        warmup_steps=50,
        max_steps=MAX_STEPS,
        gradient_checkpointing=True,
        fp16=False,
        evaluation_strategy="no",
        save_steps=SAVE_STEPS,
        logging_steps=LOGGING_STEPS,
        report_to=["tensorboard"],
        load_best_model_at_end=False,
        label_names=["labels"],
        push_to_hub=False,
        remove_unused_columns=False,
    )

    data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=processor)
    trainer = Seq2SeqTrainer(
        args=training_args,
        model=model,
        train_dataset=dataset,
        data_collator=data_collator,
        tokenizer=processor.feature_extractor,
    )

    print("[*] Starting Training...")
    trainer.train()

    trainer.save_model(OUTPUT_DIR)
    processor.save_pretrained(OUTPUT_DIR)
    print(f"[*] Training finished. Model saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
