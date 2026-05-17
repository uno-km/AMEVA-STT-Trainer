# 📊 AMEVA-STT-Trainer: Domain-Specific Whisper Fine-tuning Pipeline

## 1. 개요 (Abstract)
본 프로젝트는 특정 도메인(경제/시사 콘텐츠)에 특화된 음성 인식(STT) 모델을 구축하기 위한 엔드투엔드 파이프라인이다. OpenAI의 Whisper 모델을 기반으로 하며, 데이터 수집의 자동화, 병렬 전처리 알고리즘, PEFT(LoRA)를 활용한 효율적 파인튜닝, 그리고 GGUF 포맷을 통한 최적화된 배포 과정을 포함한다. 

특히 Windows/Linux/macOS 환경 모두를 아우르는 **단일 통합 환경 구축 인터페이스(`setup.py` & `setup/` 격리)**, 품질 투명성과 감사 추적성을 극대화한 **다차원 설명성 검수 파이프라인(Explainability & Quality Audit)**, 그리고 **Whisper.cpp 연동 및 모델 양자화(Quantization)**를 패키징하여 최고 수준의 MLOps 신뢰성과 하드웨어 가용성을 확보하였다.

---

## 2. 주요 기술적 특징 (Technical Deep-Dive)

### 2.1. 데이터 획득 및 전처리 알고리즘 (Data Engineering & Signal Processing)
본 파이프라인은 비정형 스트리밍 데이터로부터 고품질 학습 코퍼스를 추출하기 위해 고도의 시그널 프로세싱 및 정교한 텍스트 가공 체계를 통합 구축하였다.
- **Suffix-Prefix Overlap Matching (접두사-접미사 중복 매칭 제거)**: 유튜브 자동생성 자막의 특성(실시간 단어 누적으로 인한 이전 자막과의 극심한 겹침)을 해결하기 위해, 공백을 제거한 텍스트 단위로 이전 꼬리(`last_tail`)와 새 텍스트 머리(`new_text`) 간의 접미사-접두사 일치 길이(Overlap Length)를 역추적한다. 오버랩된 중복 단어와 문맥을 온전하게 분리/제거하는 알고리즘을 도입하여 텍스트 데이터의 중복도를 $1\%$ 미만으로 억제한다.
- **Boundary-Aware Dynamic Chunking (문장 경계 감지 동적 청킹)**: Whisper 모델의 30초 오디오 인풋 윈도우 한계를 맞추면서도 문장이 발화 도중 잘려 문맥이 끊기는 현상을 방지한다. 자막 텍스트 내에서 한국어 문장 종결 어미("다", "요", "죠", "니", "까") 또는 구두점(`.`, `?`, `!`)을 감지하여, 15초 이상 30초 미만의 최적의 타임스탬프 시점에서 세그먼트를 동적으로 잘라내는 **Boundary protection** 메커니즘을 적용한다.
- **Robust Audio Resampling & Signal Processing**: `yt-dlp`를 통해 획득한 고화질 오디오 컨테이너를 타임라인과 완벽히 동조하여 밀리초(ms) 단위로 정밀하게 슬라이싱하고, 모든 청크 소스는 $f_s = 16,000\,Hz$ (Mono)로 강제 리샘플링하여 오디오 품질의 일관성을 강화한다.
- **Feature Extraction (Log-Mel Spectrogram)**: 연속적인 오디오 신호에 STFT(Short-Time Fourier Transform)를 적용하고, $N=80$ 채널의 Mel-filterbank를 거쳐 인간의 청각적 특성을 모델링한 Log-Mel Spectrogram 인풋 텐서로 변환하며, 이는 다음과 같은 수학식으로 표현된다:
  $$ S_{mel}(m) = \ln \left( \sum_{k=0}^{N-1} |X(k)|^2 \cdot H_m(k) \right) $$
  
  본 시스템에서는 `transformers.WhisperFeatureExtractor` 모듈을 격리 환경에서 호출하여 주파수를 80차원 오디오 Mel-Spectrogram 특징 벡터로 정밀 변환한다.
  
  ```python
  # [src/training/trainer.py:L110-L112] WhisperFeatureExtractor를 통한 오디오 특징 추출 실체
  input_features = feature_extractor(
      audio_array, sampling_rate=16000
  ).input_features[0]
  ```

- **Windows Optimized I/O (Streaming)**: Windows 환경에서의 대규모 오디오 로딩으로 인한 `WinError 87` (메모리 맵핑 한계) 에러를 원천 방지하기 위해 **IterableDataset** 방식을 도입하여 데이터 로딩 버퍼와 학습 파이프라인의 메모리 점유율을 실시간으로 수평 고정(Flatly Controlled)한다.

### 2.2. 모델 아키텍처 및 학습 전략 (Fine-Tuning Methodology)
본 프로젝트는 OpenAI의 **Whisper** 모델(Transformer 기반 Encoder-Decoder 구조)을 베이스로 하며, 효율적인 도메인 적응을 위해 PEFT 전략을 채택하였다.
- **LoRA (Low-Rank Adaptation) Theory**: 모델의 전체 파라미터 $W \in \mathbb{R}^{d \times k}$를 고정한 채, 저차원 행렬 $A$와 $B$의 곱으로 표현되는 업데이트 행렬 $\Delta W$만을 학습시킨다. 이는 다음과 같은 가중치 업데이트 식을 따른다:
  $$ W_{updated} = W_0 + \Delta W = W_0 + BA \quad (\text{where } B \in \mathbb{R}^{d \times r}, A \in \mathbb{R}^{r \times k}, r \ll d, k) $$
  이를 통해 학습 파라미터 수를 기존 대비 $1\%$ 미만으로 줄이면서도 도메인 특화 용어를 정밀하게 캡처한다.
  
  ```python
  # [src/models/whisper_lora.py:L54-L65] 베이스 모델에 LoRA 어댑터를 주입하는 실체 구현체
  lora_cfg = LoraConfig(
      r            = CFG["lora_r"],       # 저차원 랭크: 행렬 분해 차원 수
      lora_alpha   = CFG["lora_alpha"],   # 스케일링 인자: 업데이트 강도 조절
      target_modules = ["q_proj", "v_proj"],  # Whisper Attention 레이어
      lora_dropout = CFG["lora_dropout"], # 과적합 방지를 위한 드롭아웃 비율
      bias         = "none",              # 바이어스 파라미터는 학습하지 않음
  )
  # 베이스 모델에 LoRA 어댑터 주입 (베이스 가중치는 동결됨)
  model = get_peft_model(model, lora_cfg)
  ```

- **Hardware-Aware Training (Windows CPU)**: 
    - **Full Precision (FP32)**: CPU 환경에서 양자화 라이브러리의 불안정성을 피하기 위해 정밀도 손실이 없는 `torch.float32`를 채택한다.
    - **Stability Guard**: `use_cache=False` 및 `gradient_checkpointing=False` 설정을 통해 시스템 콜 충돌 및 메모리 오버헤드를 방지한다.
- **Loss Function**: 자동 음성 인식을 위해 Cross-Entropy Loss를 기반으로 하는 Sequence-to-Sequence 학습을 수행하며, Label Smoothing 기술을 적용하여 모델의 일반화 성능을 향상시켰다.

### 2.3. 양자화 및 배포 최적화 (Inference Optimization & Quantization)
학습된 LoRA 가중치는 베이스 모델과 병합(Merge)된 후, 최종적으로 `llama.cpp` 에코시스템과 호환되는 **GGUF** 포맷으로 변환되어 초고속 로컬 추론을 실현한다.
- **Cross-Platform Building**: 통합 실행기(`setup.py`) 구동 시, Windows는 동봉된 precompiled 양자화 유틸리티(`quantize.exe`, DLL 패키지)의 무결성을 검증하고, Linux/macOS(Darwin)는 로컬 아키텍처를 자동 진단하여 **Apple Silicon Metal 가속** 또는 **Linux OpenMP** 기반으로 `quantize` C++ 바이너리를 자동 즉시 컴파일(make)한다.
- **Quantization Logic (K-Quants)**: 부동 소수점(FP16/FP32) 가중치를 4-bit 혹은 8-bit 정수형으로 압축하는 양자화를 수행한다. 이때 Perplexity 손실을 최소화하기 위해 가중치 블록 단위로 스케일을 조정하는 비대칭 양자화(Asymmetric Quantization) 기법을 사용한다.
- **Static Graph Optimization**: 모델 내보내기 과정에서 추론에 불필요한 연산 노드를 제거하고 정적 그래프로 변환함으로써, CPU 환경에서의 연산 처리량(Throughput)을 극대화하였다.

### 2.4. 핵심 전처리 알고리즘 소스코드 및 실주소 명세 (Core Algorithms & Implementations)

#### 2.4.1. 접두사-접미사 중복 제거 알고리즘 (Suffix-Prefix Overlap Matching)
* **물리적 소스코드 주소**: [src/data/processor.py:L59-L96](file:///c:/ameva/AMEVA-STT-Trainer/src/data/processor.py#L59-L96)
* **설계 목적**: 실시간 누적 출력되는 VTT 자막의 겹침 텍스트를 기하학적으로 식별하여 완벽 차단하고, 순수 신규 단어 및 문맥 영역만 안전하게 발라낸다.

```python
def get_new_only(old_text: str, new_text: str) -> str:
    """
    old_text와 new_text 사이의 중복을 완벽히 제거하고, new_text에서 새롭게 추가된 고유 부분만 반환한다.
    유니코드 NFKC 호환성 정규화 및 최소 오버랩 기준(MIN_OVERLAP = 6)을 적용하여 기형적 과매칭을 철저하게 방지합니다.
    """
    import unicodedata
    def _norm(s):
        # NFKC 정규화로 전각 기호(％, ＄) 및 호환 문자까지 완벽 통일
        s = unicodedata.normalize('NFKC', str(s or ""))
        return "".join(c for c in s if c.isalnum()).lower()
        
    old_n = _norm(old_text)
    new_n = _norm(new_text)
    
    if not new_n: return ""
    
    # 접미사-접두사 오버랩 탐색 (과격한 포함 관계 컷을 배제하고 접미사 매칭을 정교하게 진행)
    match_len = 0
    for i in range(len(new_n), 0, -1):
        if old_n.endswith(new_n[:i]):
            match_len = i
            break
            
    # 최소 오버랩 길이 가드 (6글자 미만의 사소한 조사 겹침 등으로 인한 단어 잘림 방지)
    MIN_OVERLAP = 6
    if match_len < MIN_OVERLAP:
        return new_text
        
    # 원본 new_text에서 match_len만큼의 '유효 알파뉴머릭 문자'를 건너뛰고 남은 부분 정확히 반환
    matched_chars = 0
    for idx, char in enumerate(new_text):
        char_norm = unicodedata.normalize('NFKC', char)
        if char_norm.isalnum():
            matched_chars += 1
        if matched_chars == match_len:
            return new_text[idx+1:].strip()
            
    return ""
```

#### 2.4.2. 문장 경계 감지 동적 청킹 알고리즘 (Boundary-Aware Dynamic Chunking)
* **물리적 소스코드 주소**: [src/data/processor.py:L207-L233](file:///c:/ameva/AMEVA-STT-Trainer/src/data/processor.py#L207-L233)
* **설계 목적**: 발화 맥락이 임의의 30초 임계 시점에서 끊어지는 참사를 방지하고, 한국어 종결어미 형태소 및 무음 단락 가이드를 종합 분석해 인코더 경계를 동적 수호한다.

```python
# process_video 루프 내부 dynamic slice flush 판단 로직
duration = end_ms - cur_start_ms

# 겹침 보정 이전의 오리지널 타임스탬프로 정확한 캡션 스트림 침묵 갭(Silence Gap) 스캔
caption_gap_ms = cap["start_ms"] - cur_end_ms
is_silence_gap = caption_gap_ms > 1500

# 고도화된 한국어 종결 및 인용부호 닫힘 문맥 경계(Sentence Boundary) 감지 정규식
is_sentence_end = bool(re.search(r"(다|요|죠|니|까)[\.\?\!\s]*[\'\"\]\)]*$", cur_text.strip())) or cur_text.strip().endswith((".", "?", "!"))

# 복합 하이브리드 청킹 판단 트리거
# (A) Whisper 최대 인코더 윈도우 한계인 30초에 도달했을 때 (max_dur)
# (B) 10초 이상의 유효 발화가 채워진 상태에서 1.5초 이상의 대화 공백이 탐지되어 단락이 전환될 때
# (C) 15초 이상의 유효 발화가 채워진 상태에서 문장 종결 어미가 완성되어 문맥이 끊어지지 않게 마감될 때
should_flush = (
    duration > max_dur or 
    (duration > 10000 and is_silence_gap) or 
    (duration > 15000 and is_sentence_end)
)
```

#### 2.4.3. 구어체 연속 반복 및 중복 데이터 감사 (Adjacent Repetition & Row Duplication Audit)
* **물리적 소스코드 주소**: [src/data/validator.py:L150-L195](file:///c:/ameva/AMEVA-STT-Trainer/src/data/validator.py#L150-L195)
* **설계 목적**: 물리 데이터셋의 단순 로우 레벨 1:1 중복 검출 및 세그먼트 단어군 내부의 말더듬(Adjacent 1~3 gram repetition) 구어체 특성을 수식 분석해 데이터 다양성을 강제 진단한다.

```python
# 1. 데이터셋 전체 중복(Row-level duplicates) 확인
row_dups = int(clean_df.duplicated(subset=['transcription_clean']).sum())

# 2. 단일 청크 내 구어체 연속 반복(Adjacent Repetition) 패턴 검출 (1~3 gram)
stutter_count = 0
repetition_samples = []

for idx, row in clean_df.iterrows():
    text = str(row.get('transcription_clean', "")).strip()
    raw_text = str(row.get('transcription', "")).strip()
    words = [w for w in text.split() if w and re.match(r'^[a-zA-Z0-9가-힣]+$', w)]
    if len(words) >= 2:
        has_repeat = False
        repeated_pattern = None
        repeat_n = 0
        for n in (1, 2, 3):
            if len(words) >= n * 2:
                grams = [tuple(words[i:i+n]) for i in range(len(words)-n+1)]
                for i in range(len(grams) - n):
                    # 인접 n-gram이 정확히 반복 일치할 때
                    if grams[i] == grams[i+n]:
                        has_repeat = True
                        repeated_pattern = " ".join(grams[i])
                        repeat_n = n
                        break
            if has_repeat:
                break
```

---

## 3. 시스템 아키텍처 설계 (Software Architecture Design)

본 시스템은 유지보수성과 확장성을 위해 **Layered Architecture** 패턴을 채택하여 모듈 간 의존성을 최소화하고, 실행 스크립트와 인프라 셋업 도구의 관심사를 완벽히 분리하였다.

### 3.1. 모듈별 설계 의도
- **`src/core/` (Core Layer)**: 설정 관리(Config) 및 전역 예외 처리를 담당한다. 
  
  ```python
  # [src/core/config.py:L133-L154] YAML 설정을 안전하게 로드하고 단일 진실 공급원(CFG) 모듈 싱글톤 노출
  def load_config() -> dict:
      if not os.path.exists(CONFIG_PATH):
          return DEFAULTS.copy()

      with open(CONFIG_PATH, "r", encoding="utf-8") as f:
          user_cfg = yaml.safe_load(f) or {}

      cfg = DEFAULTS.copy()
      cfg.update(user_cfg)
      return cfg

  # 전역에서 설정 값 참조를 통합 제어하는 모듈 단위 싱글톤
  CFG = load_config()
  ```

- **`src/data/` (Data Processing Layer)**: 
    - `scraper.py`: 네트워크 I/O 비동기 처리를 고려한 영상 수집 모듈.
    - `processor.py`: 오디오 신호 처리, 자막 정렬 및 4대 파이프라인 계측 카운터 제어.
    - `validator.py`: 학습 전 데이터 무결성 검증, 물리 중복 전수 검사, 구어체 연속 반복 분석(Adjacent n-grams) 및 영구 품질 보고서(MD, JSON, CSV) 3종 세트 자동 생성.
- **`src/training/` (Training Layer)**: `transformers.Trainer`를 래핑하여 학습 프로세스를 제어한다. **Streaming Generator**를 통해 윈도우 메모리 이슈를 해결하며, 커스텀 콜백을 통해 실시간 대시보드와 연동된다.
- **`src/utils/` (Support Layer)**: 로깅, 시각화, 오디오 유틸리티 등 공통적으로 사용되는 유틸리티 함수군을 포함하며, 전역 예외 방어 메커니즘을 구동한다.
  
  ```python
  # [src/core/exceptions.py:L101-L128] 전역 예외 자동 로깅 및 안전한 복구용 Guard 데코레이터 실체
  def exception_guard(location: str = None, reraise: bool = False):
      def decorator(func):
          @functools.wraps(func)
          def wrapper(*args, **kwargs):
              loc = location or f"{func.__name__}()"
              try:
                  return func(*args, **kwargs)
              except Exception as e:
                  log_exception(e, loc)
                  if reraise:
                      raise
                  return None
          return wrapper
      return decorator
  ```

### 3.2. 디렉토리 구조 (Repository Layout)
```text
AMEVA-STT-Trainer/
├── setup.py            # [Root] 단일 통합 크로스플랫폼 셋업 진입점 (OS 자동 라우터)
├── setup/              # [NEW] 셋업 전용 독립 격리 폴더
│   ├── setup_env.ps1   # Windows PowerShell 용 셋업 스크립트
│   └── setup_env.sh    # Unix / Linux / macOS 용 Bash 셋업 스크립트
├── configs/            # 전역 하이퍼파라미터 (YAML)
├── src/                # 핵심 로직 (Engine)
│   ├── core/           # Exception Guard, Singleton Config
│   ├── data/           # Scraper, Processor, Validator (ETL + Audit Core)
│   ├── models/         # Model Loader, LoRA Configuration
│   ├── training/       # Seq2SeqTrainer, Custom Callbacks
│   └── utils/          # Dashboard Logger, Audio Utils
├── scripts/            # 실행 가능한 엔트리 포인트 (CLI - Cleaned)
│   ├── 01_build_dataset.py
│   ├── 02_start_training.py
│   ├── 03_export_model.py
│   └── export_gguf.py
├── dataset/            # 검증된 세그먼트 데이터 및 전수 품질 감사 보고서 보관소
├── models/             # 학습된 LoRA 가중치 및 병합된 모델 저장소
└── logs/               # 학습 중 발생하는 에러 및 트래킹 로그
```

---

## 4. 데이터 무결성 및 설명성 감사 체계 (Explainability & Quality Audit)

실무 MLOps 및 엔터프라이즈 데이터 엔지니어링 환경에서는 전처리 단계에서 유입되는 데이터 노이즈의 필터링 결과와 은밀한 시간 보정 이벤트를 블랙박스로 다루는 것이 허용되지 않는다. 본 파이프라인은 `src/data/processor.py` 및 `src/data/validator.py` 모듈을 중심으로 가동되는 실시간 전처리 계측 및 사후 3단계 다차원 정밀 감사 구조를 도입하여 데이터 투명성과 설명 추적성(Auditable Transparency)을 극대화하였다.

```mermaid
graph TD
    A[Raw Audio + Subtitles] --> B[Slicing & Subtitle Merging]
    B --> C{Real-Time Corrections}
    
    C -->|invalid end <= start| D[invalid_timestamp_skip]
    C -->|start < cur_end| E[overlap_clamp_count]
    C -->|post-clamp duration <= 0| F[post_clamp_skip]
    C -->|chunk duration < min_duration| G[too_short_chunk_drop]
    C -->|Standard Slicing & Trim| H[Audio Chunk Exported]
    
    H --> I[Post-Processor Validator]
    I --> J[Row-Level duplicates check on transcription_clean]
    I --> K[Adjacent n-gram repetitions audit for n in {1,2,3}]
    
    J --> L[Deduplication Audit Report]
    K --> L
    
    L --> M[audit_summary.json]
    L --> N[repetition_samples.csv]
    L --> O[validation_report.md]
```

### 4.1. 3단계 무결성 검증 프로토콜 (Integrity Protocols)
1. **물리적 무결성 스캔 (Physical Integrity Scan)**:
   - 디렉토리 내에 슬라이싱 생성된 모든 WAV 파일의 오디오 헤더 블록을 전수 파싱하여 RIFF 포맷 무결성을 확인한다.
   - 오디오 파일이 손상되었거나 인코딩 오류, 혹은 파일 전송/디스크 쓰기 실패로 인해 $0\,Byte$ 파일이 생성되어 훈련 파이프라인 구동 시 예외(Crash)를 유발하는 불량 데이터셋 요소를 사전 감지하여 영구 제거한다.
2. **논리적 정제 정합성 (Logical Clean Verification)**:
   - 전사 텍스트(Transcription) 데이터 내에 불필요한 마크다운 기호, 한글 자모 단독 분리 오류, 더블 스페이스, 무음 구간 전사 마커 등을 정밀 텍스트 정규화 필터로 전수 필터링한다.
   - 무음 매칭 결과로 인해 빈 전사 문자열(Null) 또는 발화가 존재하지 않는 무음 슬라이스가 학습 데이터셋에 편입되어 모델 가중치 분산 에러를 유발하는 문제를 사전 차단한다.
3. **정렬 및 시간 스펙 정합성 (Temporal Specification Alignment)**:
   - Whisper 인코더의 30초 컨텍스트 제한을 기하학적으로 초과하는 오버헤드 청크를 전수 조사하여 클램핑한다.
   - 정제 및 트리밍 과정을 마친 순수 오디오 발화 구간이 최소 물리 규격인 $3,000\,ms$ (3초) 미만인 레코드를 자동 배제함으로써 데이터셋의 정보 밀도를 유지한다.

### 4.2. 실시간 파이프라인 계측 카운터 (Pipeline Event Counters)
데이터셋 청킹 및 보정이 실시간으로 가동되는 도중, 메모리 레벨에서 카운터 구조인 `PIPELINE_COUNTERS`를 통해 발생하는 이벤트를 실시간으로 누적 수치로 가시화한다:
* **`invalid_timestamp_skip`**: WebVTT 등 소스 자막 타임스탬프 규격에 심각한 오류가 존재하여 자막 종료 지점이 시작 지점보다 과거이거나 동일하여 발생한 무효 스킵 수.
* **`overlap_clamp_count`**: 연속되는 오디오 구간에서 자막 타임라인 간의 겹침 현상(Overlap)이 감지되어, 선행 자막의 종료점을 기반으로 후행 자막의 시작점을 밀어서 음향 시간 정합성을 강제 맞춤한 보정 횟수.
* **`post_clamp_skip`**: 중첩 보정을 거치는 과정에서 두 자막 간의 겹침 밀도가 비정상적으로 높아 보정 후 세그먼트 시간 길이가 $0$초 이하로 줄어들어 데이터 가치가 소멸된 스킵 건수.
* **`too_short_chunk_drop`**: 물리 전사 슬라이싱 가공을 정상 완료하였으나 최종 오디오 신호의 유효 발화가 $3,000\,ms$ 스펙 제한에 도달하지 못해 기각 처리한 청크 수.

### 4.3. 다차원 정량적 사후 감사 (Post-Processing Audit)
1. **물리 레코드 중복 감사 (Row-Level Deduplication Audit)**:
   - 문장 정규화 및 필터링(`[0-9A-Za-z가-힣]+`)을 통과한 `transcription_clean` 텍스트 간의 1:1 전수 비교(Exact-Match) 연산을 수행한다.
   - 데이터셋 적재 단계에서의 물리적인 로우 레벨 중복 적재도(Row-Level Duplicity)를 완벽 검출하여 학습 데이터셋 내의 중복 편향(Overfitting bias)을 억제하며, 중복이 검출될 경우 MLOps 감사 보고서에 상위 5개 중복 증거를 즉각 박제한다.
2. **구어체 연속 반복 상세 지표화 (Adjacent Repetition Index, INFO-only)**:
   - 발화자의 고유 특성, 말더듬 현상, 단어의 연속 중복 등장 빈도를 측정하기 위해 고안된 유니크 분석 엔진이다.
   - 단일 세그먼트 내부에서 인접하게 중복 등장하는 단어 또는 단어구(Adjacent repeated n-grams for $n \in \{1, 2, 3\}$)를 정밀 추적하여 검출 빈도를 지표화한다. 이는 학습 가중치가 특정 어휘에 매몰되는 위험을 사전에 모니터링한다.
3. **무작위 5-세그먼트 정합성 프로파일링 (Random Verification)**:
   - 전수 조사가 마무리된 직후, 무작위로 5개의 물리 청크를 강제 샘플링하여 파일명, 재생시간(sec), 문자 밀도(Characters Per Second, CPS), 데시벨 음향 에너지(dBFS), 원문 텍스트 Snippet을 그대로 박제한다. 이를 통해 엔지니어 및 리뷰어가 전처리 통계의 실효성을 즉각 육안으로 확인할 수 있다.

### 4.4. 영구 MLOps 품질 보고서 3종 세트 (Permanent Artifacts)
가공 및 검수가 완료되는 즉시 각 태스크별 고유 샌드박스 경로(`dataset/<task_name>/`)에 다음 3가지 영구 아티팩트가 생성된다:
* **`validation_report.md`**: 전사 무결성 판정 그리드, 분위수 분포(p50, p90, p99 등) 오디오 통계, 4대 실시간 계측 카운터, 로우 중복 감사 증거, 구어체 연속 반복 및 무작위 샘플 프로필을 모두 아우르는 **프리미엄 설명성 리포트**.
* **`audit_summary.json`**: MLOps 자동화 대시보드와 파이프라인 연동을 위해 통계치와 카운터 데이터를 머신러닝 분석 규격으로 정제하여 저장한 JSON 프로파일링 요약서.
* **`repetition_samples.csv`**: 발화 반복이 일어난 전체 리포트의 세그먼트 파일명, 감지된 반복 패턴, n-gram 종류, 원문 자막을 영구 보존하는 감사용 레지스트리 원장.

---

## 5. 설치 및 파이프라인 가이드 (Execution Pipeline)

본 프로젝트는 복잡한 멀티미디어 처리와 딥러닝 가상 환경의 완벽한 재현을 도모하고 인프라 구성 상의 불일치를 해결하기 위해 혁신적인 단일 통합 설치 전략 및 상세 운영 가이드를 제공한다.

### 5.1. 인프라 구축 및 의존성 관리 전략 (Infrastructure Setup Strategy)

#### 5.1.1. 가상환경 및 단일 통합 셋업 실행기 (Unified setup.py Launcher)
Windows 환경의 파이썬 패키지 버전 충돌 및 Unix 아키텍처의 C++ 빌드 충돌을 근원적으로 방지하기 위해 **최상위 루트 단일 통합 실행기(`setup.py`)** 및 **`setup/` 격리 아키텍처**를 구축하였다.

```bash
# 운영체제가 Windows이든 macOS이든 Linux이든 상관없이, 루트 폴더에서 다음 단 한 줄만 터미널에 입력하십시오.
python setup.py
```

* **OS별 내부 작동 메커니즘 (setup/):**
  - **`setup/setup_env.ps1` (Windows)**:
    1. 최상위 루트 디렉토리에 로컬 가상환경(`venv`) 생성 및 시스템 pip 업그레이드를 실행한다.
    2. `requirements.txt`에 명세된 핵심 딥러닝 패키지를 Windows 가용성에 특화시켜 정밀 설치한다.
    3. `third_party/whisper.cpp` 내부의 precompiled Windows 전용 양자화 바이너리(`quantize.exe`, `SDL2.dll`, `ggml.dll`, `whisper.dll` 등)의 물리 존재 여부 및 경로 정합성을 실시간 유효성 검사한다.
  - **`setup/setup_env.sh` (Unix/Linux/macOS)**:
    1. 호스트 시스템 내 Python3 및 venv 환경을 점검하고, 독립 가상환경 생성 및 활성화를 구동한다.
    2. `requirements.txt` 전수 의존성 명세를 완벽히 자동 설치 완료한다.
    3. `third_party/whisper.cpp` 저장소를 Clone하고 `uname -s`로 호스트 하드웨어를 진단한다.
    4. **macOS (Darwin)** 일 경우 Apple Silicon의 **Metal(MPS) GPU 가속**이 활성화되도록 C++ Makefile 컴파일을 백그라운드 구동한다.
    5. **Linux** 일 경우 **OpenMP** 멀티스레드 가속 빌드를 가동하여 하드웨어 성능을 최대로 쥐어짜는 `quantize` C++ 바이너리를 현장 컴파일(`make`) 완성한다.

* **`requirements.txt` 의존성 패키지 역할 및 기술 규격:**
  - **딥러닝 엔진 (Core AI Stack)**:
    * `torch` & `torchaudio`: PyTorch 가상환경 연산 백엔드. Windows CPU FP32 및 GPU CUDA 연산 그래프 제어.
    * `transformers`: 사전 학습된 Whisper Encoder-Decoder 트랜스포머 아키텍처 및 Sequence-to-Sequence 제어.
    * `peft (LoRA)`: 저차원 행렬 분해 가중치 가산 및 어댑터 로더.
    * `datasets`: **IterableDataset** 아키텍처를 가동하여 로컬 오디오 텐서를 실시간 스트리밍화.
    * `evaluate` & `jiwer`: 편집 거리 기반의 표준 WER / CER 과학적 검증 백엔드.
  - **시그널 및 데이터 엔지니어링 (Data Engineering Stack)**:
    * `yt-dlp` & `webvtt-py`: 웹 데이터 수집, 비동기 VTT 자막 다운로드 및 파싱 스트리밍.
    * `pydub` & `librosa` & `soundfile` & `scipy`: 시계열 WAV 오디오 로드, 리샘플링, 트리밍, 데시벨 프로파일링.
    * `pandas` & `pyyaml` & `tqdm`: 메타데이터 데이터 프레임 관리, 설정 파일 로드, 실시간 처리 프로그레스바 관리.
  - **원격 제어 및 텔레메트리 (Telemetry Stack)**:
    * `rich` & `psutil`: 터미널 GUI 시각화 및 시스템 자원 모니터링.
    * `wandb` & `win10toast`: 학습 통계 클라우드 트래킹 및 Windows 알림 토스트 가동.
    * `PyQt6` & `python-docx` & `matplotlib`: 품질 보고서 생성 및 시각화 도구 차트 렌더링.

#### 5.1.2. 시스템 레벨: 외부 바이너리 격리 관리 (Isolated FFmpeg)
운영체제의 환경 변수(`PATH`) 오염으로 인한 바이너리 버전 충돌을 원천 차단하기 위해 **격리 격벽 전략**을 구현한다.
1. **격리 프로비저닝**: `scripts/install_ffmpeg.ps1`을 가동하여 검증된 FFmpeg 정적 바이너리를 `C:\ffmpeg\bin`에 고립식으로 영구 안착시킨다.
2. **정적 절대 경로 바인딩**: 시스템 전역 환경 변수를 건드려 타 프로세스를 방해하지 않고, 파이프라인의 오디오 커팅 및 리샘플링 실행 시 이 격리된 절대 경로에서 FFmpeg 바이너리를 직접 지정/참조하여 무결성을 달성한다.

---

### 5.2. 운영 프로세스 상세 명세 (Operational Workflow Deep-Dive)

본 파이프라인은 데이터의 생성부터 최종 배포용 최적 양자화 모델 추출까지 전 과정을 CLI 도구로 제어한다.

#### 1단계: 설명성 데이터셋 구축 및 품질 검수 (`scripts/01_build_dataset.py`)
이 단계는 로컬 원본 경로 또는 유튜브 등 비정형 소스로부터 완벽히 정제된 고품질의 WAV 청크 데이터셋을 구축하고 품질 설명 아티팩트를 저장하는 MLOps ETL 단계이다.
* **주요 핵심 메커니즘:**
  - **Task Sandbox Isolation**: `--name <task_name>` 파라미터를 입력받아 `dataset/<task_name>` 디렉토리를 물리적 샌드박스로 확보하여 독립된 WAV 청크 및 메타데이터를 유지하므로 멀티 태스크 학습 데이터 혼입을 막는다.
  - **Suffix-Prefix Overlap Matching**: 공백을 제거한 자막 텍스트 단위로 이전 꼬리와 새 머리 간의 오버랩 일치 길이(Overlap Length)를 파악해 겹침 단어를 제거한다.
  - **Boundary-Aware Dynamic Chunking**: 문장 종결 어미 기준 문맥이 파괴되지 않도록 15~30초 동적 슬라이싱을 수행하며, 모든 청크는 $16,000\,Hz$ Mono 포맷으로 리샘플링된다.
  - **Audit Artifact Auto-Writing**: 데이터셋 구축 프로세스가 완료되면 MLOps 감사 파일 3종(`validation_report.md`, `audit_summary.json`, `repetition_samples.csv`)을 해당 샌드박스에 즉시 배포 보존한다.
* **실행 커맨드 예시:**
  ```powershell
  # 로컬 오디오 폴더 모드로 태스크 test_run_verify 구동 및 검수 아티팩트 자동 추출
  python scripts/01_build_dataset.py --folder dataset/2026/05/17 --name test_run_verify
  ```

#### 2단계: 안정성 최우선 LoRA 파인튜닝 (`scripts/02_start_training.py`)
베이스 Whisper 모델 가중치에 타깃 도메인 시사/경제 어휘 지식을 저차원 가중치로 가산 및 파인튜닝하는 안정성 강화 학습 단계이다.
* **주요 핵심 메커니즘:**
  - **IterableDataset Flat-Memory Stream**: 텐서 데이터를 메모리에 올리지 않고 필요할 때 실시간 스트리밍 로딩하여 Windows `WinError 87` 메모리 맵 한계 에러를 근본 차단한다.
  - **Pickle-Free Shielding**: 가상환경 멀티프로세싱 시 빈번하게 발생하는 직렬화 크래시(`Pickle Error`)를 완벽히 막기 위해, 데이터 제너레이터 객체와 모니터링 객체(Logger)의 생명주기를 메모리 레벨에서 독립 분리 구동한다.
  - **W&B & Checkpoint Recovery**: Rich 대시보드로 시스템 자원을 추적하는 동시에 W&B 클라우드로 학습 메트릭을 실시간 트래킹하며, `resume_from_checkpoint`를 통해 학습 영속성을 보장한다.
* **실행 커맨드 예시:**
  ```powershell
  python scripts/02_start_training.py --task-id task_0001
  ```

#### 3단계: 정량적 성능 평가 (`scripts/eval.py`)
학습이 끝난 모델의 실제 언어적 음성 인식 정확도를 Levenshtein Distance 수식 기반으로 검증하는 품질 진단 단계이다.
* **주요 핵심 메커니즘:**
  - **WER / CER 과학적 계측**: 평가 셋을 Whisper 생성 파이프라인에 투입하여 추론 텍스트를 생성하고, 레이블 정답과 비교하여 편집 거리 오차율(WER, CER)을 수학적으로 산출한다.
    $$ \text{CER} = \frac{\text{Substitution} + \text{Deletion} + \text{Insertion}}{\text{Reference Length}} $$
  - **Hold-out Target Set Evaluation**: 학습 데이터셋과 완전 차단된 10%의 홀드아웃 타깃 셋으로 객관적인 오버피팅 여부를 확인한다.
* **실행 커맨드 예시:**
  ```powershell
  python scripts/eval.py
  ```

#### 4단계: 모델 병합 및 배포 최적화 (`scripts/03_export_model.py` & `scripts/export_gguf.py`)
분리되어 학습된 LoRA 어댑터 가중치를 원본 Whisper 모델 본체와 일체화하고 C++ 초고속 추론 환경을 위해 GGUF 변환을 수행하는 배포 최적화 단계이다.
* **주요 핵심 메커니즘:**
  - **Weights Merger**: `merge_and_unload()` 메서드를 통해 원본 가중치 가속 매트릭스에 LoRA 행렬 가중치를 수학적으로 완전히 결합한 단일 HuggingFace 포맷 모델을 출력한다.
  - **K-Quantization Layout (Whisper.cpp)**: 병합 완료 모델을 GGUF 도구로 패킹해 기본 binary 형식(`ggml-model.bin`)을 구축하고, `setup.py` 시점에 자동 현장 컴파일 완료된 `quantize` C++ 바이너리 유틸리티를 호출해 K-Quant 4비트/8비트 고밀도 양자화를 가동하여 CPU 연산 성능을 극대화한다.
* **실행 커맨드 예시:**
  ```powershell
  # 1. 모델 가중치 병합 및 HuggingFace 포맷 최종 저장
  python scripts/03_export_model.py
  
  # 2. GGUF 변환 및 컴파일된 양자화 명령어 매뉴얼 출력
  python scripts/export_gguf.py
  ```
  *(GGML 가이드라인에 따라 모델 변환 바이너리가 생성되면 OS 사양에 맞게 컴파일된 양자화 도구를 호출한다)*
  ```bash
  # Windows OS 환경
  .\third_party\whisper.cpp\quantize.exe ggml-model.bin ggml-model-q4_0.bin q4_0
  
  # Linux/macOS Environment (setup.py에서 CPU OpenMP / Metal MPS 가속 사양으로 자동 현장 컴파일 완료된 바이너리 참조)
  ./third_party/whisper.cpp/quantize ggml-model.bin ggml-model-q4_0.bin q4_0
  ```

---

## 6. 실험 로드맵 및 검증 전략 (Experimental Roadmap & Methodology)

본 파이프라인의 궁극적인 존재 가치는 단순 학습의 자동화를 넘어, 오디오 데이터의 **전처리 정밀도(Chunking Level)**와 모델의 수용 용량(Model Size) 간의 시너지 임계점을 실험을 통해 과학적으로 규명하는 데 있다.

### 6.1. 실험 설계 원칙 (Design of Experiments)
학습 파라미터(Learning Rate, Batch Size, Optimizer)의 정적 제어를 원칙으로 삼으며, 오직 독립 변수로서 **"오디오 청킹 레벨(Lv.1 ~ Lv.3)"**과 **"모델 뼈대(Tiny, Small, Large-v3)"**만을 변형하여 목적 함수인 $\min(\text{WER}, \text{CER})$를 추구한다.
- **평가 셋**: 슈카월드 특정 에피소드에서 무작위 추출된 10%의 홀드아웃(Hold-out) 데이터셋 활용.

### 6.2. 실험 단계별 가설 및 목표 (Phased Hypotheses)

1. **Phase 1 (Baseline Exploration)**:
   - **가설**: 가장 단순한 전처리 데이터만으로도 파이프라인의 전체 입출력 무결성이 검증될 것이며, 연산 비용이 가장 낮은 베이스 성능(Baseline)을 제시할 것이다.
   - **목표**: `Tiny` 모델 및 시간 기반 단순 25초 고정 절단(Lv.1) 조합의 기본 WER/CER 수치 획득.
2. **Phase 1-1 (Temporal Optimization)**:
   - **가설**: 25초 고정 절단 대신 자막 문맥 경계를 보존하는 스마트 청킹(Lv.2)을 적용하면, 동일한 `Tiny` 모델에서 음절 탈락 현상이 현저히 감소하여 CER이 크게 개선될 것이다.
   - **목표**: `Boundary Protection` 전처리가 디코더 예측 정확도에 미치는 단독 파급 지표 측정.
3. **Phase 2 (Data Quality vs. Model Scale)**:
   - **가설**: 모델 크기를 `Small`로 스케일업할 시, 기존 `Tiny` baseline 데이터셋 대비 전사 텍스트의 언어적 완결성 및 구조 이해도가 향상될 것이다.
   - **목표**: 모델 스펙 변화에 따른 기본적인 도메인 어휘 복원력 증가 추이 확인.
4. **Phase 2-1 (Semantic Alignment)**:
   - **가설**: `Small` 모델에 Lv.2 스마트 청킹 데이터를 주입하면, 언어 인풋 윈도우의 문맥 보호 효과가 극대화되어 시너지 효과(WER 감소 속도 가속화)가 발생할 것이다.
   - **목표**: 모델 용량과 전처리 지능 간의 복합 시너지 작용 정량 평가.
5. **Phase 3 (Optimization Synergy)**:
   - **가설**: `Small` 모델에 최고 등급 하이브리드 전처리(Lv.3 - Skilled) 데이터를 융합할 경우, 경제 및 금융 시사의 고난이도 복합 명사 및 외래어 발화 구간의 인식 성공률이 baseline 대비 비약적인 성장을 이룩할 것이다.
   - **목표**: Suffix-Prefix Matching 및 무음 가이드 정렬을 결합한 데이터셋 가치가 미치는 프로덕션급 성능 증명.
6. **Phase 4 (SOTA Implementation)**:
   - **가설**: 현존 최고 아키텍처인 `Large-v3` 베이스 모델과 고정밀 Lv.3 전처리 LoRA 어댑터의 시너지 융합이 극한의 한계 인식 능력을 구현하여 완벽한 도메인 특화 STT 엔진을 완성할 것이다.
   - **목표**: 최종 배포용 최적 모델 확정 및 비대칭 양자화를 통한 임베디드 성능의 극대화.

### 6.3. 실험 진행 상황 (Experiment Tracker)

| 완료 | 페이즈 | 모델 | 전처리 스킬 | 현재 상태 | WER/CER | 소요 시간 |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| [/] | **Phase 1** | `tiny` | Lv.1 (25s 고정) | `Ready to Start` | - / - | - |
| [ ] | **Phase 1-1**| `tiny` | Lv.2 (15s 스마트) | `Scheduled` | - / - | - |
| [ ] | **Phase 2** | `small`| Lv.1 (25s 고정) | `Scheduled` | - / - | - |
| [ ] | **Phase 2-1**| `small`| Lv.2 (15s 스마트) | `Scheduled` | - / - | - |
| [ ] | **Phase 3** | `small`| **Lv.3 (Skilled)** | `Waiting` | - / - | - |
| [ ] | **Phase 4** | **Large-v3**| **Lv.3 (Skilled)** | `Final Boss` | - / - | - |

### 6.4. 전처리(Chunking) 레벨의 정밀 정의
* **Lv.1 (Basic) - Time-based Accumulation**:
  - **전략**: 자막 스트림의 타임스탬프를 맹목적으로 누적 계산하여 약 25초 간격으로 단순 산술 절단한다.
  - **특징**: 단순하여 I/O 비용이 낮으나, 문장 또는 어휘의 한복판이 잘려 디코더 가중치 업데이트 시 모델의 문맥 엔트로피 Loss 왜곡을 유발하기 쉽다.
* **Lv.2 (Smart) - Boundary Protection**:
  - **전략**: 문장의 실제 종결 지점("다", "요", "죠")을 감지하여 발화의 맥락 단락을 안전하게 유지하고, 15~30초 범위 안에서 유동적으로 음성 세그먼트 경계를 정한다.
  - **특징**: 오디오-자막 경계의 문맥적 흐름을 유지하므로, 모델 디코더의 Autoregressive 문맥 예측율을 증폭시킨다.
* **Lv.3 (Skilled) - Hybrid Precision Alignment**:
  - **전략**: Boundary Protection(Lv.2)에 Suffix-Prefix Matching(접두-접미사 중복 제거)을 가동하고, 오디오 웨이브폼 무음구간 가이드를 융합하여 데이터와 자막을 정렬한다.
  - **특징**: 오버랩 중복 발화를 완전히 소거하여 훈련 데이터를 최고 수준으로 농축하며, 고난이도 도메인 지식 파인튜닝 시 SOTA 수준의 정확도를 획득한다.

---
**Note**: 본 시스템은 CPU 환경에서도 안정적으로 동작하도록 설계되었으나, 학습 효율을 위해 최신 NVIDIA GPU 환경(CUDA) 사용을 권장한다.

---
> **"데이터가 장인정신을 만나면, 인공지능은 예술이 된다."** - AMEVA STT Project
