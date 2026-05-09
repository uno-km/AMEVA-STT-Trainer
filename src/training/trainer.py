"""
src/training/trainer.py
Whisper + LoRA 학습 파이프라인.

핵심 설계:
  - metadata.csv의 file_name(상대경로)으로 오디오를 로드한다.
  - resume_from_checkpoint=True: 재실행 시 마지막 체크포인트부터 이어서 학습한다.
  - save_steps 주기로 가중치를 저장하여 크래시 손실을 최소화한다.
  - 모든 예외는 @exception_guard를 통해 syuka_error_log.md에 기록된다.
"""
import os
import torch
import pandas as pd
from dataclasses import dataclass
from typing import Any, Dict, List, Union

from datasets import Dataset, Audio
from transformers import (
    WhisperFeatureExtractor,
    WhisperTokenizer,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
)

from src.core.config import CFG, DATASET_DIR, METADATA_PATH, LORA_DIR
from src.core.exceptions import TrainingError, exception_guard
from src.models.whisper_lora import load_base_model, apply_lora
from src.training.callbacks import DashboardCallback
from src.utils import logger


# ---------------------------------------------------------------------------- #
#  데이터 콜레이터 (패딩 및 레이블 마스킹)                                        #
# ---------------------------------------------------------------------------- #

@dataclass
class DataCollatorSpeechSeq2SeqWithPadding:
    """
    배치 내 샘플들의 길이를 맞추고,
    레이블에서 패딩 토큰을 -100으로 마스킹한다.
    (-100은 CrossEntropyLoss에서 자동으로 무시됨)
    """
    # Whisper 모델용 프로세서 (특징 추출기 및 토크나이저 포함)
    processor: Any

    def __call__(self, features: List[Dict[str, Union[List[int], torch.Tensor]]]) -> Dict[str, torch.Tensor]:
        # 배치 내 각 샘플로부터 입력 오디오 특징 추출
        input_features = [{"input_features": f["input_features"]} for f in features]
        # 입력 특징들을 패딩하여 동일한 길이의 텐서로 변환
        batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")

        # 배치 내 각 샘플로부터 텍스트 레이블 추출
        label_features = [{"input_ids": f["labels"]} for f in features]
        # 레이블들을 패딩하여 동일한 길이의 텐서로 변환
        labels_batch   = self.processor.tokenizer.pad(label_features, return_tensors="pt")
        
        # 패딩된 영역(-1)을 -100으로 치환하여 손실 계산 시 제외되도록 설정
        labels         = labels_batch["input_ids"].masked_fill(
            labels_batch.attention_mask.ne(1), -100
        )

        # 문장 시작(BOS) 토큰이 모든 레이블의 처음에 있으면 중복 방지를 위해 제거
        if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all().cpu().item():
            labels = labels[:, 1:]

        # 최종 가공된 레이블을 배치 딕셔너리에 저장
        batch["labels"] = labels
        return batch


# ---------------------------------------------------------------------------- #
#  전처리 함수 (map 적용용)                                                       #
# ---------------------------------------------------------------------------- #

def _make_prepare_fn(feature_extractor, tokenizer):
    """
    feature_extractor와 tokenizer를 클로저로 캡처한
    dataset.map() 적용 함수를 반환한다.
    """
    def prepare_dataset(batch):
        # 데이터셋 행으로부터 오디오 데이터 추출
        audio = batch["audio"]
        # 오디오 신호를 Mel-Spectrogram 입력 특징으로 변환
        batch["input_features"] = feature_extractor(
            audio["array"], sampling_rate=audio["sampling_rate"]
        ).input_features[0]
        # 전사 텍스트를 토큰 ID 리스트로 변환
        batch["labels"] = tokenizer(batch["transcription"]).input_ids
        return batch
    return prepare_dataset


# ---------------------------------------------------------------------------- #
#  메인 학습 함수                                                                 #
# ---------------------------------------------------------------------------- #

@exception_guard(location="run_training() -> 학습 루프", reraise=True)
def run_training() -> None:
    """
    전체 학습 파이프라인을 실행한다.
    1. metadata.csv 로드 -> HuggingFace Dataset 변환
    2. 오디오 피처 추출 + 텍스트 토큰화 (map)
    3. 베이스 모델 로딩 + LoRA 적용
    4. Seq2SeqTrainer로 학습 (체크포인트 재개 지원)
    5. 최종 모델 저장
    """
    # ---- 1. 데이터셋 로드 ----
    # 학습에 필요한 메타데이터 파일이 존재하는지 검사
    if not os.path.exists(METADATA_PATH):
        raise TrainingError(f"metadata.csv 없음: {METADATA_PATH}. 먼저 01_build_dataset.py를 실행하세요.")

    # CSV 파일을 읽어 데이터프레임 생성
    df = pd.read_csv(METADATA_PATH, encoding="utf-8-sig")
    logger.info(f"학습 데이터: {len(df)}개 샘플")

    # 상대 경로로 기록된 파일명을 절대 경로로 변환하여 오디오 경로 생성
    df["audio"] = df["file_name"].apply(lambda x: os.path.join(DATASET_DIR, x))

    # 데이터프레임을 HuggingFace 데이터셋 객체로 변환 (pyarrow 에러 방지를 위해 from_dict 사용)
    dataset = Dataset.from_dict({
        "audio": df["audio"].tolist(),
        "transcription": df["transcription"].tolist()
    })
    # 오디오 컬럼을 실제 오디오 데이터 타입으로 캐스팅 (리샘플링 포함)
    dataset = dataset.cast_column("audio", Audio(sampling_rate=CFG["sample_rate"]))

    # ---- 2. 모델/프로세서 로드 ----
    # 베이스 Whisper 모델과 통합 프로세서 로드
    model, processor = load_base_model()
    # 특징 추출기 및 토크나이저 개별 로드 (전처리용)
    feature_extractor = WhisperFeatureExtractor.from_pretrained(CFG["model_id"])
    tokenizer         = WhisperTokenizer.from_pretrained(
        CFG["model_id"], language=CFG["language"], task=CFG["task"]
    )

    # ---- 3. 전처리 map 적용 ----
    # 오디오 특징 추출 및 텍스트 토큰화를 수행할 함수 생성
    prepare_fn = _make_prepare_fn(feature_extractor, tokenizer)
    # 데이터셋 전체에 전처리 함수 적용 (병렬 처리는 Windows 환경 안정성을 위해 1로 설정)
    dataset = dataset.map(
        prepare_fn,
        remove_columns=dataset.column_names,
        num_proc=1,  # Windows 멀티프로세싱 이슈 방지
    )

    # ---- 4. LoRA 적용 ----
    # 모델의 특정 레이어만 학습하도록 LoRA 어댑터 설정 및 주입
    model = apply_lora(model)

    # ---- 5. 학습 인수 설정 ----
    # 기존에 중단된 학습이 있다면 체크포인트에서 재개하도록 경로 검색
    resume_checkpoint = None
    if os.path.exists(LORA_DIR):
        # 출력 디렉터리 내의 모든 체크포인트 폴더 수집
        ckpts = [
            d for d in os.listdir(LORA_DIR)
            if d.startswith("checkpoint-") and os.path.isdir(os.path.join(LORA_DIR, d))
        ]
        if ckpts:
            # 가장 큰 스텝 번호를 가진 최신 체크포인트 선정
            latest = sorted(ckpts, key=lambda x: int(x.split("-")[-1]))[-1]
            resume_checkpoint = os.path.join(LORA_DIR, latest)
            logger.info(f"체크포인트에서 재개: {resume_checkpoint}")

    # HuggingFace Trainer용 학습 하이퍼파라미터 설정
    training_args = Seq2SeqTrainingArguments(
        output_dir                  = LORA_DIR,               # 모델 결과 저장 경로
        per_device_train_batch_size = CFG["batch_size"],      # 장치당 배치 크기
        gradient_accumulation_steps = CFG["gradient_accumulation"], # 경사 누적 스텝 수
        learning_rate               = CFG["learning_rate"],   # 초기 학습률
        warmup_steps                = CFG["warmup_steps"],    # 워밍업 스텝 수
        max_steps                   = CFG["max_steps"],       # 최대 학습 스텝
        gradient_checkpointing      = True,                   # 메모리 절약을 위한 체크포인팅 활성화
        fp16                        = False,                  # 혼합 정밀도 학습 (CPU 환경이므로 비활성화)
        evaluation_strategy         = "no",                   # 검증 생략 (학습 가속화)
        save_steps                  = CFG["save_steps"],      # 모델 저장 주기
        save_total_limit            = 3,                      # 최근 3개의 체크포인트만 유지
        logging_steps               = CFG["logging_steps"],   # 로그 기록 주기
        report_to                   = ["tensorboard"],        # 텐서보드 시각화 연동
        load_best_model_at_end      = False,                  # 마지막 모델을 최적으로 간주
        label_names                 = ["labels"],             # 손실 계산에 사용할 레이블 키
        push_to_hub                 = False,                  # 허브 업로드 비활성화
        remove_unused_columns       = False,                  # 데이터셋 컬럼 유지
    )

    # 패딩 및 마스킹을 수행할 데이터 콜레이터 인스턴스 생성
    data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=processor)
    # 실시간 대시보드 갱신을 위한 콜백 인스턴스 생성
    callback      = DashboardCallback()

    # 최종 Trainer 객체 초기화
    trainer = Seq2SeqTrainer(
        args           = training_args,
        model          = model,
        train_dataset  = dataset,
        data_collator  = data_collator,
        tokenizer      = processor.feature_extractor,
        callbacks      = [callback],
    )

    # ---- 6. 학습 실행 (체크포인트 재개) ----
    # 실시간 모니터링 대시보드 컨텍스트 내에서 학습 실행
    with logger.dashboard_context():
        logger.set_status("Whisper Fine-tuning 중", "엔진 초기화 완료")
        logger.info("학습 프로세스 시작...")
        # 학습 시작 (이전 체크포인트가 있으면 자동으로 재개)
        trainer.train(resume_from_checkpoint=resume_checkpoint)

        # ---- 7. 최종 저장 ----
        logger.set_status("모델 저장 중")
        # 최종 학습된 LoRA 가중치 저장
        trainer.save_model(LORA_DIR)
        # 추론 시 함께 사용할 프로세서 정보 저장
        processor.save_pretrained(LORA_DIR)
        logger.success(f"학습 완료! LoRA 어댑터 저장됨: {LORA_DIR}")
