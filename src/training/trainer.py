"""
src/training/trainer.py
Whisper + LoRA 학습 파이프라인 (안정성 + 편의성 통합 버전)

핵심 기능:
  - IterableDataset (Streaming): 윈도우 메모리 맵핑 에러(WinError 87)를 원천 차단.
  - 자동 체크포인트 재개: 중단된 학습을 마지막 저장 지점부터 이어서 진행.
  - 실시간 대시보드: Rich 라이브러리를 활용한 시각적인 학습 현황 모니터링.
  - 안전한 데이터 로딩: 피클링 에러 방지를 위해 전처리 로직을 격리 처리.
"""
import os
import torch
import pandas as pd
import librosa
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Union

from datasets import IterableDataset
from transformers import (
    WhisperFeatureExtractor,
    WhisperTokenizer,
    WhisperForConditionalGeneration,
    WhisperProcessor,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
)

from src.core.config import CFG, DATASET_DIR, METADATA_PATH, LORA_DIR
from src.core.exceptions import TrainingError, exception_guard
from src.models.whisper_lora import apply_lora
from src.training.callbacks import DashboardCallback
from src.utils import logger


# ---------------------------------------------------------------------------- #
#  데이터 콜레이터 (패딩 및 레이블 마스킹)                                        #
# ---------------------------------------------------------------------------- #

@dataclass
class DataCollatorSpeechSeq2SeqWithPadding:
    """
    배치 내 샘플들의 길이를 맞추고 레이블에서 패딩 토큰을 -100으로 마스킹한다.
    (-100은 CrossEntropyLoss에서 자동으로 무시됨)
    """
    processor: Any

    def __call__(self, features: List[Dict[str, Union[List[int], torch.Tensor]]]) -> Dict[str, torch.Tensor]:
        # 입력 오디오 특징 추출 및 패딩
        input_features = [{"input_features": f["input_features"]} for f in features]
        batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")

        # 텍스트 레이블 추출 및 패딩
        label_features = [{"input_ids": f["labels"]} for f in features]
        labels_batch   = self.processor.tokenizer.pad(label_features, return_tensors="pt")
        
        # 패딩된 영역을 -100으로 치환하여 손실 계산 시 제외되도록 설정
        labels = labels_batch["input_ids"].masked_fill(
            labels_batch.attention_mask.ne(1), -100
        )

        # 문장 시작(BOS) 토큰 중복 방지
        if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all().cpu().item():
            labels = labels[:, 1:]

        batch["labels"] = labels
        return batch


# ---------------------------------------------------------------------------- #
#  안전한 전처리 엔진 (격리 모드)                                                 #
# ---------------------------------------------------------------------------- #

def _pure_prepare_fn(sample, feature_extractor, tokenizer):
    """
    외부 객체(logger, rich 등)를 절대 참조하지 않는 순수 전처리 함수.
    이 함수는 피클링 에러를 방지하기 위해 제너레이터 내부에서만 작동합니다.
    """
    try:
        path = sample["audio"]
        # 오디오 로드 및 float32 강제 (WinError 87 방지)
        audio_array, _ = librosa.load(path, sr=16000)
        audio_array = audio_array.astype("float32")
        
        # 30초 초과 데이터는 Whisper 기본 사양에 맞춰 절단
        if len(audio_array) > 16000 * 30:
            audio_array = audio_array[:16000*30]

        # Mel-Spectrogram 추출
        input_features = feature_extractor(
            audio_array, sampling_rate=16000
        ).input_features[0]
        
        # 전사 텍스트 토큰화
        text = str(sample["transcription"]) if sample["transcription"] else " "
        labels = tokenizer(text).input_ids
        
        return {
            "input_features": input_features,
            "labels": labels
        }
    except:
        return None

def dataset_generator(audio_list, transcription_list, model_id, language, task):
    """
    멀티프로세싱 호환을 위해 최소한의 기본 타입 인자만 받는 데이터 제너레이터.
    내부에서 필요한 도구(fe, tk)를 로컬로 생성하여 외부 상태 오염을 방지합니다.
    """
    from transformers import WhisperFeatureExtractor, WhisperTokenizer
    
    # 제너레이터 내부에서 전처리 도구 초기화 (피클링 에러 해결의 핵심)
    # [수정] 인터넷 의존성 제거: local_files_only=True 추가
    fe = WhisperFeatureExtractor.from_pretrained(model_id, local_files_only=True)
    tk = WhisperTokenizer.from_pretrained(model_id, language=language, task=task, local_files_only=True)
    
    # 카운터 추가 및 로그 파일 직결
    count = 0
    from src.utils import logger
    
    for audio, transcription in zip(audio_list, transcription_list):
        count += 1
        if count % 10 == 0:  # 10개마다 로그 파일 및 심박계 파일에 기록
             logger.info(f"[Data Loading] {count}/{len(audio_list)} samples processed... (Searching for resume point)")
             # [긴급 확인용] 텍스트 파일에 직접 기록 (로그 설정 영향 안 받음)
             with open("scratch/generator_heartbeat.txt", "a") as f:
                 import datetime
                 f.write(f"[{datetime.datetime.now()}] Data Loading: {count} samples processed\n")
        
        sample = {"audio": audio, "transcription": transcription}
        processed = _pure_prepare_fn(sample, fe, tk)
        if processed:
            yield processed


# ---------------------------------------------------------------------------- #
#  메인 학습 파이프라인                                                            #
# ---------------------------------------------------------------------------- #

@exception_guard(location="run_training()", reraise=True)
def run_training(resume_from_checkpoint: str = None) -> None:
    """
    전체 학습 파이프라인을 총괄하는 메인 함수입니다.
    데이터 준비부터 모델 로딩, LoRA 적용, 최종 학습 및 저장까지의 전 과정을 제어합니다.
    """
    
    # ---- [1단계] 데이터셋 경로 확보 및 메타데이터 로드 ----
    # 학습의 재료가 되는 metadata.csv 파일이 있는지 먼저 확인합니다.
    if not os.path.exists(METADATA_PATH):
        raise TrainingError(f"metadata.csv 파일을 찾을 수 없습니다: {METADATA_PATH}")

    # CSV를 읽어 오디오 파일의 절대 경로 리스트와 전사(Transcription) 텍스트를 준비합니다.
    df = pd.read_csv(METADATA_PATH, encoding="utf-8-sig")
    audio_paths = [os.path.join(DATASET_DIR, x) for x in df["file_name"].tolist()]
    transcriptions = df["transcription"].tolist()
    logger.info(f"[INFO] 학습 데이터 로드 완료: 총 {len(df)}개의 샘플을 준비했습니다.")

    # ---- [2단계] 모델 및 프로세서(토크나이저) 로딩 ----
    # 사용자가 설정한 베이스 모델(예: whisper-tiny)을 불러옵니다.
    model_id = CFG["model_id"]
    
    # [Windows CPU 최적화 포인트]
    # 1. torch_dtype=torch.float32: CPU에서 가장 안정적인 연산 정밀도를 강제합니다.
    # 2. low_cpu_mem_usage=False: 윈도우의 메모리 할당 방식과의 충돌을 방지합니다.
    model = WhisperForConditionalGeneration.from_pretrained(
        model_id, 
        torch_dtype=torch.float32, 
        low_cpu_mem_usage=False,
        local_files_only=True
    )
    
    # 학습 시 불필요하게 디코딩을 간섭하는 설정들을 초기화하여 충돌을 방지합니다.
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []
    
    # [중요] model.config.use_cache = False:
    # 윈도우에서 'WinError 87'을 일으키는 가장 큰 원인 중 하나인 그래디언트 체크포인팅 충돌을 해결합니다.
    model.config.use_cache = False
    
    # 오디오 특징 추출 및 텍스트 토큰화를 담당하는 프로세서를 로드합니다.
    processor = WhisperProcessor.from_pretrained(
        model_id, language=CFG["language"], task=CFG["task"]
    )

    # ---- [3단계] 스트리밍 데이터셋(IterableDataset) 구성 ----
    # [Windows 최적화 핵심] 
    # 데이터를 한꺼번에 메모리에 올리지 않고 학습할 때 실시간으로 하나씩 읽어오는 방식을 채택합니다.
    # 이는 윈도우의 고질적인 'Memory Mapping' 오류를 원천 차단하는 가장 강력한 해결책입니다.
    train_dataset = IterableDataset.from_generator(
        dataset_generator, 
        gen_kwargs={
            "audio_list": audio_paths,
            "transcription_list": transcriptions,
            "model_id": model_id,
            "language": CFG["language"],
            "task": CFG["task"]
        }
    )

    # ---- [4단계] LoRA(Low-Rank Adaptation) 어댑터 주입 ----
    # 베이스 모델의 가중치는 고정하고 효율적인 학습을 위한 LoRA 레이어를 추가합니다.
    # 이를 통해 저사양 환경(CPU)에서도 강력한 성능 향상을 꾀할 수 있습니다.
    model = apply_lora(model)

    # ---- [5단계] 체크포인트 자동 검색 및 재개 설정 ----
    # 만약 이전에 학습하다가 멈춘 기록(checkpoint-*)이 있다면 자동으로 찾아냅니다.
    resume_checkpoint = None
    if os.path.exists(LORA_DIR):
        ckpts = [d for d in os.listdir(LORA_DIR) if d.startswith("checkpoint-")]
        if ckpts:
            # 가장 마지막에 저장된(숫자가 가장 큰) 체크포인트를 선정합니다.
            latest = sorted(ckpts, key=lambda x: int(x.split("-")[-1]))[-1]
            resume_checkpoint = os.path.join(LORA_DIR, latest)
            logger.info(f"[RESUME] 이전 학습 기록을 발견했습니다! {resume_checkpoint} 지점부터 이어서 진행합니다.")

    # ---- [6단계] 학습 파라미터(Seq2SeqTrainingArguments) 설정 ----
    # 윈도우 CPU 환경에서 가장 '안전'하고 '안정적'인 설정값들을 배치합니다.
    training_args = Seq2SeqTrainingArguments(
        output_dir                  = LORA_DIR,               # 결과물 저장 경로
        per_device_train_batch_size = CFG["batch_size"],      # 한 번에 공부할 데이터 양
        gradient_accumulation_steps = CFG["gradient_accumulation"], # 경사 누적 (메모리 절약 기술)
        learning_rate               = CFG["learning_rate"],   # 학습 속도 조절
        warmup_steps                = CFG["warmup_steps"],    # 초반 적응 기간
        max_steps                   = CFG["max_steps"],       # 총 학습 횟수
        gradient_checkpointing      = False,                  # [Windows CPU] 안정성을 위해 비활성화
        fp16                        = False,                  # [Windows CPU] 반정밀도 연산 제외
        bf16                        = False,                  # [Windows CPU] bfloat16 제외
        eval_strategy               = "no",                   # 검증 생략 (오직 학습에만 집중)
        save_steps                  = CFG["save_steps"],      # 모델 저장 주기
        save_total_limit            = 3,                      # 최근 3개의 체크포인트만 유지 (용량 관리)
        logging_steps               = CFG["logging_steps"],   # 로그 기록 주기
        report_to                   = ["wandb"] if CFG["wandb"]["enabled"] else "none", 
        disable_tqdm                = True,                   # 터미널 로그 도배 방지
        dataloader_num_workers      = 0,                      # [Windows] 멀티프로세싱 충돌 방지 핵심
        dataloader_pin_memory       = False,                  # [Windows] WinError 87 방지 핵심
        remove_unused_columns       = False,                  # 데이터셋 컬럼 유실 방지
        push_to_hub                 = False,                  # 온라인 업로드 비활성화
        optim                       = "adamw_torch",          # 표준 옵티마이저 강제
    )

    # 데이터를 묶어줄 콜레이터와 시각적 피드백을 위한 대시보드 콜백을 생성합니다.
    data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=processor)
    callback      = DashboardCallback()

    # 최종적인 Trainer 객체를 초기화합니다.
    trainer = Seq2SeqTrainer(
        args           = training_args,
        model          = model,
        train_dataset  = train_dataset,
        data_collator  = data_collator,
        callbacks      = [callback],
    )

    # ---- [7단계] 본격적인 학습 실행 (Training Start!) ----
    logger.info("[START] 모든 준비가 끝났습니다. 학습을 시작합니다.")
    
    # 대시보드 컨텍스트를 열어 터미널에 진행 상황을 표시합니다.
    with logger.dashboard_context():
        try:
            logger.set_status("Whisper Fine-tuning", "Engine Ready")
            # 학습 시작! (체크포인트가 있다면 자동으로 그 시점부터 로드합니다.)
            trainer.train(resume_from_checkpoint=resume_checkpoint)
            
            # ---- [8단계] 학습 완료 후 최종 저장 ----
            logger.set_status("Saving Model", "Complete")
            # 최종 학습된 LoRA 가중치를 디스크에 영구 저장합니다.
            trainer.save_model(LORA_DIR)
            # 추론 시 꼭 필요한 프로세서 정보도 함께 저장합니다.
            processor.save_pretrained(LORA_DIR)
            logger.success(f"[SUCCESS] 학습이 무사히 완료되었습니다. 저장 위치: {LORA_DIR}")
            
        except Exception as e:
            # 예상치 못한 에러 발생 시 상세한 기록을 남기고 상위로 던집니다.
            error_msg = f"[ERROR] 학습 루프 중 치명적 오류 발생: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise e
