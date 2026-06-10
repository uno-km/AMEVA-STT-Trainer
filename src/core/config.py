"""
src/core/config.py
프로젝트 전체 설정 관리자.
- configs/train_config.yaml을 로드하거나, 기본값으로 동작한다.
- 모든 경로 및 하이퍼파라미터의 단일 진실 공급원(Single Source of Truth).
"""
import os
import yaml


# ---------------------------------------------------------------------------- #
#  경로 상수 (변경 시 이곳만 수정하면 된다)                                       #
# ---------------------------------------------------------------------------- #

# 프로젝트 루트 (이 파일 기준 2단계 상위)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Hugging Face 모델 캐시 디렉토리를 외부 공통 폴더로 지정
os.environ["HF_HOME"] = r"C:\ameva\models\stt"

# --- Dynamic Task-Specific Paths ---
ACTIVE_TASK_ID = os.environ.get("CURRENT_TASK_ID")
DATASET_DIR     = os.path.join(ROOT_DIR, "dataset")

def resolve_paths():
    global OUTPUTS_DIR, LORA_DIR, MERGED_DIR, METADATA_PATH
    
    if ACTIVE_TASK_ID:
        try:
            # 순환 참조 방지를 위해 함수 내에서 임포트
            from src.backend.core.database import db_manager
            task = db_manager.get_task_details(ACTIVE_TASK_ID)
            if task:
                # 01_build_dataset.py 규칙: {name}_{id[:8]}
                folder_name = f"{task['tsk_nm']}_{ACTIVE_TASK_ID[:8]}"
                
                OUTPUTS_DIR = os.path.join(ROOT_DIR, "outputs", ACTIVE_TASK_ID)
                LORA_DIR    = os.path.join(OUTPUTS_DIR, "lora_adapter")
                MERGED_DIR  = os.path.join(OUTPUTS_DIR, "merged_model")
                METADATA_PATH = os.path.join(DATASET_DIR, folder_name, "metadata.csv")
                return
        except Exception:
            pass

    # 기본값 (ID가 없거나 DB 조회 실패 시)
    OUTPUTS_DIR     = os.path.join(ROOT_DIR, "outputs")
    LORA_DIR        = os.path.join(OUTPUTS_DIR, "lora_adapter")
    MERGED_DIR      = os.path.join(OUTPUTS_DIR, "merged_model")
    METADATA_PATH   = os.path.join(DATASET_DIR, "metadata.csv")

resolve_paths()

# 실행 로그 및 에러 로그가 저장될 디렉터리
LOG_DIR         = os.path.join(ROOT_DIR, "logs")

# GGUF 모델 저장 경로 (외부 공통 저장소 혹은 프로젝트 내부 fallback)
GGUF_DIR_PRIMARY = r"C:\ameva\models\stt"
if os.path.exists(GGUF_DIR_PRIMARY):
    GGUF_DIR = GGUF_DIR_PRIMARY
else:
    GGUF_DIR = os.path.join(ROOT_DIR, "models", "ggml")

# 설정 파일 경로
CONFIG_PATH     = os.path.join(ROOT_DIR, "configs", "train_config.yaml")


# ---------------------------------------------------------------------------- #
#  기본 설정값                                                                   #
# ---------------------------------------------------------------------------- #

DEFAULTS = {
    # 데이터 수집
    "channel_url"            : "https://www.youtube.com/@syukaworld/videos",
    "max_videos"             : 30,           # 한 번에 수집할 최대 영상 수
    "sample_rate"            : 16000,        # Whisper 요구 샘플링 레이트 (Hz)
    "max_chunk_duration_ms"  : 25000,        # 25초 (30초 안전 마진)
    "min_chunk_duration_ms"  : 3000,         # 3초 미만 청크 버림
    "audio_padding_ms"       : 100,          # 단어 잘림 방지 패딩

    # 학습
    "model_id"               : "openai/whisper-tiny",  # HuggingFace 모델 식별자
    "language"               : "Korean",
    "task"                   : "transcribe",
    "batch_size"             : 2,            # 배치당 샘플 수 (CPU 환경 최소값)
    "gradient_accumulation"  : 8,            # 실질 배치 크기 = batch_size × gradient_accumulation
    "learning_rate"          : 1e-4,         # [수정] LoRA 어댑터 학습률 (1e-3은 치명적 망각 유발, 1e-4가 황금비율)
    "max_steps"              : 400,          # [수정] 전체 학습 스텝 수 (Tiny 모델 기준 과적합 방지)
    "save_steps"             : 100,          # 체크포인트 저장 주기
    "logging_steps"          : 10,           # 로그 출력 주기
    "warmup_steps"           : 50,           # 학습률 워밍업 스텝 수
    "lora_r"                 : 32,           # LoRA 저차원 랭크(r)
    "lora_alpha"             : 64,           # LoRA 스케일링 인자(α)
    "lora_dropout"           : 0.05,         # LoRA 드롭아웃 비율

    # 평가
    "eval_samples"           : 50,           # 평가 시 무작위 추출 샘플 수

    # WandB
    "wandb": {
        "enabled"       : False,
        "project"       : "AMEVA-STT-Trainer",
        "mode"          : "disabled",
        "log_artifacts" : False,
    }
}

# ---------------------------------------------------------------------------- #
#  모델 체급별 파인튜닝 황금 비율 레시피 (동적 전환용)                              #
# ---------------------------------------------------------------------------- #

MODEL_DEFAULTS = {
    "openai/whisper-tiny": {
        "description"            : "파라미터 39M. CPU 환경 최적화. 가볍고 빠른 도메인 학습에 적합.",
        "learning_rate"          : 1e-4,    # LoRA 학습 효율을 위한 상향 (1e-4 권장)
        "max_steps"              : 400,     # 300~600 스텝 사이 권장
        "batch_size"             : 2,
        "gradient_accumulation"  : 4,       # CPU 연산 속도 고려 (실질 배치 8)
        "warmup_steps"           : 50,
        "lora_r"                 : 16,      # CPU 부담 경감을 위한 R16
        "lora_alpha"             : 32,
    },
    "openai/whisper-small": {
        "description"            : "파라미터 244M. CPU 환경 최적화. LoRA를 통한 고효율 중상급 파인튜닝.",
        "learning_rate"          : 1e-4,    # LoRA + CPU 환경 권장 학습률
        "max_steps"              : 800,     # 중상급 성능을 위한 현실적 타협점
        "batch_size"             : 1,
        "gradient_accumulation"  : 8,       # CPU 연산 속도와 배치의 최적 타협 (실질 배치 8)
        "warmup_steps"           : 80,
        "lora_r"                 : 16,      # CPU 연산 부담 경감
        "lora_alpha"             : 32,
    }
}



# ---------------------------------------------------------------------------- #
#  설정 로더                                                                     #
# ---------------------------------------------------------------------------- #

def load_config() -> dict:
    """
    YAML 설정 파일을 로드한다.
    파일이 없으면 DEFAULTS를 반환한다.
    """
    # YAML 파일이 없으면 기본값 복사본을 그대로 반환
    if not os.path.exists(CONFIG_PATH):
        return DEFAULTS.copy()

    # UTF-8 인코딩으로 YAML 파일 열기
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        # safe_load: 임의 파이썬 객체 실행 없이 안전하게 파싱 (None 방어 처리 포함)
        user_cfg = yaml.safe_load(f) or {}

    # 사용자 설정으로 기본값을 덮어씌움
    cfg = DEFAULTS.copy()
    cfg.update(user_cfg)
    return cfg


# 전역 설정 객체 (한 번만 로드): 전 모듈에서 CFG 로 임포트하여 사용
CFG = load_config()
