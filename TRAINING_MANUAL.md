# AMEVA STT Whisper Fine-Tuning 매뉴얼

이 문서는 윈도우 CPU 환경에서 Whisper 모델을 LoRA(Low-Rank Adaptation) 방식으로 파인튜닝하기 위한 전체 과정과 트러블슈팅 기록을 담고 있습니다.

---

## 1. 학습 파이프라인 단계 (3-Step)

학습은 총 3단계의 스크립트 실행으로 구성됩니다.

### [1단계] 데이터셋 빌드 (Step 01)
- 실행: `.\venv\Scripts\python.exe scripts/01_build_dataset.py`
- 역할: `dataset/raw_data` 폴더의 영상을 분석하여 `metadata.csv`를 생성합니다.
- 결과: 학습에 사용할 오디오 경로와 전사 데이터 리스트가 준비됩니다.

### [2단계] 모델 학습 (Step 02)
- 실행: `.\venv\Scripts\python.exe scripts/02_start_training.py --skip`
- 역할: 실제로 Whisper 모델을 불러와 한국어 학습을 진행합니다.
- 주요 옵션: `--skip` 또는 `-s`를 붙이면 시스템 자원 확인 후 사용자 승인 절차를 건너뛰고 즉시 시작합니다.

### [3단계] 모델 내보내기 (Step 03)
- 실행: `.\venv\Scripts\python.exe scripts/03_export_model.py`
- 역할: 학습된 LoRA 가중치를 베이스 모델과 병합하고, 추론에 최적화된 형식(GGUF 등)으로 변환할 준비를 합니다.

---

## 2. 모니터링 및 로그 확인 방법

학습이 백그라운드에서 돌아갈 때 상태를 확인하는 방법입니다.

### 실시간 상태 확인
- 터미널에 나타나는 Progress Bar를 확인하십시오.
- `[00:45<12:30:40, 45.18s/it]`와 같은 표시에서 `45.18s/it`는 1단계 학습에 걸리는 시간이며, 오른쪽의 시간은 남은 예상 시간입니다.

### 로그 파일 확인
- 전체 실행 로그: `logs/pipeline_run.log` 파일에서 상세한 진행 상황과 에러 기록을 볼 수 있습니다.
- 에러 전용 로그: 치명적 오류 발생 시 `logs/syuka_error_log.md`에 상세한 트레이스백(Traceback)이 기록됩니다.

---

## 3. 트러블슈팅 기록 (주요 해결 사례)

윈도우 네이티브 환경에서 발생한 고질적인 문제들과 그 해결책입니다.

### [CASE 01] OSError: [WinError 87] 매개 변수가 틀립니다
- 증상: 학습 엔진이 시동을 걸 때 윈도우 커널에서 에러를 뱉으며 종료됨.
- 원인: 윈도우의 메모리 맵핑(Memory Mapping) 제한 및 PyTorch의 멀티프로세싱 충돌.
- 해결:
    - IterableDataset (Streaming) 모드 도입: 데이터를 한꺼번에 메모리에 올리지 않고 실시간으로 읽어오도록 수정.
    - dataloader_pin_memory=False 및 dataloader_num_workers=0 강제 설정.
    - model.config.use_cache=False 설정으로 캐시 충돌 방지.

### [CASE 02] TypeError: cannot pickle 'ConsoleThreadLocals' object
- 증상: 데이터셋 제너레이터 실행 시 객체 복사(Pickle) 에러 발생.
- 원인: rich 라이브러리나 logger 객체가 데이터 로딩 프로세스에 엉켜서 발생.
- 해결: 제너레이터 함수를 외부 객체와 완전히 분리(Isolation)하고, 필요한 라이브러리를 함수 내부에서 로컬로 임포트하도록 수정.

### [CASE 03] torchcodec DLL 로드 실패 및 라이브러리 충돌
- 증상: FFmpeg 버전 불일치로 인한 오디오 로딩 에러.
- 해결: 불안정한 torchcodec을 제거하고, 가장 신뢰도 높은 librosa 및 soundfile 기반의 수동 오디오 로딩 로직으로 전면 교체.

---

## 4. 사용자 가이드 및 주의사항

- 이어하기 기능: 학습 중 중단되더라도 다시 실행하면 `models/lora_weights`의 체크포인트를 자동으로 찾아 마지막 지점부터 이어서 학습합니다.
- 메모리 관리: 학습 중에는 가급적 웹 브라우저(크롬 등)의 탭을 줄여 CPU와 RAM 자원을 학습 엔진에 집중시켜 주십시오.
- 데이터 업데이트: 새로운 영상을 추가했다면 metadata.csv만 갱신하면 스트리밍 모드에서 자동으로 새 데이터를 읽어옵니다.

---

## 5. 향후 활용 및 고도화 (Next Steps)

### 모델 병합 (Merge)
학습이 완료되면 LoRA 어댑터 가중치만 저장됩니다. 이를 실제 Whisper 모델처럼 사용하려면 베이스 모델과 병합해야 합니다.
- `.\venv\Scripts\python.exe scripts/03_export_model.py`를 실행하여 병합된 모델을 생성하십시오.

### GGUF 변환 및 추론
병합된 모델은 `models/merged_model`에 저장됩니다. 이를 `llama.cpp`나 다른 라이브러리에서 사용하기 위해 GGUF 형식으로 변환할 수 있습니다.
- 프로젝트 내 `scripts/export_gguf.py` 등을 활용하여 경량화 및 변환을 진행하십시오.

### GPU 환경으로 업그레이드 시
만약 NVIDIA GPU 환경으로 옮겨서 학습한다면 다음 설정을 변경하여 속도를 획기적으로 높일 수 있습니다.
- `training_args` 내의 `fp16 = True` 또는 `bf16 = True` 설정.
- `dataloader_num_workers = 4` 이상 설정.
- `bitsandbytes` 라이브러리를 통한 4/8비트 양자화 학습(QLoRA) 고려.

---

## 6. Contact & Support

이 프로젝트가 도움이 되셨다면, 아래 채널을 통해 개발자를 응원하거나 피드백을 주실 수 있습니다.

### Contact Me
- **GitHub**: [https://github.com/uno-km/AMEVA-STT-Trainer](https://github.com/uno-km/AMEVA-STT-Trainer)
- **Tistory**: [여기에 티스토리 주소 입력]
- **KakaoTalk ID**: [여기에 카톡 ID 입력](https://open.kakao.com/o/여기에_오픈채팅_코드_입력)
- **Email**: [여기에 이메일 주소 입력](mailto:여기에_이메일_주소_입력)

### Support & Donation
프로젝트의 지속적인 발전과 고도화를 위해 후원해주시면 큰 힘이 됩니다.

- **후원 계좌**: [은행명] [계좌번호] (예금주: [이름])
- **후원 QR**: 
  ![Donation QR Code](docs/images/donation_qr.png)
  *(QR 코드 이미지를 `docs/images/donation_qr.png` 경로에 저장하면 여기에 표시됩니다.)*
