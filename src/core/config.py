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

# 학습 데이터 세그먼트(WAV·CSV)가 저장될 최상위 디렉터리
DATASET_DIR     = os.path.join(ROOT_DIR, "dataset")
# 전체 오디오-전사 쌍 목록을 담은 CSV 파일 경로
METADATA_PATH   = os.path.join(DATASET_DIR, "metadata.csv")
# 학습 결과(어댑터·병합 모델)가 저장될 디렉터리
OUTPUTS_DIR     = os.path.join(ROOT_DIR, "outputs")
# LoRA 어댑터 가중치 저장 경로
LORA_DIR        = os.path.join(OUTPUTS_DIR, "lora_adapter")
# LoRA 병합 완료 모델 저장 경로
MERGED_DIR      = os.path.join(OUTPUTS_DIR, "merged_model")
# 실행 로그 및 에러 로그가 저장될 디렉터리
LOG_DIR         = os.path.join(ROOT_DIR, "logs")

# GGUF 모델 저장 경로 (외부 공통 저장소)
GGUF_DIR        = r"C:\ameva\AI_Models\ggml"

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
    "learning_rate"          : 1e-3,         # LoRA 어댑터 학습률
    "max_steps"              : 1000,         # 전체 학습 스텝 수
    "save_steps"             : 50,           # 체크포인트 저장 주기
    "logging_steps"          : 10,           # 로그 출력 주기
    "warmup_steps"           : 50,           # 학습률 워밍업 스텝 수
    "lora_r"                 : 32,           # LoRA 저차원 랭크(r)
    "lora_alpha"             : 64,           # LoRA 스케일링 인자(α)
    "lora_dropout"           : 0.05,         # LoRA 드롭아웃 비율

    # 평가
    "eval_samples"           : 50,           # 평가 시 무작위 추출 샘플 수
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
