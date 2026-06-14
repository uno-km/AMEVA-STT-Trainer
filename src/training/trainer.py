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

from datasets import IterableDataset, Features, Sequence, Value
from transformers import (
    WhisperFeatureExtractor,
    WhisperTokenizer,
    WhisperForConditionalGeneration,
    WhisperProcessor,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
)

from src.core.config import CFG, DATASET_DIR, METADATA_PATH, LORA_DIR, GPU_TIER_OVERRIDES
from src.core.exceptions import TrainingError, exception_guard
from src.core.hardware_profile import get_profile
from src.models.whisper_lora import apply_lora
from src.training.callbacks import DashboardCallback
from src.utils import logger

# [RESUME BUG FIX] 글로벌 스킵 누적치 및 안전한 하트비트
_GLOBAL_TOTAL_SKIPPED = 0
_HEARTBEAT_PATH = os.path.join("scratch", "generator_heartbeat.txt")

def _safe_heartbeat(msg: str):
    try:
        os.makedirs(os.path.dirname(_HEARTBEAT_PATH), exist_ok=True)
        with open(_HEARTBEAT_PATH, "a", encoding="utf-8") as f:
            import datetime
            f.write(f"[{datetime.datetime.now()}] {msg}\n")
    except:
        pass


# ---------------------------------------------------------------------------- #
#  데이터 콜레이터 (패딩 및 레이블 마스킹)                                        #
# ---------------------------------------------------------------------------- #

@dataclass
class DataCollatorSpeechSeq2SeqWithPadding:
    """
    [역할] 배치(Batch) 내 학습 샘플들의 입력 특징(Audio) 및 전사(Text) 토큰 길이를 정렬(Padding)
    [매개변수] 
      - processor: WhisperProcessor 객체 (FeatureExtractor 및 Tokenizer 바인딩체)
    """
    processor: Any

    def __call__(self, features: List[Dict[str, Union[List[int], torch.Tensor]]]) -> Dict[str, torch.Tensor]:
        """
        [작동 흐름 및 변수 맵핑]
          - features: List[Dict] 형태 ➡️ 제너레이터가 생성한 개별 데이터 배치 묶음
            * 개별 딕셔너리 구조: {"input_features": List[float], "labels": List[int]}
          - batch: Dict[str, torch.Tensor] ➡️ 패딩 처리된 입력 오디오 배치
            * 추출 결과물: batch["input_features"] (Shape: [Batch_Size, Feature_Dim, Sequence_Len])
          - labels_batch: Dict[str, torch.Tensor] ➡️ 패딩 처리된 텍스트 토큰 배치
            * 추출 결과물: labels_batch["input_ids"] (Shape: [Batch_Size, Max_Token_Len])
          - labels: torch.Tensor ➡️ CrossEntropy 손실 계산 시 패딩 토큰을 무시하기 위해 -100으로 마스킹된 텐서
        """
        # 1. 입력 오디오 데이터의 Mel-Spectrogram 추출 특징들을 모아 최대 길이에 맞춰 패딩 정렬
        input_features = [{"input_features": f["input_features"]} for f in features]
        batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")

        # 2. 텍스트 레이블 토큰(input_ids)을 추출하여 최대 길이에 맞춰 패딩(Padding) 정렬
        label_features = [{"input_ids": f["labels"]} for f in features]
        labels_batch   = self.processor.tokenizer.pad(label_features, return_tensors="pt")
        
        # 3. 패딩 토큰(어텐션 마스크가 1이 아닌 곳)을 -100으로 강제 치환
        # (-100 값은 PyTorch 손실 연산(CrossEntropyLoss) 시 자동으로 역전파 계산에서 완전 무시됨)
        labels = labels_batch["input_ids"].masked_fill(
            labels_batch.attention_mask.ne(1), -100
        )

        # 4. 토크나이저 특성상 문장 시작(BOS) 토큰이 중복 덧붙여진 경우 첫 토큰을 절단하여 강박적 오류 방지
        if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all().cpu().item():
            labels = labels[:, 1:]

        batch["labels"] = labels  # 최종 배치 딕셔너리에 마스킹이 끝난 텐서 대입
        return batch              # 반환형: PyTorch 훈련 파이프라인으로 주입될 최종 텐서 배치 딕셔너리


# ---------------------------------------------------------------------------- #
#  안전한 전처리 엔진 (격리 모드)                                                 #
# ---------------------------------------------------------------------------- #

def _pure_prepare_fn(sample: Dict[str, Any], feature_extractor: WhisperFeatureExtractor, tokenizer: WhisperTokenizer) -> Dict[str, Any]:
    """
    [역할] 멀티프로세싱 파이프라인에서 직렬화(Pickling) 에러를 방지하는 순수 격리식 오디오 전처리 엔진.
    [매개변수]
      - sample: Dict[str, Any] ➡️ {"audio": 오디오절대경로_문자열, "transcription": 전사 한글문장_문자열}
      - feature_extractor: WhisperFeatureExtractor ➡️ 오디오 음파를 Mel-Spectrogram으로 파싱하는 모듈
      - tokenizer: WhisperTokenizer ➡️ 자연어 문장을 숫자 토큰 리스트로 맵핑하는 자연어 모듈
    [반환형]
      - 성공 시: {"input_features": np.ndarray(Mel-Spectrogram), "labels": List[int]}
      - 실패 시: None
    """
    try:
        path = sample["audio"]  # 파일 시스템 내의 로컬 음원 절대경로(String) 추출
        
        # 1. librosa를 사용한 16,000Hz 고정 샘플링 레이트 오디오 로드 및 float32 정밀도 변환
        # (32비트 부동소수점 강제는 윈도우 커널과의 메모리 충돌 에러인 WinError 87을 미연에 차단)
        audio_array, _ = librosa.load(path, sr=16000)
        audio_array = audio_array.astype("float32")
        
        # 2. Whisper 모델의 기본 규격 사양에 맞춰 30초 초과 데이터는 30초 분량만 하드웨어 레벨로 절단
        if len(audio_array) > 16000 * 30:
            audio_array = audio_array[:16000*30]

        # 3. 1차원 주파수를 80차원 오디오 스펙트로그램 특징 텐서(Mel-Spectrogram)로 변환
        input_features = feature_extractor(
            audio_array, sampling_rate=16000
        ).input_features[0]
        
        # 4. 전사 한글 문장 전처리 및 토크나이저를 통한 정수형 Token IDs 리스트 변환
        text = str(sample["transcription"]) if sample["transcription"] else " "
        labels = tokenizer(text).input_ids
        
        return {
            # Hugging Face 스키마 검증 통과를 위해 명시적 중첩 List로 변환
            "input_features": input_features.tolist() if hasattr(input_features, "tolist") else list(input_features),
            "labels": labels.tolist() if hasattr(labels, "tolist") else list(labels)
        }
    except:
        return None  # 손상된 음원 등이 유입될 시 예외 없이 완전 격리 후 무시 처리


def dataset_generator(audio_list: List[str], transcription_list: List[str], model_id: str, language: str, task: str, skip_count: int = 0):
    """
    [역할] 대량의 데이터를 일시 로딩하지 않고 한 장씩 스트리밍 기동하는 Generator(Iterable) 빌더.
    [매개변수]
      - audio_list: List[str] ➡️ 전사 맵핑용 오디오 절대 경로 리스트
      - transcription_list: List[str] ➡️ 전사 정답 한글 텍스트 리스트 (오디오 리스트와 1:1 대치)
      - model_id: str ➡️ 베이스 모델 명칭 (예: "openai/whisper-tiny")
      - language: str ➡️ 타겟 자연어 코드 (예: "Korean")
      - task: str ➡️ 학습 태스크 (예: "transcribe")
      - skip_count: int ➡️ 초고속 건너뛰기 대상 샘플 개수
    """
    from transformers import WhisperFeatureExtractor, WhisperTokenizer
    
    # 코랩 환경(온라인)이면 False, 폐쇄망(오프라인) 환경이면 True로 자동 변경
    try:
        import google.colab
        local_files_only = False
    except ImportError:
        local_files_only = True
    
    # 1. 피클링(Pickle) 직렬화 에러를 완벽 차단하기 위해 제너레이터 함수 스코프 내에서 객체 격리 초기화
    fe = WhisperFeatureExtractor.from_pretrained(model_id, local_files_only=local_files_only)
    tk = WhisperTokenizer.from_pretrained(model_id, language=language, task=task, local_files_only=local_files_only)
    
    global _GLOBAL_TOTAL_SKIPPED
    
    from src.utils import logger
    
    # 2. 오디오 파일과 전사 텍스트를 한 쌍씩 동기화하여 스트리밍 순회 시작
    for audio, transcription in zip(audio_list, transcription_list):
        _GLOBAL_TOTAL_SKIPPED += 1
        
        # [초고속 스킵 로직 및 모니터링 로그]
        if skip_count > 0 and _GLOBAL_TOTAL_SKIPPED <= skip_count:
            if _GLOBAL_TOTAL_SKIPPED % 1000 == 0 or _GLOBAL_TOTAL_SKIPPED == skip_count:
                _safe_heartbeat(f"Fast-Forwarding: {_GLOBAL_TOTAL_SKIPPED}/{skip_count} skipped")
            
            # [최적화] Trainer의 ignore_data_skip=True 옵션과 연계하여
            # Dummy 데이터를 만들거나 yield하지 않고 순식간에 루프만 넘깁니다.
            continue
            
        # 정상 로딩(학습) 구간 진입 시 10개 단위로 백업 로깅
        if _GLOBAL_TOTAL_SKIPPED % 10 == 0:
             _safe_heartbeat(f"Data Loading: {_GLOBAL_TOTAL_SKIPPED} processed")
            
        # 3. 개별 샘플 딕셔너리 구조체 형성 및 전처리 가동
        sample = {"audio": audio, "transcription": transcription}
        processed = _pure_prepare_fn(sample, fe, tk)
        
        # 4. 전처리가 성공한 에셋에 대해 파이프라인 호출부에 한 개씩 양보(Yield) 방출
        if processed:
            yield processed


# ---------------------------------------------------------------------------- #
#  메인 학습 파이프라인                                                            #
# ---------------------------------------------------------------------------- #

@exception_guard(location="run_training()", reraise=True)
def run_training(resume_from_checkpoint: str = None, task_id: str = None):
    """
    [역할] 데이터 로딩 ➡️ LoRA 어댑터 주입 ➡️ 훈련 아규먼트 정합 ➡️ 트레이너 기동 및 저장의 전 과정을 오케스트레이션함.
    [매개변수]
      - resume_from_checkpoint: str ➡️ 이어서 시작할 로컬 체크포인트의 절대경로 (기본값: None)
      - task_id: str ➡️ DB 연동 및 파라미터 매핑을 결정하는 고유 태스크 UUID (기본값: None)
    """
    global METADATA_PATH, DATASET_DIR, _GLOBAL_TOTAL_SKIPPED
    _GLOBAL_TOTAL_SKIPPED = 0

    # ---- [1단계] 데이터셋 경로 확인 및 동적 매핑 ----
    if task_id:
        from src.backend.core.database import db_manager
        
        # 데이터베이스(tb_task)에서 task_id에 매핑된 상세 조작 레코드를 딕셔너리로 조회
        task = db_manager.get_task_details(task_id)
        if task:
            task_nm = task['tsk_nm']  # 사용자가 지정했던 작업 이름 문자열(String) 추출
            
            # [규칙성 매핑] 개별 태스크 전용 데이터셋 폴더와 메타데이터 파일 경로 조립
            task_dataset_dir = os.path.join("dataset", f"{task_nm}_{task_id[:8]}")
            task_metadata_path = os.path.join(task_dataset_dir, "metadata.csv")
            
            # 폴더 실체 여부에 따라 글로벌 전처리 메타 경로 변수들을 동적 교체(Override)
            if os.path.exists(task_metadata_path):
                DATASET_DIR = task_dataset_dir
                METADATA_PATH = task_metadata_path
                logger.info(f"[DYNAMIC] 태스크 전용 데이터셋 감지: {DATASET_DIR}")
            else:
                logger.warning(f"[WARNING] 태스크 폴더는 있으나 metadata.csv가 없습니다: {task_metadata_path}")

            # ---- [핵심 버그 수정부] DB(tb_task_dtl) 내의 2단계 사용자 지정 하이퍼파라미터 연동 파싱 ----
            details = task.get('details', [])  # 각 단계별 메타 상세가 리스트로 유입됨
            
            # 2단계(모델 학습) 전용 설정 레코드만 지능적으로 추출
            step2 = next((d for d in details if d['step_seq'] == 2), None)
            if step2 and step2.get('parameters'):
                try:
                    import json
                    # JSON 포맷팅된 문자열을 파이썬 딕셔너리로 완전 파싱 수행
                    params = json.loads(step2['parameters'])
                    logger.info(f"[PARAMETER OVERRIDE] DB 파라미터로 학습 설정을 덮어씁니다.")
                    
                    # 딕셔너리 키 존재 여부를 엄격하게 판독하여 글로벌 학습 설정 파일(CFG) 값들을 실시간 형변환 덮어쓰기!
                    if "model_id" in params:
                        CFG["model_id"] = params["model_id"]  # 베이스 모델명 (String)
                    if "max_steps" in params:
                        CFG["max_steps"] = int(params["max_steps"])  # 총 훈련 스텝 제한 (Integer)
                    if "learning_rate" in params:
                        CFG["learning_rate"] = float(params["learning_rate"])  # 학습 가중 비율 (Float)
                    if "batch_size" in params:
                        CFG["batch_size"] = int(params["batch_size"])  # 배치 적재 크기 (Integer)
                    if "gradient_accumulation" in params:
                        CFG["gradient_accumulation"] = int(params["gradient_accumulation"])  # 경사도 축적수 (Integer)
                        
                    logger.info(f"  -> model_id: {CFG['model_id']}")
                    logger.info(f"  -> max_steps: {CFG['max_steps']}")
                    logger.info(f"  -> learning_rate: {CFG['learning_rate']}")
                    logger.info(f"  -> batch_size: {CFG['batch_size']}")
                    logger.info(f"  -> gradient_accumulation: {CFG['gradient_accumulation']}")
                except Exception as pe:
                    logger.warning(f"[PARAMETER OVERRIDE WARNING] DB 파라미터 반영 실패: {pe}")

    # 최종 메타데이터 파일 존립 여부를 확인하여 예외 가드 가동
    if not os.path.exists(METADATA_PATH):
        raise TrainingError(f"metadata.csv 파일을 찾을 수 없습니다: {METADATA_PATH}")

    # Pandas 엔진을 가동하여 UTF-8-BOM 인코딩으로 데이터셋 파일명 및 한글 전사 정답 리스트 획득
    df = pd.read_csv(METADATA_PATH, encoding="utf-8-sig")
    audio_paths = [os.path.join(DATASET_DIR, x) for x in df["file_name"].tolist()]  # 각 음원들의 절대경로 리스트 생성
    transcriptions = df["transcription"].tolist()                                  # 한글 매핑 텍스트 리스트 생성
    logger.info(f"[INFO] 학습 데이터 로드 완료: 총 {len(df)}개의 샘플을 준비했습니다.")

    # ---- [2단계] 모델 및 프로세서(토크나이저) 로딩 ----
    if CFG["model_id"] == "small":
        CFG["model_id"] = "openai/whisper-small"
    elif CFG["model_id"] == "tiny":
        CFG["model_id"] = "openai/whisper-tiny"
        
    model_id = CFG["model_id"]  # 덮어쓰기 완료된 타겟 모델명 로드
    
    # ---- [하드웨어 프로파일 감지] ----
    # 실행 시 CPU/GPU/VRAM/CUDA를 자동 감지하여 최적 학습 파라미터를 결정합니다.
    hw = get_profile()
    tier_params = GPU_TIER_OVERRIDES.get(hw.tier, GPU_TIER_OVERRIDES[0])
    
    logger.info(f"[HW] 감지된 환경: {hw.gpu_name} | Tier {hw.tier} | {hw.profile_name}")
    logger.info(f"[HW] 학습 파라미터 적용: batch={tier_params['batch_size']}, "
                f"accumulation={tier_params['gradient_accumulation']}, "
                f"fp16={tier_params['fp16']}, "
                f"checkpointing={tier_params['gradient_checkpointing']}")
    for w in hw.warnings:
        logger.warning(w)

    # 윈도우 CPU 환경에서의 안정성 및 메모리 누수 방지를 위한 특수 매개변수 주입
    #   - torch_dtype=torch.float32: CPU/GPU 공용 안전 기본값 (FP16은 TrainingArguments에서 처리)
    #   - low_cpu_mem_usage=False: 윈도우 가상메모리 할당 에러(WinError 1455) 충돌 원천 차단
    try:
        import google.colab
        local_files_only = False
    except ImportError:
        local_files_only = True
    model = WhisperForConditionalGeneration.from_pretrained(
        model_id, 
        torch_dtype=torch.float32, 
        low_cpu_mem_usage=False,
        local_files_only=local_files_only  # 코랩(온라인) 시 자동 인터넷 다운로드 허용
    )
    
    # 학습 방해 요소(디코딩 강제 매핑 및 유실 억제 토큰) 제거
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []
    
    # [극단적인 중요 설정] model.config.use_cache = False
    # (LoRA 미세조정 시 그래디언트 축적 및 역전파 계산 과정에서 중복 캐싱을 막아 WinError 87 오류를 철저히 차단함)
    model.config.use_cache = False
    
    # [GPU 자동 디바이스 바인딩]
    # Tier 1 이상(CUDA 환경)에서 모델을 GPU로 이동합니다.
    # gradient_checkpointing은 LoRA 주입 후 적용해야 안전하므로 여기선 설정만 예약합니다.
    if hw.tier > 0 and hw.torch_cuda_available:
        model = model.to("cuda")
        logger.info(f"[HW] 모델이 GPU로 이동되었습니다: {hw.gpu_name}")
    
    # 오디오 스펙트로그램 처리 및 한글 디코딩을 주도하는 프로세서 기동
    processor = WhisperProcessor.from_pretrained(
        model_id, language=CFG["language"], task=CFG["task"], local_files_only=local_files_only
    )

    # ---- [3단계] 체크포인트 재개 설정 및 스킵 연산 ----
    # 훈련이 비정상 중단되었을 시, 저장된 폴더를 정밀 소팅하여 번호가 가장 높은 로컬 어댑터 가중치를 체크포인트로 채택
    # (단, 외부 매개변수로 명시적 체크포인트 경로가 들어왔을 시 최우선 순위로 바인딩)
    resume_checkpoint = None
    if resume_from_checkpoint:
        resume_checkpoint = resume_from_checkpoint
        logger.info(f"[RESUME] 사용자 지정 체크포인트 경로를 사용하여 재개합니다: {resume_checkpoint}")
    elif os.path.exists(LORA_DIR):
        ckpts = [d for d in os.listdir(LORA_DIR) if d.startswith("checkpoint-")]
        if ckpts:
            latest = sorted(ckpts, key=lambda x: int(x.split("-")[-1]))[-1]
            resume_checkpoint = os.path.join(LORA_DIR, latest)
            logger.info(f"[RESUME] 이전 학습 기록을 발견했습니다! {resume_checkpoint} 지점부터 이어서 진행합니다.")

    # [FAST-FORWARD] 재개 시 초고속 로딩을 위한 스킵 카운트 자동 계산
    skip_count = 0
    if resume_checkpoint and os.path.exists(os.path.join(resume_checkpoint, "trainer_state.json")):
        try:
            import json
            with open(os.path.join(resume_checkpoint, "trainer_state.json"), "r") as f:
                state = json.load(f)
                global_step = state.get("global_step", 0)
                skip_count = global_step * CFG["batch_size"] * CFG["gradient_accumulation"]
                logger.info(f"⚡ [FAST-FORWARD] IterableDataset 초고속 스킵 가속 활성화: {skip_count}개 샘플 패스")
        except Exception as e:
            logger.warning(f"[FAST-FORWARD] 스킵 연산 실패: {e}")

    # ---- [4단계] 스트리밍 데이터셋(IterableDataset) 구성 ----
    # [윈도우 메모리 오버플로우 영구 예방]
    # 전체 대용량 파일의 음파를 램에 로드하지 않고 학습 스텝 가동 중에 제너레이터가 실시간 스트리밍 바인딩하도록 조치
    ds_features = Features({
        "input_features": Sequence(Sequence(Value("float32"))),
        "labels": Sequence(Value("int64"))
    })
    
    train_dataset = IterableDataset.from_generator(
        dataset_generator, 
        features=ds_features,
        gen_kwargs={
            "audio_list": audio_paths,
            "transcription_list": transcriptions,
            "model_id": model_id,
            "language": CFG["language"],
            "task": CFG["task"],
            "skip_count": skip_count
        }
    )

    # ---- [5단계] LoRA(Low-Rank Adaptation) 어댑터 주입 ----
    # 3천만 개 이상의 전체 Whisper 매개변수를 훈련하는 대신, 1% 미만의 trainable_params(LoRA 레이어)만
    # 모델의 주요 어텐션 가중치층에 주입하여 저스펙 환경에서도 초고속 모델 개조가 일어날 수 있게 매핑
    model = apply_lora(model)

    # [GPU] gradient_checkpointing은 LoRA 주입 완료 후 활성화해야 PEFT와 충돌하지 않음
    # Tier 1 이상 + enable_checkpointing=True인 경우에만 적용
    if tier_params["gradient_checkpointing"] and hw.tier > 0:
        model.enable_input_require_grads()  # PEFT + gradient_checkpointing 호환성 필수 설정
        model.gradient_checkpointing_enable()
        logger.info("[HW] Gradient Checkpointing 활성화 (VRAM 절약 모드)")

    # [가이드 반영] 체크포인트 재개 시 가중치 폭발 방지를 위해 학습률(learning_rate)을 기존 설정의 절반으로 조정
    original_lr = CFG["learning_rate"]
    current_lr = original_lr
    if resume_checkpoint:
        current_lr = original_lr * 0.5
        logger.info(f"[RESUME] 재개 학습 보호막 작동: Learning Rate를 절반으로 낮춥니다. ({original_lr} -> {current_lr})")

    # ---- [6단계] 학습 파라미터(Seq2SeqTrainingArguments) 설정 ----
    # [GPU Tier 자동 적응] hardware_profile.py에서 감지된 Tier 기반으로 파라미터 자동 오버라이드
    # CFG에서 사용자가 명시적으로 설정한 값이 있는 경우 DB 오버라이드가 이미 적용되어 있음
    # 배치/fp16 등은 Tier 오버라이드로 최종 확정됨
    effective_batch_size = tier_params["batch_size"]
    effective_accumulation = tier_params["gradient_accumulation"]
    effective_fp16 = tier_params["fp16"]
    effective_pin_memory = tier_params["dataloader_pin_memory"]
    # gradient_checkpointing은 이미 위에서 model에 직접 적용하였으므로 Trainer에는 False 전달
    # (Trainer 내부에서 중복 enable하면 PEFT 충돌 위험)
    
    training_args = Seq2SeqTrainingArguments(
        output_dir                  = LORA_DIR,                         # 가중치 어댑터 결과 저장 폴더 (String)
        per_device_train_batch_size = effective_batch_size,             # [Tier 자동] 배치 당 연산 데이터 크기 (Integer)
        gradient_accumulation_steps = effective_accumulation,           # [Tier 자동] 메모리 부족 시 그라디언트 누적 (Integer)
        learning_rate               = current_lr,                       # 옵티마이저 학습율 가중비율 (Float)
        warmup_steps                = CFG["warmup_steps"],              # 초반 오버슈팅 방지를 위한 적응용 스텝수 (Integer)
        max_steps                   = CFG["max_steps"],                 # 최대 총 훈련 반복 횟수 (Integer)
        gradient_checkpointing      = False,                            # 이미 model에 직접 적용했으므로 Trainer는 False (PEFT 호환)
        fp16                        = effective_fp16,                   # [Tier 자동] GPU: True(FP16 가속), CPU: False (Boolean)
        bf16                        = False,                            # bfloat16 포맷 오작동 배제용 비활성화 (Boolean)
        eval_strategy               = "no",                             # 검증 비용 단 1초도 쓰지 않도록 평가 생략 (String)
        save_steps                  = CFG["save_steps"],                # 체크포인트 디렉터리 물리 저장 주기 (Integer)
        save_total_limit            = 3,                                # 저장 공간 절약을 위해 최신 3개 보존 후 구형 자동 삭제 (Integer)
        logging_steps               = CFG["logging_steps"],             # 대시보드 및 터미널 출력용 로깅 주기 (Integer)
        report_to                   = ["wandb"] if CFG["wandb"]["enabled"] else "none",
        disable_tqdm                = True,                             # 콘솔 텍스트 밀림 및 가독성 훼손 방지를 위해 TQDM 비활성화 (Boolean)
        dataloader_num_workers      = 0,                                # 윈도우 스레드 포크 오류인 WinError 87 방지 (Integer)
        dataloader_pin_memory       = effective_pin_memory,             # [Tier 자동] GPU 환경: True(DMA 전송 가속), CPU: False (Boolean)
        remove_unused_columns       = False,                            # 메타 데이터 잃지 않기 위해 정밀 보존 (Boolean)
        push_to_hub                 = False,                            # 온라인 공유 업로드 비활성화 (Boolean)
        optim                       = "adamw_torch",                    # PyTorch 빌트인 AdamW 정밀 옵티마이저 활용 (String)
        max_grad_norm               = 1.0,                              # 그라디언트 폭발을 강력 억제하는 클리핑 (Float)
        ignore_data_skip            = True,                             # [최적화] Dataset Generator에서 자체 스킵하므로 Trainer 중복 스킵 차단
    )

    import threading
    stop_io_event = threading.Event()
    
    # 오디오/텍스트 배치 가공을 위한 패딩 객체 및 실시간 훈련 통계를 수신해 DB/UI로 뿜어주는 콜백 생성
    data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=processor)
    callback      = DashboardCallback(task_id=task_id, stop_io_event=stop_io_event)

    # HuggingFace Seq2SeqTrainer 공식 프레임워크 초기화
    trainer = Seq2SeqTrainer(
        args           = training_args,
        model          = model,
        train_dataset  = train_dataset,
        data_collator  = data_collator,
        callbacks      = [callback],
    )

    # ---- [7단계] 본격적인 학습 실행 (Training Start!) ----
    logger.info("[START] 모든 준비가 끝났습니다. 학습을 시작합니다.")
    
    if resume_checkpoint:
        logger.info("⏳ [WARNING] 허깅페이스 엔진이 과거의 거대한 옵티마이저 가중치(약 3GB)를 디스크에서 RAM으로 불러오고 있습니다...")
        logger.info("⏳ [WARNING] 이 압축 해제 및 메모리 할당 작업은 컴퓨터 성능에 따라 2~5분 정도 소요될 수 있습니다. 멈춘 것이 아니니 잠시만 기다려 주세요!")
        
        # [블랙박스 가시화] 허깅페이스 내부 로딩 중 윈도우 디스크 I/O 속도 모니터링 스레드 가동
        import psutil
        import time
        
        def io_monitor(pid, stop_event):
            try:
                p = psutil.Process(pid)
                last_io = p.io_counters()
                start_time = time.time()
                while not stop_event.is_set():
                    time.sleep(2)
                    
                    if time.time() - start_time > 600:
                        logger.error("🚨 [I/O Monitor] 10분 경과 타임아웃 발생! 프로세스가 교착 상태(Deadlock)에 빠진 것으로 의심됩니다.")
                        break
                        
                    curr_io = p.io_counters()
                    read_mb = (curr_io.read_bytes - last_io.read_bytes) / (1024 * 1024)
                    # 2초 동안 1MB 이상 읽었을 때만 로깅 (과도한 출력 방지)
                    if read_mb > 1.0:
                        logger.info(f"💿 [I/O Monitor] 디스크 맹렬히 읽는 중... 최근 2초간 {read_mb:.1f} MB 로드 완료")
                    last_io = curr_io
            except Exception:
                pass

        io_thread = threading.Thread(target=io_monitor, args=(os.getpid(), stop_io_event))
        io_thread.daemon = True
        io_thread.start()
    
    # 터미널 창을 미려한 GUI 관제 콘솔 화면 테마로 락온(dashboard_context)
    with logger.dashboard_context():
        try:
            logger.set_status("Whisper Fine-tuning", "Engine Ready")
            
            # 메인 학습 실행 ➡️ 만약 resume_checkpoint 경로가 할당되면 0이 아닌 해당 시점부터 가중치를 이어받음
            trainer.train(resume_from_checkpoint=resume_checkpoint)
            
            # 허깅페이스 락이 풀리고 메인 루프 진입 성공 시 I/O 모니터 스레드 종료
            if resume_checkpoint:
                stop_io_event.set()
            
            # ---- [8단계] 학습 완료 후 최종 저장 ----
            logger.set_status("Saving Model", "Complete")
            
            # 미세조정(Fine-Tuning)이 끝난 최상의 LoRA 어댑터 가중치 물리 파일들 저장
            trainer.save_model(LORA_DIR)
            
            # 추론(Inference) 단계에서 로드할 수 있도록 전처리 토크나이저 및 프로세서 파일 병합 저장
            processor.save_pretrained(LORA_DIR)
            logger.success(f"[SUCCESS] 학습이 무사히 완료되었습니다. 저장 위치: {LORA_DIR}")
            
        except Exception as e:
            # 학습 루프 파괴 시 원인 분석을 돕기 위해 트레이스백 상세 내용을 로그에 직격 적재 후 에러 전파
            error_msg = f"[ERROR] 학습 루프 중 치명적 오류 발생: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
            raise e

