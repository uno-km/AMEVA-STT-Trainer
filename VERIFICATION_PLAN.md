# 🚀 Shuka-STT Trainer: 초정밀 검증 마스터 플랜

본 문서는 전처리 전략과 모델 규모의 조합을 테스트하는 **실험 대시보드**입니다.

---

## 📊 실험 진행 상황 (Experiment Tracker)

| 완료 | 페이즈 | 모델 | 전처리 스킬 | 현재 상태 | WER/CER | 소요 시간 |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| [ ] | **Phase 1** | `tiny` | Lv.1 (25s 고정) | `Ready to Start` | - / - | - |
| [ ] | **Phase 1-1**| `tiny` | Lv.2 (15s 동적) | `Scheduled` | - / - | - |
| [ ] | **Phase 2** | `small`| Lv.1 (25s 고정) | `Scheduled` | - / - | - |
| [ ] | **Phase 2-1**| `small`| Lv.2 (15s 동적) | `Scheduled` | - / - | - |
| [ ] | **Phase 3** | `small`| **Lv.3 (Skilled)** | `Waiting` | - / - | - |
| [ ] | **Phase 4** | **Large-v3**| **Lv.3 (Skilled)** | `Final Boss` | - / - | - |

---

## 🛠️ 전처리(Chunking) 레벨 정의

*   **Lv.1 (Basic)**: 단순 누적. 타임스탬프 합이 25초 넘으면 절삭.
*   **Lv.2 (Smart)**: **문장 경계 보호.** 15~30초 사이 유동적 묶음. (말 끊김 없음)
*   **Lv.3 (Skilled)**: **무음 구간 + 호흡 단위.** 문맥의 최소 단위로 초정밀 분할.

---

## 📉 결과 요약 및 인사이트
> 각 실험이 끝난 후 여기에 핵심 변화(예: "데이터 양이 3배 늘어남", "특유의 말투를 더 잘 잡음")를 기록하세요.

- **Phase 1**: (기록 대기 중...)
- **Phase 2**:
- **Phase 3**:

---
> **"데이터가 장인정신을 만나면, 인공지능은 예술이 된다."** - AMEVA STT Project

---

### 🛠️ 재현 및 검증 커맨드 (Reproduction Commands)
* **데이터셋 빌드**: `.\venv\Scripts\python.exe scripts/01_build_dataset.py --folder dataset/2026/05/17 --name test_run_verify`
* **단위 테스트 실행 (Standard unittest & pytest compatible)**: `.\venv\Scripts\python.exe tests/test_data_integrity.py`
  * *Note: 테스트 스위트는 표준 `unittest.TestCase` 구조로 작성되어 `python -m pytest tests/test_data_integrity.py`로도 동일한 검증이 가능합니다.*
* **토큰화 명세 (Tokenization Spec)**: 토큰은 정규식 `[0-9A-Za-z가-힣]+`을 통과하는 요소만 필터링 및 정규화하여 추출되며, 이에 따라 문장부호 및 침묵 마커(`. . .`)는 오탐 연산에서 완전히 격리됩니다.

