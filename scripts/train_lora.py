"""
scripts/train_lora.py
단일 파일 형태의 LoRA 학습 스크립트.
주로 빠른 실험이나 환경 테스트용으로 사용된다.
"""
import os
import torch
import pandas as pd
from datasets import Dataset, Audio, load_dataset
from transformers import (
    WhisperProcessor,
    WhisperForConditionalGeneration,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
    WhisperTokenizer,
    WhisperFeatureExtractor
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from dataclasses import dataclass
from typing import Any, Dict, List, Union

# --- 기본 설정 (수동 지정) ---
MODEL_ID = "openai/whisper-tiny"  # 베이스 모델 식별자
LANGUAGE = "Korean"               # 대상 언어
TASK = "transcribe"               # 수행 작업 (음성 전사)
DATASET_CSV = "dataset/metadata.csv" # 학습 데이터 목록 파일
AUDIO_DIR = "dataset/wav"         # 오디오 데이터 기본 폴더
OUTPUT_DIR = "outputs/lora_adapter" # 학습 결과 저장 폴더

# 학습 하이퍼파라미터 (CPU 환경 최적화 설정)
BATCH_SIZE = 2
GRADIENT_ACCUMULATION_STEPS = 8
LEARNING_RATE = 1e-3
MAX_STEPS = 500  
SAVE_STEPS = 100
LOGGING_STEPS = 10

# 전용 프로세서, 토크나이저, 특징 추출기 초기화
processor = WhisperProcessor.from_pretrained(MODEL_ID, language=LANGUAGE, task=TASK)
tokenizer = WhisperTokenizer.from_pretrained(MODEL_ID, language=LANGUAGE, task=TASK)
feature_extractor = WhisperFeatureExtractor.from_pretrained(MODEL_ID)

def prepare_dataset(batch):
    """데이터셋 행 단위 전처리 함수."""
    # 오디오 데이터 로드
    audio = batch["audio"]
    # 오디오 신호로부터 입력 특징 추출 (Mel-Spectrogram)
    batch["input_features"] = feature_extractor(audio["array"], sampling_rate=audio["sampling_rate"]).input_features[0]
    # 전사 텍스트를 토큰 ID 리스트로 변환하여 레이블 생성
    batch["labels"] = tokenizer(batch["transcription"]).input_ids
    return batch

@dataclass
class DataCollatorSpeechSeq2SeqWithPadding:
    """배치 내 샘플들의 길이를 패딩으로 맞추는 클래스."""
    processor: Any

    def __call__(self, features: List[Dict[str, Union[List[int], torch.Tensor]]]) -> Dict[str, torch.Tensor]:
        # 입력 오디오 특징 패딩
        input_features = [{"input_features": feature["input_features"]} for feature in features]
        batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")

        # 텍스트 레이블 패딩 및 마스킹 (-100 설정)
        label_features = [{"input_ids": feature["labels"]} for feature in features]
        labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")

        # 패딩된 영역을 손실 계산에서 제외하도록 -100으로 치환
        labels = labels_batch["input_ids"].masked_fill(labels_batch.attention_mask.ne(1), -100)
        # BOS 토큰 중복 방지 처리
        if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all().cpu().item():
            labels = labels[:, 1:]

        batch["labels"] = labels
        return batch

def main():
    # 메타데이터 파일 존재 확인
    if not os.path.exists(DATASET_CSV):
        print(f"[ERROR] Metadata file not found at {DATASET_CSV}. Run make_dataset.py first.")
        return

    # 1. 데이터셋 준비
    # CSV 파일을 읽어 데이터프레임 생성
    df = pd.read_csv(DATASET_CSV)
    # 개별 오디오 파일의 절대 경로 생성
    df["audio"] = df["file_name"].apply(lambda x: os.path.join(AUDIO_DIR, x))
    
    # HuggingFace Dataset 객체로 변환
    dataset = Dataset.from_pandas(df)
    # 오디오 컬럼 타입 지정 및 샘플링 레이트 고정
    dataset = dataset.cast_column("audio", Audio(sampling_rate=16000))
    
    print(f"[*] Total samples: {len(dataset)}")
    
    # 전처리 함수 적용 (map)
    dataset = dataset.map(prepare_dataset, remove_columns=dataset.column_names, num_proc=1)

    # 2. 베이스 모델 로드
    model = WhisperForConditionalGeneration.from_pretrained(MODEL_ID)
    # 학습을 위해 고정된 디코더 ID 비활성화
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []

    # 3. LoRA 어댑터 설정 및 적용
    config = LoraConfig(
        r=32,                         # 어댑터 랭크
        lora_alpha=64,                # 스케일링
        target_modules=["q_proj", "v_proj"], # 학습 대상 Attention 레이어
        lora_dropout=0.05,            # 드롭아웃
        bias="none"                   # 바이어스 학습 안 함
    )
    # 베이스 모델에 LoRA 레이어 주입
    model = get_peft_model(model, config)
    # 학습 파라미터 정보 출력
    model.print_trainable_parameters()

    # 4. 학습 인수 설정
    training_args = Seq2SeqTrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        learning_rate=LEARNING_RATE,
        warmup_steps=50,
        max_steps=MAX_STEPS,
        gradient_checkpointing=True,
        fp16=False,                   # CPU 환경이므로 False 고정
        evaluation_strategy="no",
        save_steps=SAVE_STEPS,
        logging_steps=LOGGING_STEPS,
        report_to=["tensorboard"],
        load_best_model_at_end=False,
        label_names=["labels"],
        push_to_hub=False,
        remove_unused_columns=False,
    )

    # 데이터 콜레이터 인스턴스화
    data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=processor)

    # 5. Trainer 객체 생성 및 학습 실행
    trainer = Seq2SeqTrainer(
        args=training_args,
        model=model,
        train_dataset=dataset,
        data_collator=data_collator,
        tokenizer=processor.feature_extractor,
    )

    print("[*] Starting Training...")
    # 학습 루프 시작
    trainer.train()

    # 최종 결과물 저장
    trainer.save_model(OUTPUT_DIR)
    processor.save_pretrained(OUTPUT_DIR)
    print(f"[*] Training finished. Model saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    # 스크립트 진입점 실행
    main()
