# AMEVA-STT-Trainer: Domain-Specific Whisper Fine-tuning Pipeline

## 1. 개요 (Abstract)
본 프로젝트는 특정 도메인(경제/시사 콘텐츠)에 특화된 음성 인식(STT) 모델을 구축하기 위한 엔드투엔드 파이프라인이다. OpenAI의 Whisper 모델을 기반으로 하며, 데이터 수집의 자동화, 병렬 전처리 알고리즘, PEFT(LoRA)를 활용한 효율적 파인튜닝, 그리고 GGUF 포맷을 통한 최적화된 배포 과정을 포함한다. 특히 자막과 오디오의 정렬 무결성을 확보하기 위한 다단계 검증 체계를 설계하여 학습 데이터의 품질을 극대화하였다.

## 2. 주요 기술적 특징 (Technical Deep-Dive)

### 2.1. 데이터 획득 및 전처리 알고리즘 (Data Engineering & Signal Processing)
본 파이프라인은 비정형 스트리밍 데이터로부터 고품질 학습 코퍼스를 추출하기 위해 다단계 시그널 프로세싱 체계를 구축하였다.
- **Robust VTT Synchronization**: `yt-dlp` 엔진을 통해 추출된 WebVTT 자막 데이터와 오디오 신호 사이의 정렬(Alignment) 무결성을 확보한다. 자막의 시작($T_{start}$)과 종료($T_{end}$) 시간을 기준으로 오디오 세그먼트를 슬라이싱하며, 이때 발생할 수 있는 샘플링 레이트 미스매치를 방지하기 위해 모든 소스는 $f_s = 16,000\,Hz$ (Mono)로 강제 리샘플링된다.
- **Feature Extraction (Log-Mel Spectrogram)**: Whisper 모델의 인풋 텐서로 변환하기 위해, 연속적인 오디오 신호에 STFT(Short-Time Fourier Transform)를 적용한다. 이후 $N=80$ 채널의 Mel-filterbank를 통과시켜 인간의 청각 특성을 반영한 Log-Mel Spectrogram을 생성하며, 이는 다음과 같은 수식으로 정의된다:
  $$ S_{mel}(m) = \ln \left( \sum_{k=0}^{N-1} |X(k)|^2 \cdot H_m(k) \right) $$
- **Parallel Processing Complexity**: 대규모 데이터셋 구축 시 발생하는 병목 현상을 제거하기 위해 `ProcessPoolExecutor`를 활용한 $O(N/P)$ 수준의 시간 복잡도 최적화를 달성하였다 ($N$: 영상 수, $P$: 할당된 CPU 프로세스 수).

### 2.2. 모델 아키텍처 및 학습 전략 (Fine-Tuning Methodology)
본 프로젝트는 OpenAI의 **Whisper** 모델(Transformer 기반 Encoder-Decoder 구조)을 베이스로 하며, 효율적인 도메인 적응을 위해 PEFT 전략을 채택하였다.
- **LoRA (Low-Rank Adaptation) Theory**: 모델의 전체 파라미터 $W \in \mathbb{R}^{d \times k}$를 고정한 채, 저차원 행렬 $A$와 $B$의 곱으로 표현되는 업데이트 행렬 $\Delta W$만을 학습시킨다. 이는 다음과 같은 가중치 업데이트 식을 따른다:
  $$ W_{updated} = W_0 + \Delta W = W_0 + BA \quad (\text{where } B \in \mathbb{R}^{d \times r}, A \in \mathbb{R}^{r \times k}, r \ll d, k) $$
  이를 통해 학습 파라미터 수를 기존 대비 $1\%$ 미만으로 줄이면서도, 경제 용어 및 특정 화자의 조음 특성(Articulation)을 정밀하게 캡처한다.
- **Hyperparameter Optimization**: 
    - **Rank ($r$)**: 32 혹은 64로 설정하여 모델의 표현력과 계산 효율 사이의 균형을 맞춤.
    - **Alpha ($\alpha$)**: 학습률 스케일링 인자로 작용하며, $\alpha/r$ 비율을 통해 가중치 업데이트 강도를 조절함.
    - **Dropout**: 과적합(Overfitting) 방지를 위해 LoRA 레이어에 $0.05 \sim 0.1$의 드롭아웃 적용.
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
    - `processor.py`: 오디오 신호 처리 및 텍스트 정렬을 담당하며, 병렬 컴퓨팅 자원을 최대한 활용한다.
    - `validator.py`: 학습 전 데이터 무결성을 검증하는 게이트웨이 역할을 수행한다.
- **`src/training/` (Training Layer)**: `transformers.Trainer`를 래핑하여 학습 프로세스를 제어한다. 커스텀 콜백을 통해 실시간 대시보드와 연동되며, 체크포인트 저장 전략을 관리한다.
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
└── outputs/            # 학습된 Adapter 및 병합된 모델 가중치
```

## 4. 데이터 무결성 및 장애 복구 체계 (Reliability & Resilience)

실무 환경에서의 데이터 오염 및 크래시 상황에 대비하여 다음과 같은 안전장치를 구현하였다.

### 4.1. 3단계 무결성 검증 프로토콜
학습 데이터셋의 노이즈를 제거하기 위해 `validator.py`를 통한 단계별 검수를 수행한다.
1. **정적 검수(Physical)**: 오디오 파일의 헤더 정보 파싱 및 0바이트 파일 자동 제거.
2. **논리 검수(Logical)**: 자막 텍스트의 특수문자 정제 및 빈 문자열(Null) 레코드 필터링.
3. **정렬 검수(Alignment)**: Whisper의 30초 윈도우를 초과하는 청크를 감지하여 자동 재분할(Re-segmentation).

### 4.2. 전역 예외 가드 (Global Exception Guard)
- 모든 주요 파이프라인은 `src/core/exceptions.py`에 정의된 데코레이터를 통해 실행된다.
- 예외 발생 시 스택 트레이스를 `logs/error_log.md`에 상세히 기록하고, 해당 시점의 시스템 상태를 스냅샷으로 남긴다.
- `resume_from_checkpoint` 설정을 통해 하드웨어 장애나 프로세스 강제 종료 시에도 마지막 학습 시점부터 즉시 재개가 가능하다.

## 5. 설치 및 파이프라인 가이드 (Execution Pipeline)

### 5.1. 인프라 구축 및 의존성 관리 전략 (Infrastructure Setup Strategy)

본 프로젝트는 복잡한 멀티미디어 처리와 딥러닝 환경의 재현성을 보장하기 위해 시스템 레벨과 애플리케이션 레벨의 의존성을 이원화하여 관리한다.

#### 5.1.1. 시스템 레벨: 외부 바이너리 격리 관리 (FFmpeg Automation)
멀티미디어 데이터 처리의 핵심인 **FFmpeg**의 경우, 운영체제 환경 변수(`PATH`) 오염으로 인한 버전 충돌을 방지하기 위해 **Isolated Binaries** 전략을 채택한다.
- **Automated Provisioning**: `scripts/install_ffmpeg.ps1` 파워쉘 스크립트는 신뢰할 수 있는 빌드 서버로부터 정적 컴파일된(Static-linked) FFmpeg 바이너리를 직접 획득한다.
- **Path Redirection**: 바이너리를 `C:\ffmpeg\bin` 경로에 독립적으로 배치한 후, 애플리케이션 내부 로직(`src/utils/audio_utils.py` 및 `src/data/scraper.py`)에서 해당 절대 경로를 직접 참조하도록 설계하였다. 이는 전역 환경 변수를 수정하지 않고도 `pydub`과 `yt-dlp`가 상호 연동되어 오디오 디코딩 및 인코딩을 수행할 수 있게 한다.

#### 5.1.2. 애플리케이션 레벨: 핵심 라이브러리 스택 및 역할
학습 파이프라인의 각 단계는 다음과 같은 고성능 라이브러리들에 의해 유기적으로 구동된다.

- **딥러닝 및 모델링 (Model Architecture)**
    - `transformers`: OpenAI Whisper 모델의 사전 학습된 가중치 로딩 및 Encoder-Decoder 트랜스포머 아키텍처 제어.
    - `peft (LoRA)`: 대규모 언어 모델의 효율적 파인튜닝을 위해 저차원 행렬(Low-Rank)을 원본 가중치에 주입하는 핵심 엔진.
    - `torch (PyTorch)`: Tensor 연산 및 역전파(Backpropagation)를 수행하는 기본 가속 프레임워크.
    - `bitsandbytes`: 8-bit/4-bit 양자화 학습 기술을 통해 메모리 점유율을 획기적으로 낮추고 CPU/GPU 자원 효율성 극대화.

- **데이터 및 오디오 처리 (Signal Processing)**
    - `yt-dlp`: 네트워크 스트림으로부터 VTT 메타데이터와 오디오 컨테이너를 안전하게 추출하는 데이터 수집 라이브러리.
    - `pydub`: FFmpeg의 래퍼로서, 샘플 단위의 정밀한 오디오 커팅 및 리샘플링 작업을 수행.
    - `librosa`: 평가(Evaluation) 단계에서 오디오 신호를 로드하고 시계열 분석을 위한 파라미터 추출 담당.
    - `pandas`: 수천 개의 데이터 세그먼트를 관리하고 학습 파이프라인에 주입하기 위한 메타데이터 관리 엔진.

- **시스템 텔레메트리 및 UI (Telemetry & Monitoring)**
    - `rich`: 터미널 환경에서 고도의 시각화와 실시간 대시보드(Live Dashboard) 인터페이스를 구축하여 사용자 경험 개선.
    - `psutil`: 하드웨어 자원(CPU, RAM)의 사용량을 커널 레벨에서 모니터링하여 대시보드에 실시간 전송.

- **검증 및 성능 평가 (Metric Validation)**
    - `evaluate` & `jiwer`: STT 성능 측정의 표준인 WER(단어 오차율) 및 CER(음절 오차율)을 과학적으로 산출하기 위한 수학적 알고리즘 라이브러리.

### 5.2. 운영 프로세스 상세 명세 (Operational Workflow Deep-Dive)

본 파이프라인은 데이터의 생성부터 최종 배포용 모델 추출까지의 전 과정을 자동화하며, 각 단계는 원자성(Atomicity)을 유지하도록 설계되었다.

#### 1단계: 데이터셋 구축 및 정제 (`01_build_dataset.py`)
이 단계는 비정형 유튜브 소스로부터 기계학습이 가능한 정형 데이터셋을 추출하는 ETL(Extract, Transform, Load) 과정이다.
- **Ingestion**: `yt-dlp`를 내부 서브프로세스로 호출하여 자막(WebVTT)과 오디오(WAV)를 동시 수집한다. 이때 API 기반의 수집이 아닌 VTT 파싱 방식을 채택하여 전송량 최적화 및 차단 회피를 달성한다.
- **Parallel Transformation**: 추출된 고용량 오디오 파일은 `ProcessPoolExecutor` 기반의 워커(Worker)들에게 분배된다. 각 워커는 자막의 타임스탬프 정보를 매개변수로 받아 `pydub` 엔진을 통해 밀리초(ms) 단위의 정밀한 오디오 슬라이싱을 수행한다.
- **Normalization**: 모든 슬라이스 데이터는 $16,000\,Hz$ 샘플링 레이트로 통일되며, `metadata.csv`에 상대 경로와 전사 텍스트(Transcription) 쌍으로 매핑되어 저장된다.

#### 2단계: 도메인 특화 LoRA 학습 (`02_start_training.py`)
Whisper 모델의 사전 학습된 가중치(Pre-trained Weights) 위에 특정 도메인 지식을 주입하는 파인튜닝 과정이다.
- **PEFT Integration**: `bitsandbytes`를 통해 베이스 모델을 4-bit/8-bit 양자화 상태로 로드한 후, `peft` 라이브러리를 사용하여 Attention Layer(q_proj, v_proj) 등에 가중치 어댑터를 삽입한다.
- **Telemetry Monitoring**: `Rich` 라이브러리를 활용한 커스텀 콜백(`DashboardCallback`)이 가동된다. 이는 매 스텝마다 `Loss`, `Learning Rate`, `Epoch` 정보를 수집하여 하단 고정형 RGB 대시보드에 시각화하며, `psutil`을 통해 CPU/RAM 자원 포화 상태를 실시간 감시한다.
- **Resilience**: `resume_from_checkpoint=True` 옵션을 통해 학습 도중 중단된 지점의 최신 가중치와 Optimizer 상태를 자동으로 복원하여 영속성 있는 학습을 보장한다.

#### 3단계: 정량적 성능 평가 (`eval.py`)
학습된 모델의 언어적 이해도를 검증하기 위해 전용 평가 메트릭을 산출한다.
- **Metric Calculation**: HuggingFace `evaluate` 라이브러리를 사용하여 **WER(Word Error Rate)**과 **CER(Character Error Rate)**을 독립적으로 계산한다. 한국어의 경우 음절 단위의 정확도가 중요하므로 CER 지표를 핵심 평가지표로 활용한다.
- **Inference Pipeline**: 학습 모드와 동일한 전처리 과정을 거친 테스트 샘플들을 `model.generate()` 함수에 투입하여 생성된 텍스트와 실제 정답(Ground Truth) 사이의 편집 거리(Edit Distance)를 측정한다.

#### 4단계: 모델 병합 및 GGUF 최적화 내보내기 (`03_export_model.py`)
운영 환경 배포를 위해 LoRA 어댑터를 베이스 모델과 일체화하고 최적화하는 최종 단계이다.
- **Weight Merging**: `merge_and_unload()` 메서드를 호출하여 분리되어 있던 LoRA 레이어의 가중치를 베이스 모델의 파라미터 행렬에 합산한다. 이를 통해 별도의 어댑터 로드 없이 단일 모델 파일로 동작 가능하게 한다.
- **Quantization & Export**: 병합된 모델은 FP16/FP32 포맷으로 임시 저장된 후, `llama.cpp` 도구 체인과 연동되어 GGUF 포맷으로 변환된다. `q4_k_m`, `q8_0` 등의 고성능 양자화 알고리즘을 적용하여 모델 용량을 약 1/4 수준으로 압축하면서도 성능 하락을 최소화한다.

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
| [ ] | **Phase 1** | `tiny` | Lv.1 (25s 고정) | `Ready to Start` | - / - | - |
| [ ] | **Phase 1-1**| `tiny` | Lv.2 (15s 동적) | `Scheduled` | - / - | - |
| [ ] | **Phase 2** | `small`| Lv.1 (25s 고정) | `Scheduled` | - / - | - |
| [ ] | **Phase 2-1**| `small`| Lv.2 (15s 동적) | `Scheduled` | - / - | - |
| [ ] | **Phase 3** | `small`| **Lv.3 (Skilled)** | `Waiting` | - / - | - |
| [ ] | **Phase 4** | **Large-v3**| **Lv.3 (Skilled)** | `Final Boss` | - / - | - |

### 6.4. 전처리(Chunking) 레벨 정의
- **Lv.1 (Basic)**: 단순 시간 누적 기반 절삭 (25s). 타임라인 위주의 단순 절단.
- **Lv.2 (Smart)**: **문장 경계 보호 전략.** VTT 자막 경계를 인식하여 발화 중간 절단을 방지하고 15~30s 사이에서 유동적으로 그룹화.
- **Lv.3 (Skilled)**: **초정밀 하이브리드 정렬.** VAD(Voice Activity Detection)를 통한 무음 구간 탐지와 형태소 분석을 결합하여 인간의 호흡 단위로 데이터를 분할.

---
**Note**: 본 시스템은 CPU 환경에서도 안정적으로 동작하도록 설계되었으나, 학습 효율을 위해 최신 NVIDIA GPU 환경(CUDA) 사용을 권장한다.

---
> **"데이터가 장인정신을 만나면, 인공지능은 예술이 된다."** - AMEVA STT Project
