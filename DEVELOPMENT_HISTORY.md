# AMEVA-STT-Trainer 개발 연대기 및 트러블슈팅 리포트

본 문서는 Windows 11 환경에서 Whisper 모델의 LoRA 파인튜닝 파이프라인을 구축하며 발생한 기술적 난제들과 그 해결 과정을 기록한 엔지니어링 리포트입니다.

---

## 1. 프로젝트 개요 (Mission Objective)
- **목표**: 저사양/범용 환경(Windows CPU)에서 Whisper 모델을 특정 도메인 데이터로 파인튜닝할 수 있는 안정적인 파이프라인 구축.
- **핵심 도전 과제**: Windows의 엄격한 메모리 관리 정책과 PyTorch의 멀티프로세싱 호환성 문제 해결.

---

## 2. 주요 트러블슈팅 및 기술적 돌파구 (The War History)

### [난제 01] DLL 로드 및 오디오 라이브러리 충돌
- **현상**: `torchcodec` 사용 시 FFmpeg DLL 불일치로 인한 시스템 크래시 및 오디오 로딩 실패.
- **원인 분석**: Windows 환경에서 최신 PyTorch 익스텐션들의 DLL 의존성 관리가 불안정함.
- **해결책**: 불안정한 라이브러리를 배제하고, 가장 검증된 `librosa`와 `soundfile` 기반의 수동 오디오 디코딩 로직으로 회귀하여 원천적인 안정성 확보.

### [난제 02] OSError: [WinError 87] 매개 변수가 틀립니다
- **현상**: `Dataset.map`을 통한 대규모 데이터 전처리 시 윈도우 커널 에러 발생.
- **원인 분석**: 윈도우의 메모리 맵핑(Memory Mapping) 시스템이 대량의 파일 오프셋을 한꺼번에 처리하지 못해 발생하는 시스템 레벨의 충돌.
- **해결책 (Technical Breakthrough)**:
    - **Streaming Mode (IterableDataset)** 도입: 데이터를 메모리에 미리 올리지 않고, 학습 루프가 실행될 때마다 실시간으로 제너레이터에서 데이터를 하나씩 추출하여 전달하는 방식 채택.
    - 이를 통해 메모리 점유율을 획기적으로 낮추고 커널 에러를 완벽히 차단함.

### [난제 03] TypeError: cannot pickle 'ConsoleThreadLocals' object
- **현상**: 학습 시작 시 프로세스 간 객체 전달 실패로 인한 중단.
- **원인 분석**: `rich` 라이브러리의 글로벌 객체나 `logger`가 데이터 로딩 제너레이터 내부로 캡처(Capture)되면서 직렬화(Pickle)가 불가능해짐.
- **해결책**: 
    - **Isolation Strategy**: 데이터 제너레이터 함수(`dataset_generator`)를 외부 환경과 완전히 격리.
    - 필요한 모든 라이브러리 임포트 및 객체 생성을 함수 내부에서 수행하도록 설계하여 외부 객체의 간섭을 차단.

---

## 3. 최종 시스템 아키텍처 (Final Architecture)

### 데이터 로딩 엔진
- **Engine**: `IterableDataset.from_generator`
- **Optimization**: 
    - `dataloader_num_workers = 0`: 직렬 처리를 통한 Windows 호환성 극대화.
    - `float32` 정규화: CPU 연산 시 발생할 수 있는 데이터 타입 불일치 방지.

### 학습 최적화 설정
- **Precision**: FP32 (Full Precision) 강제 적용으로 연산 안정성 확보.
- **Memory**: `use_cache=False` 설정을 통해 그래디언트 체크포인팅 시의 메모리 오버헤드 방지.
- **Resume**: `checkpoint-*` 폴더 자동 검색 및 학습 이어하기 기능 구현.

---

## 4. 향후 과제 (Future Roadmap)
1. **GPU 확장성**: 현재의 안정적인 로직을 기반으로 CUDA 환경에서의 가속화 옵션(`fp16`, `bitsandbytes`) 검증 완료.
2. **GGUF 배포**: 학습된 LoRA 어댑터를 GGUF 형식으로 변환하여 저사양 기기에서의 추론 효율 극대화.

---

## 5. 결론
본 프로젝트는 Windows 환경이 딥러닝 학습에 친화적이지 않음에도 불구하고, 하이 레벨 프레임워크의 편의성보다는 하드웨어와 OS 커널에 대한 깊은 이해를 바탕으로 아키텍처를 재설계함으로써 성공적인 학습 안정성을 달성하였습니다.

> **"안정성은 최적화의 결과가 아니라, 올바른 설계의 시작이다."**
