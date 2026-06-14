"""
src/models/whisper_lora.py
Whisper 모델 로딩 및 LoRA 어댑터 설정.
- base 모델 로딩 (HuggingFace)
- PEFT LoRA 적용
- 학습 후 저장 및 병합(merge_and_unload) 지원
"""
import os
import shutil
from transformers import WhisperForConditionalGeneration, WhisperProcessor
from peft import LoraConfig, get_peft_model, PeftModel

from src.core.config import CFG, LORA_DIR, MERGED_DIR, GGUF_DIR
from src.core.exceptions import ModelError, exception_guard
from src.utils import logger

# Google Colab 환경(온라인) 감지하여 local_files_only 값 동적 지정
try:
    import google.colab
    LOCAL_FILES_ONLY = False
except ImportError:
    LOCAL_FILES_ONLY = True


@exception_guard(location="load_base_model() -> HuggingFace 로딩", reraise=True)
def load_base_model():
    """
    설정된 MODEL_ID로 Whisper 베이스 모델과 프로세서를 로드한다.
    Returns: (model, processor)
    """
    # 전역 설정에서 HuggingFace 모델 식별자 가져오기 (예: openai/whisper-tiny)
    model_id = CFG["model_id"]
    logger.info(f"베이스 모델 로딩: {model_id}")

    # HuggingFace Hub 에서 사전 학습된 Whisper 모델 가중치 로드
    # [수정] 오프라인 환경 지원을 위해 로컬 파일 우선 로드 설정 (코랩 등 온라인 환경 시 자동 다운로드)
    model = WhisperForConditionalGeneration.from_pretrained(model_id, local_files_only=LOCAL_FILES_ONLY)
    # 학습 시 불필요한 강제 디코더 토큰 비활성화
    # (없애지 않으면 학습 시 토큰 ID 충돌 발생 가능)
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens    = []

    # 언어 및 태스크 설정이 포함된 프로세서(토크나이저+특징 추출기) 로드
    processor = WhisperProcessor.from_pretrained(
        model_id,
        language=CFG["language"],
        task=CFG["task"],
        local_files_only=LOCAL_FILES_ONLY
    )
    return model, processor


@exception_guard(location="apply_lora() -> PEFT LoRA 적용", reraise=True)
def apply_lora(model):
    """
    베이스 모델에 LoRA 어댑터를 적용한다.
    target_modules: Whisper 인코더/디코더의 어텐션 Q, V 행렬만 학습 (파라미터 절감).
    Returns: LoRA가 적용된 model
    """
    # LoRA 설정 객체 생성
    lora_cfg = LoraConfig(
        r            = CFG["lora_r"],       # 저차원 랭크: 행렬 분해 차원 수
        lora_alpha   = CFG["lora_alpha"],   # 스케일링 인자: 업데이트 강도 조절
        target_modules = ["q_proj", "v_proj"],  # Whisper Attention 레이어
        lora_dropout = CFG["lora_dropout"], # 과적합 방지를 위한 드롭아웃 비율
        bias         = "none",              # 바이어스 파라미터는 학습하지 않음
    )
    # 베이스 모델에 LoRA 어댑터 주입 (베이스 가중치는 동결됨)
    model = get_peft_model(model, lora_cfg)
    # 학습 대상 파라미터 수와 전체 파라미터 수를 터미널에 출력
    model.print_trainable_parameters()
    return model


@exception_guard(location="load_for_inference() -> LoRA 어댑터 로딩")
def load_for_inference():
    """
    추론/평가용으로 베이스 모델 + LoRA 어댑터를 로드한다.
    Returns: (model, processor) or (None, None) on failure
    """
    # 학습이 완료된 LoRA 어댑터 디렉터리 존재 여부 확인
    if not os.path.exists(LORA_DIR):
        raise ModelError(f"LoRA 어댑터 없음: {LORA_DIR}. 먼저 학습을 실행하세요.")

    # 설정에서 모델 식별자 로드
    model_id = CFG["model_id"]
    # 베이스 모델을 HuggingFace 에서 로드
    model    = WhisperForConditionalGeneration.from_pretrained(model_id, local_files_only=LOCAL_FILES_ONLY)
    # 저장된 LoRA 어댑터를 베이스 모델 위에 얹기
    model    = PeftModel.from_pretrained(model, LORA_DIR)
    # 추론 전용 모드 설정 (드롭아웃 비활성화, 배치 정규화 고정)
    model.eval()

    # 추론에 사용할 프로세서 로드 (자막 디코딩 및 오디오 특징 추출)
    processor = WhisperProcessor.from_pretrained(model_id, language=CFG["language"], task=CFG["task"], local_files_only=LOCAL_FILES_ONLY)
    return model, processor


@exception_guard(location="merge_and_save() -> LoRA 병합", reraise=True)
def merge_and_save():
    """
    LoRA 어댑터를 베이스 모델에 병합하고 MERGED_DIR에 저장한다.
    병합된 모델은 표준 Whisper HF 모델로 사용 가능하다.
    """
    # 설정에서 베이스 모델 식별자 로드
    model_id = CFG["model_id"]
    logger.info("LoRA 병합 시작...")

    # 병합 작업을 위해 베이스 모델을 새로 로드 (기존 메모리와 독립)
    base_model = WhisperForConditionalGeneration.from_pretrained(model_id, local_files_only=LOCAL_FILES_ONLY)
    # 저장된 LoRA 어댑터를 베이스 모델 위에 로드
    peft_model = PeftModel.from_pretrained(base_model, LORA_DIR)

    # merge_and_unload: LoRA 가중치를 베이스 가중치에 흡수 후 순수 모델 반환
    # 병합 후에는 LoRA 레이어가 없어지고 일반 Whisper 모델처럼 동작
    merged = peft_model.merge_and_unload()

    # 병합 모델 저장 디렉터리 생성 (없으면 자동 생성)
    os.makedirs(MERGED_DIR, exist_ok=True)
    # 병합된 모델 가중치와 설정 파일을 MERGED_DIR 에 저장
    merged.save_pretrained(MERGED_DIR)

    # 프로세서도 같은 디렉터리에 저장 (추론 시 함께 필요)
    processor = WhisperProcessor.from_pretrained(model_id, local_files_only=LOCAL_FILES_ONLY)
    processor.save_pretrained(MERGED_DIR)
    # whisper.cpp 변환 스크립트가 요구하는 vocab.json 파일을 강제로 생성
    processor.tokenizer.save_vocabulary(MERGED_DIR)

    # [중요] whisper.cpp의 convert-h5-to-ggml.py 레시피가 요구하는 added_tokens.json 등 누락 파일 강제 복사
    try:
        model_folder_name = "models--" + model_id.replace("/", "--")
        cache_hub_dir = os.path.join(os.environ.get("HF_HOME", r"C:\ameva\models\stt"), "hub", model_folder_name, "snapshots")
        if os.path.exists(cache_hub_dir):
            snapshots = sorted(os.listdir(cache_hub_dir))
            if snapshots:
                latest_snapshot_dir = os.path.join(cache_hub_dir, snapshots[-1])
                for f_name in ["added_tokens.json", "normalizer.json", "merges.txt", "vocab.json"]:
                    src_file = os.path.join(latest_snapshot_dir, f_name)
                    dest_file = os.path.join(MERGED_DIR, f_name)
                    if os.path.exists(src_file) and not os.path.exists(dest_file):
                        shutil.copy(src_file, dest_file)
                        logger.info(f"[MERGE] whisper.cpp 연동용 {f_name} 복사 완료 -> {dest_file}")
    except Exception as e:
        logger.warning(f"[MERGE] whisper.cpp 토크나이저 파일 복제 오류 (양자화 시 주의): {e}")

    logger.info(f"병합 완료 -> {MERGED_DIR}")
    return MERGED_DIR
