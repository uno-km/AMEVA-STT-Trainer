"""
scripts/eval.py
[단계 평가] 학습된 LoRA 모델의 WER/CER을 측정한다.
베이스 모델과의 수치 비교를 통해 파인튜닝 효과를 검증한다.
"""
import sys
import os
import torch
import pandas as pd
import librosa
from tqdm import tqdm
from evaluate import load

# 프로젝트 루트 디렉터리를 Python 경로에 등록하여 src 모듈을 불러올 수 있도록 설정
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.whisper_lora import load_for_inference
from src.core.config         import CFG, DATASET_DIR, METADATA_PATH
from src.utils               import logger


def main():
    # 실시간 모니터링 대시보드 활성화
    with logger.dashboard_context():
        logger.set_status("모델 평가 중", "초기화")
        logger.info("평가 시작")

        # 단어 에러율(WER) 및 문자 에러율(CER) 지표 로드
        wer_metric = load("wer")
        cer_metric = load("cer")

        # 추론용으로 베이스 모델과 LoRA 어댑터 가중치 로드
        model, processor = load_for_inference()
        if model is None:
            # 모델 로드 실패 시 에러 출력 후 프로그램 종료
            logger.error("모델 로딩 실패. 학습 완료 여부를 확인하세요.")
            sys.exit(1)

        # 평가에 사용할 메타데이터 CSV 로드
        df = pd.read_csv(METADATA_PATH, encoding="utf-8-sig")
        # 설정된 샘플 수만큼 무작위로 추출하여 평가 데이터 생성 (고정된 난수 시드 사용)
        n = min(CFG["eval_samples"], len(df))
        df = df.sample(n, random_state=42)
        logger.info(f"평가 샘플 수: {n}")

        # 예측 결과와 정답(전사 텍스트)을 저장할 리스트
        predictions, references = [], []

        # 각 평가 데이터 행을 순회
        for idx, (_, row) in enumerate(df.iterrows()):
            # 대시보드 상태바에 현재 진행률 표시
            logger.set_status("모델 평가 중", f"진행률: {idx+1}/{n}")
            # 오디오 파일의 절대 경로 계산
            abs_path = os.path.join(DATASET_DIR, row["file_name"])
            if not os.path.exists(abs_path):
                # 파일이 존재하지 않으면 경고 출력 후 건너뜀
                logger.warning(f"파일 없음, 스킵: {abs_path}")
                continue

            # librosa를 사용하여 오디오 파일 로드 (16kHz 리샘플링)
            audio, _ = librosa.load(abs_path, sr=CFG["sample_rate"])
            # 프로세서를 통해 오디오 데이터를 입력 특징(Mel-Spectrogram)으로 변환
            input_features = processor(
                audio, sampling_rate=CFG["sample_rate"], return_tensors="pt"
            ).input_features

            # 경사 계산 비활성화 (추론 모드)
            with torch.no_grad():
                # 모델을 사용하여 텍스트 생성
                generated_ids = model.generate(input_features)
                # 생성된 토큰 ID를 실제 텍스트로 변환 (특수 토큰 제외)
                pred = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

            # 결과 저장
            predictions.append(pred)
            references.append(row["transcription"])

        # 평가 결과가 하나도 없는 경우 종료
        if not predictions:
            logger.error("유효 샘플 없음. 평가 종료.")
            return

        # 전체 예측 결과에 대한 WER 및 CER 지표 계산
        wer = wer_metric.compute(predictions=predictions, references=references)
        cer = cer_metric.compute(predictions=predictions, references=references)

        # 최종 지표를 콘솔에 강조 출력
        print("\n" + "=" * 40)
        print(f"WER (Word Error Rate) : {wer:.4f}")
        print(f"CER (Char Error Rate) : {cer:.4f}")
        print("=" * 40)

        # 평가 결과를 로그 파일에 기록
        logger.info(f"평가 완료 | WER={wer:.4f} | CER={cer:.4f}")


if __name__ == "__main__":
    # 메인 실행부 호출
    main()
