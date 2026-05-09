# AMEVA-STT-Trainer: Domain-Specific Whisper Fine-tuning Pipeline

## 1. 개요 (Abstract)
본 프로젝트는 특정 도메인(경제/시사 콘텐츠)에 특화된 음성 인식(STT) 모델을 구축하기 위한 엔드투엔드 파이프라인이다. OpenAI의 Whisper 모델을 기반으로 하며, 데이터 수집의 자동화, 병렬 전처리 알고리즘, PEFT(LoRA)를 활용한 효율적 파인튜닝, 그리고 GGUF 포맷을 통한 최적화된 배포 과정을 포함한다. 특히 Windows 환경의 시스템 제약을 극복하고 학습의 안정성을 확보하기 위해 스트리밍 데이터 로딩(IterableDataset) 및 FP32 정밀도 최적화 설계를 적용하여 하드웨어 가용성을 극대화하였다.

## 2. 주요 기술적 특징 (Technical Deep-Dive)

### 2.1. 데이터 획득 및 전처리 알고리즘 (Data Engineering & Signal Processing)
본 파이프라인은 비정형 스트리밍 데이터로부터 고품질 학습 코퍼스를 추출하기 위해 다단계 시그널 프로세싱 체계를 구축하였다.
- **Robust VTT Synchronization**: `yt-dlp` 엔진을 통해 추출된 WebVTT 자막 데이터와 오디오 신호 사이의 정렬(Alignment) 무결성을 확보한다. 자막의 시작($T_{start}$)과 종료($T_{end}$) 시간을 기준으로 오디오 세그먼트를 슬라이싱하며, 모든 소스는 $f_s = 16,000\,Hz$ (Mono)로 강제 리샘플링된다.
- **Feature Extraction (Log-Mel Spectrogram)**: Whisper 모델의 인풋 텐서로 변환하기 위해, 연속적인 오디오 신호에 STFT(Short-Time Fourier Transform)를 적용한다. 이후 $N=80$ 채널의 Mel-filterbank를 통과시켜 인간의 청각 특성을 반영한 Log-Mel Spectrogram을 생성하며, 이는 다음과 같은 수식으로 정의된다:
  $$ S_{mel}(m) = \ln \left( \sum_{k=0}^{N-1} |X(k)|^2 \cdot H_m(k) \right) $$
- **Windows Optimized I/O (Streaming)**: 윈도우의 메모리 맵핑 제한으로 인한 `WinError 87`을 방지하기 위해 **IterableDataset** 방식을 채택, 데이터 전처리와 학습을 파이프라인화하여 메모리 점유율을 일정하게 유지한다.

### 2.2. 모델 아키텍처 및 학습 전략 (Fine-Tuning Methodology)
본 프로젝트는 OpenAI의 **Whisper** 모델(Transformer 기반 Encoder-Decoder 구조)을 베이스로 하며, 효율적인 도메인 적응을 위해 PEFT 전략을 채택하였다.
- **LoRA (Low-Rank Adaptation) Theory**: 모델의 전체 파라미터 $W \in \mathbb{R}^{d \times k}$를 고정한 채, 저차원 행렬 $A$와 $B$의 곱으로 표현되는 업데이트 행렬 $\Delta W$만을 학습시킨다. 이는 다음과 같은 가중치 업데이트 식을 따른다:
  $$ W_{updated} = W_0 + \Delta W = W_0 + BA \quad (\text{where } B \in \mathbb{R}^{d \times r}, A \in \mathbb{R}^{r \times k}, r \ll d, k) $$
  이를 통해 학습 파라미터 수를 기존 대비 $1\%$ 미만으로 줄이면서도 도메인 특화 용어를 정밀하게 캡처한다.
- **Hardware-Aware Training (Windows CPU)**: 
    - **Full Precision (FP32)**: CPU 환경에서 양자화 라이브러리의 불안정성을 피하기 위해 정밀도 손실이 없는 `torch.float32`를 채택한다.
    - **Stability Guard**: `use_cache=False` 및 `gradient_checkpointing=False` 설정을 통해 시스템 콜 충돌 및 메모리 오버헤드를 방지한다.
- **Loss Function**: 자동 음성 인식을 위해 Cross-Entropy Loss를 기반으로 하는 Sequence-to-Sequence 학습을 수행하며, Label Smoothing 기술을 적용하여 모델의 일반화 성능을 향상시켰다.

### 2.3. 양자화 및 배포 최적화 (Inference Optimization)
학습된 LoRA 가중치는 베이스 모델과 병합(Merge)된 후, 최종적으로 `llama.cpp` 에코시스템과 호환되는 **GGUF** 포맷으로 변환된다.
- **Quantization Logic (K-Quants)**: 부동 소수점(FP16/FP32) 가중치를 4-bit 혹은 8-bit 정수형으로 압축하는 양자화를 수행한다. 이때 Perplexity 손실을 최소화하기 위해 가중치 블록 단위로 스케일을 조정하는 비대칭 양자화(Asymmetric Quantization) 기법을 사용한다.
- **Static Graph Optimization**: 모델 내보내기 과정에서 추론에 불필요한 연산 노드를 제거하고 정적 그래프로 변환함으로써, CPU 환경에서의 연산 처리량(Throughput)을 극대화하였다.

## 3. 시스템 아키텍처 설계 (Software Architecture Design)

본 시스템은 유지보수성과 확장성을 위해 **Layered Architecture** 패턴을 채택하여 모듈 간 의존성을 최소화하였다.

### 3.1. 모듈별 설계 의도
- **`src/core/` (Core Layer)**: 설정 관리(Config) 및 전역 예외 처리를 담당한다. 싱글톤 패턴을 활용하여 애플리케이션 전반에 걸쳐 동일한 파라미터가 공유되도록 설계하였다.
- **`src/data/` (Data Processing Layer)**: 
    - `scraper.py`: 네트워크 I/O 비동기 처리를 고려한 영상 수집 모듈.
    - `processor.py`: 오디오 신호 처리 및 텍스트 정렬을 담당한다. (Dataset 구축 시 병렬 연산 활용)
    - `validator.py`: 학습 전 데이터 무결성을 검증하는 게이트웨이 역할을 수행한다.
- **`src/training/` (Training Layer)**: `transformers.Trainer`를 래핑하여 학습 프로세스를 제어한다. **Streaming Generator**를 통해 윈도우 메모리 이슈를 해결하며, 커스텀 콜백을 통해 실시간 대시보드와 연동된다.
- **`src/utils/` (Support Layer)**: 로깅, 시각화, 오디오 유틸리티 등 공통적으로 사용되는 유틸리티 함수군을 포함한다.

### 3.2. 디렉토리 구조 (Repository Layout)
```text
AMEVA-STT-Trainer/
├── configs/            # 전역 하이퍼파라미터 (YAML)
├── src/                # 핵심 로직 (Engine)
│   ├── core/           # Exception Guard, Singleton Config
│   ├── data/           # Scraper, Processor, Validator (ETL)
│   ├── models/         # Model Loader, LoRA Configuration
│   ├── training/       # Seq2SeqTrainer, Custom Callbacks
│   └── utils/          # Dashboard Logger, Audio Utils
├── scripts/            # 실행 가능한 엔트리 포인트 (CLI)
├── dataset/            # 검증된 세그먼트 데이터 (WAV/CSV)
├── models/             # 학습된 LoRA 가중치 및 병합된 모델 저장소
└── logs/               # 학습 중 발생하는 에러 및 트래킹 로그
```

## 4. 데이터 무결성 및 장애 복구 체계 (Reliability & Resilience)

실무 환경에서의 데이터 오염 및 크래시 상황에 대비하여 다음과 같은 안전장치를 구현하였다.

### 4.1. 3단계 무결성 검증 프로토콜
학습 데이터셋의 노이즈를 제거하기 위해 `src/data/validator.py`를 통한 단계별 검수를 수행한다.
1. **정적 검수(Physical)**: 오디오 파일의 헤더 정보 파싱 및 파손된 파일 자동 제거.
2. **논리 검수(Logical)**: 자막 텍스트의 특수문자 정제 및 빈 문자열(Null) 레코드 필터링.
3. **정렬 검수(Alignment)**: Whisper의 30초 윈도우를 초과하는 청크를 감지하여 유효성 확보.

### 4.2. 전역 예외 가드 (Global Exception Guard)
- 모든 주요 파이프라인은 `src/core/exceptions.py`에 정의된 데코레이터를 통해 실행된다.
- 예외 발생 시 스택 트레이스를 `logs/error_log.md`에 상세히 기록하고, 해당 시점의 시스템 상태를 스냅샷으로 남긴다.
- `resume_from_checkpoint` 설정을 통해 하드웨어 장애나 프로세스 강제 종료 시에도 마지막 학습 시점부터 즉시 재개가 가능하다.

## 5. 설치 및 파이프라인 가이드 (Execution Pipeline)

### 5.1. 인프라 구축 및 의존성 관리 전략 (Infrastructure Setup Strategy)

본 프로젝트는 복잡한 멀티미디어 처리와 딥러닝 환경의 재현성을 보장하기 위해 시스템 레벨과 애플리케이션 레벨의 의존성을 이원화하여 관리한다.

#### 5.1.1. 가상환경 및 의존성 관리 (Windows Virtual Environment)
Windows 환경의 라이브러리 충돌을 방지하기 위해 반드시 독립된 가상환경(`venv`) 사용을 권장한다.
```powershell
# 1. 가상환경 생성 및 활성화
python -m venv venv
.\venv\Scripts\activate

# 2. 핵심 라이브러리 설치 (Windows CPU 안정화 버전)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

#### 5.1.2. 시스템 레벨: 외부 바이너리 격리 관리 (Isolated FFmpeg)
운영체제 환경 변수(`PATH`) 오염으로 인한 버전 충돌을 방지하고, 실행 환경의 독립성을 보장하기 위해 **바이너리 직접 참조 전략**을 채택한다.
- **격리된 프로비저닝**: `scripts/install_ffmpeg.ps1`을 통해 검증된 정적 바이너리를 `C:\ffmpeg\bin`에 독립적으로 배치한다.
- **정적 경로 바인딩**: 전역 환경 변수를 수정하지 않고, `src/utils/audio_utils.py` 등 내부 로직에서 해당 절대 경로를 직접 호출하여 `yt-dlp` 및 `pydub`과의 연동 무결성을 확보한다.

#### 5.1.3. 애플리케이션 레벨: 핵심 라이브러리 스택 및 역할
본 파이프라인의 안정적인 구동을 위해 최적화된 핵심 엔진 라이브러리군이다.

- **딥러닝 엔진 (Core AI Stack)**
    - `transformers`: Whisper 모델의 사전 학습된 가중치 로딩 및 Encoder-Decoder 트랜스포머 아키텍처 제어.
    - `peft (LoRA)`: 대규모 모델의 효율적 파인튜닝을 위해 저차원 행렬(Low-Rank)을 원본 가중치에 주입하는 핵심 엔진.
    - `torch (PyTorch)`: Tensor 연산 및 역전파를 수행하며, Windows CPU 환경에서의 안정성을 위해 FP32 Full Precision 연산을 담당.
    - `datasets`: **IterableDataset** 기능을 통해 수천 개의 오디오 데이터를 로컬 메모리 부하 없이 실시간 스트리밍으로 주입.

- **멀티미디어 및 데이터 처리 (Data Engineering)**
    - `yt-dlp`: 네트워크 스트림으로부터 VTT 메타데이터와 오디오 컨테이너를 안전하게 추출하는 데이터 수집 라이브러리.
    - `pydub` & `librosa`: FFmpeg 백엔드를 활용하여 샘플 단위의 정밀한 오디오 커팅, 리샘플링 및 평가용 시계열 데이터 분석 수행.
    - `pandas`: 수만 개의 데이터 세그먼트 메타데이터를 관리하고 학습 파이프라인에 매핑하는 데이터 프레임 엔진.

- **모니터링 및 시각화 (Telemetry & UI)**
    - `rich`: 터미널 내 실시간 RGB 대시보드와 진척도 시각화를 통해 사용자 경험(UX) 극대화.
    - `psutil`: 시스템 자원(CPU, RAM) 상태를 커널 레벨에서 감시하여 대시보드에 실시간 전송.

- **검증 및 성능 평가 (Metric Validation)**
    - `evaluate` & `jiwer`: STT 성능 측정의 표준인 WER(단어 오차율) 및 CER(음절 오차율)을 과학적으로 산출하기 위한 수학적 알고리즘 라이브러리.

### 5.2. 운영 프로세스 상세 명세 (Operational Workflow Deep-Dive)

본 파이프라인은 데이터의 생성부터 최종 배포용 모델 추출까지의 전 과정을 자동화하며, 각 단계는 원자성(Atomicity)을 유지하도록 설계되었다.

#### 1단계: 데이터셋 구축 및 정제 (`01_build_dataset.py`)
이 단계는 비정형 유튜브 소스로부터 기계학습이 가능한 정형 데이터셋을 추출하는 ETL 과정이다.
- **Ingestion**: `yt-dlp`를 통해 자막(WebVTT)과 오디오(WAV)를 수집한다. 자막 파싱 방식을 채택하여 전송량 최적화 및 수집 안정성을 달성한다.
- **Parallel Transformation**: 추출된 오디오 파일은 `ProcessPoolExecutor` 기반의 워커들에게 분배되어 자막 타임스탬프에 맞춰 밀리초(ms) 단위로 정밀하게 슬라이싱된다.
- **Normalization**: 모든 슬라이스 데이터는 $16,000\,Hz$ 샘플링 레이트로 통일되며, `metadata.csv`에 상대 경로와 전사 텍스트 쌍으로 매핑되어 저장된다.

#### 2단계: 안정성 우선 LoRA 학습 (`02_start_training.py`)
Whisper 모델 위에 특정 도메인 지식을 주입하는 파인튜닝 과정으로, Windows 환경에서의 안정성을 극대화하도록 설계되었다.
- **Streaming Strategy**: `IterableDataset`을 도입하여 수천 개의 오디오 데이터를 한 번에 로드하지 않고 실시간 스트리밍 방식으로 주입함으로써, Windows의 메모리 맵핑 제한(`WinError 87`)을 원천적으로 해결한다.
- **Process Isolation**: 멀티프로세싱 시 발생하는 직렬화 에러(`Pickle Error`)를 방지하기 위해, 데이터 제너레이터를 외부 객체(Logger, UI 등)와 완전히 격리하여 독립적으로 구동한다.
- **Telemetry & Resilience**: `Rich` 기반 대시보드로 학습 상태를 실시간 모니터링하며, 프로세스 중단 시에도 최신 체크포인트에서 즉시 재개(`resume_from_checkpoint`)할 수 있는 영속성을 보장한다.

#### 3단계: 정량적 성능 평가 (`eval.py`)
학습된 모델의 언어적 이해도를 검증하기 위해 전용 평가 메트릭을 산출한다.
- **Metric Calculation**: `evaluate` 라이브러리를 사용하여 한국어 전사에 핵심적인 **CER(음절 오차율)**과 WER을 계산한다.
- **Inference Pipeline**: 테스트 샘플들을 `model.generate()`에 투입하여 생성된 결과와 실제 정답 사이의 편집 거리를 측정함으로써 모델의 실제 성능을 정량화한다.

#### 4단계: 모델 병합 및 GGUF 최적화 내보내기 (`03_export_model.py`)
운영 환경 배포를 위해 LoRA 어댑터를 베이스 모델과 일체화하고 최적화하는 최종 단계이다.
- **Weight Merging**: `merge_and_unload()` 메서드를 통해 분리된 LoRA 레이어 가중치를 베이스 모델에 합산하여 단일 모델 파일로 통합한다.
- **Quantization & Export**: 병합된 모델은 FP16/FP32 포맷으로 저장된 후, `llama.cpp` 도구 체인과 연동되어 **GGUF** 포맷으로 변환된다. 이를 통해 모델 용량을 압축하고 CPU 추론 속도를 극대화한다.

## 6. 실험 로드맵 및 검증 전략 (Experimental Roadmap & Methodology)

본 프로젝트는 데이터의 전처리 정밀도(Chunking Precision)와 모델의 수용 용량(Model Capacity) 사이의 상관관계를 정량적으로 분석하고, 최적의 비용 대비 성능(Cost-Performance) 지점을 도출하는 것을 핵심 전략으로 삼는다.

### 6.1. 실험 설계 원칙 (Design of Experiments)
모든 실험은 변수 통제를 위해 동일한 학습 하이퍼파라미터(Learning Rate, Batch Size, Optimizer 등)를 유지하며, 오직 **데이터 세그먼트 전략**과 **모델 아키텍처 규모**만을 독립 변수로 설정하여 교차 검증을 수행한다.

- **목적 함수**: $\min(WER, CER)$ s.t. $\text{Inference Time} \leq \text{Threshold}$
- **평가 셋**: 슈카월드 특정 에피소드에서 무작위 추출된 10%의 홀드아웃(Hold-out) 데이터셋 활용.

### 6.2. 실험 단계별 가설 및 목표 (Phased Hypotheses)

1. **Phase 1 (Baseline Exploration)**: 
    - **가설**: 가장 낮은 연산 비용으로 파이프라인의 엔드투엔드 무결성을 검증한다.
    - **목표**: Tiny 모델에서 단순 시간 누적 방식의 전처리 데이터가 보여주는 최소 성능(Base WER)을 측정한다.
2. **Phase 2 (Data Quality vs. Model Scale)**: 
    - **가설**: 전처리의 정밀도 향상(Lv.2)이 소형 모델(Tiny)의 문맥 이해 한계를 보완해 줄 것이다.
    - **목표**: 문장 단위 동적 청킹이 음절 단위 인식률(CER)에 미치는 기여도를 정량화한다.
3. **Phase 3 (Optimization Synergy)**: 
    - **가설**: 중형 모델(Small)과 고정밀 전처리(Lv.3)의 조합이 특정 도메인 용어(금융, 시사) 인식에서 임계점을 돌파할 것이다.
    - **목표**: 무음 구간 기반 정밀 정렬을 통한 오디오-텍스트 간의 시계열 무결성 극대화.
4. **Phase 4 (SOTA Implementation)**: 
    - **가설**: 대형 모델(Large-v3)의 Zero-shot 성능과 고도화된 LoRA 어댑터의 결합이 최고 수준의 전사 품질을 달성한다.
    - **목표**: 도메인 특화 STT 엔진으로서의 최종 성능 확정 및 배포 모델 생성.

### 6.3. 실험 진행 상황 (Experiment Tracker)

| 완료 | 페이즈 | 모델 | 전처리 스킬 | 현재 상태 | WER/CER | 소요 시간 |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| [/] | **Phase 1** | `tiny` | Lv.1 (25s 고정) | `Ready to Start` | - / - | - |
| [ ] | **Phase 1-1**| `tiny` | Lv.2 (15s 동적) | `Scheduled` | - / - | - |
| [ ] | **Phase 2** | `small`| Lv.1 (25s 고정) | `Scheduled` | - / - | - |
| [ ] | **Phase 2-1**| `small`| Lv.2 (15s 동적) | `Scheduled` | - / - | - |
| [ ] | **Phase 3** | `small`| **Lv.3 (Skilled)** | `Waiting` | - / - | - |
| [ ] | **Phase 4** | **Large-v3**| **Lv.3 (Skilled)** | `Final Boss` | - / - | - |

### 6.4. 전처리(Chunking) 레벨 정의
데이터의 정밀도가 모델의 문맥 이해도에 미치는 영향을 분석하기 위해 세 단계의 청킹 전략을 정의한다.

- **Lv.1 (Basic) - Time-based Accumulation**: 
    - **전략**: 자막 타임스탬프를 기준으로 단순 시간 누적(약 25s)을 통해 세그먼트 생성.
    - **특징**: 구현이 단순하며 타임라인 위주의 정렬에 최적화되어 있으나, 문장 중간 절단 가능성이 존재함.
- **Lv.2 (Smart) - Boundary Protection**: 
    - **전략**: VTT 자막의 경계를 인식하여 발화 중간 절단을 방지하고, 15~30s 사이에서 유동적으로 그룹화 수행.
    - **특징**: 문맥적 완결성을 확보하여 모델의 언어 모델링 성능 향상을 유도함.
- **Lv.3 (Skilled) - Hybrid Precision Alignment**: 
    - **전략**: VAD(Voice Activity Detection)를 통한 무음 구간 탐지와 형태소 분석을 결합하여 인간의 호흡 단위로 데이터를 정밀 분할.
    - **특징**: 오디오-텍스트 간의 시계열 무결성을 극대화하여 가장 높은 전사 정확도(CER)를 목표로 함.

---
**Note**: 본 시스템은 CPU 환경에서도 안정적으로 동작하도록 설계되었으나, 학습 효율을 위해 최신 NVIDIA GPU 환경(CUDA) 사용을 권장한다.

---
> **"데이터가 장인정신을 만나면, 인공지능은 예술이 된다."** - AMEVA STT Project
