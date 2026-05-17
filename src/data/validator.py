"""
src/data/validator.py
metadata.csv와 실제 WAV 파일 간의 3중 무결성 검수기.

검사 항목:
  1. WAV 파일 존재 여부 (os.path.exists)
  2. 0바이트 유령 파일 여부 (os.path.getsize > 0)
  3. transcription 텍스트 비어있지 않은지 (len > 0)

불량 레코드는 자동으로 제거하고 정제된 CSV를 덮어 저장한다.
검수 결과 리포트는 dataset/validation_report.md에 저장한다.
"""
import os
from datetime import datetime
import pandas as pd

from src.core.config import DATASET_DIR, METADATA_PATH
from src.core.exceptions import DataIntegrityError, exception_guard
from src.utils import logger

# 검수 결과 리포트를 저장할 Markdown 파일 절대 경로
REPORT_PATH = os.path.join(DATASET_DIR, "validation_report.md")


@exception_guard(location="validate_dataset() -> CSV 무결성 검수", reraise=True)
def validate_dataset(metadata_path: str = METADATA_PATH, dataset_dir: str = DATASET_DIR) -> pd.DataFrame:
    """
    metadata.csv를 로드하여 3중 검수를 수행한다.
    불량 행을 제거한 정제된 DataFrame을 반환하고,
    원본 CSV를 덮어쓴다.

    Raises DataIntegrityError: 유효 데이터가 0개일 때.
    """
    # metadata.csv 파일 존재 여부 확인
    if not os.path.exists(metadata_path):
        raise DataIntegrityError(f"metadata.csv 없음: {metadata_path}")

    # UTF-8 BOM 인코딩으로 CSV 로드 (엑셀 호환성 확보)
    df = pd.read_csv(metadata_path, encoding="utf-8-sig")
    # 전체 레코드 수 저장
    total = len(df)
    logger.info(f"검수 시작: 총 {total}개 레코드")

    # 불량 레코드 정보를 담을 리스트 (index, file_name, 사유)
    invalid_rows = []

    # 모든 레코드를 행 단위로 순회하며 3가지 검사 수행
    for idx, row in df.iterrows():
        # file_name 컬럼 값을 문자열로 변환 후 앞뒤 공백 제거
        file_name     = str(row.get("file_name", "")).strip()
        # transcription 컬럼 값을 문자열로 변환 후 앞뒤 공백 제거
        transcription = str(row.get("transcription", "")).strip()

        # 상대경로를 절대경로로 조합
        abs_path = os.path.join(dataset_dir, file_name)

        # 해당 레코드의 불량 사유 목록 (없으면 빈 리스트)
        reasons = []

        # 검사 1: 파일 존재
        if not os.path.exists(abs_path):
            reasons.append("파일 없음")

        # 검사 2: 0바이트 유령 파일
        elif os.path.getsize(abs_path) == 0:
            reasons.append("0바이트 파일")

        # 검사 3: 빈 텍스트 (빈 문자열이거나 pandas 가 읽어들인 "nan" 문자열)
        if not transcription or transcription == "nan":
            reasons.append("빈 transcription")

        # 한 가지라도 사유가 있으면 불량 레코드로 등록
        if reasons:
            invalid_rows.append({
                "index"     : idx,
                "file_name" : file_name,
                "reasons"   : ", ".join(reasons),
            })

    # 불량 레코드의 인덱스만 집합으로 추출
    bad_indices = {r["index"] for r in invalid_rows}
    # 불량 행을 제거하고 인덱스를 0부터 재정렬
    clean_df    = df.drop(index=bad_indices).reset_index(drop=True)

    # 유효 데이터가 하나도 없으면 치명적 오류로 처리
    if len(clean_df) == 0:
        raise DataIntegrityError("유효 데이터가 0개입니다. 전처리를 다시 실행하세요.")

    # 정제된 CSV 덮어 저장
    clean_df.to_csv(metadata_path, index=False, encoding="utf-8-sig")

    # Markdown 검수 리포트 생성 및 저장
    _write_report(total, len(invalid_rows), len(clean_df), invalid_rows, dataset_dir=dataset_dir)

    logger.info(
        f"검수 완료: 총 {total}개 중 불량 {len(invalid_rows)}개 제거, "
        f"최종 유효 {len(clean_df)}개"
    )
    return clean_df


def _write_report(total: int, bad: int, clean: int, invalid_rows: list, dataset_dir: str = DATASET_DIR) -> None:
    """Markdown 형식의 검수 결과 리포트를 저장한다."""
    # 현재 시각을 리포트 상단에 기록
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 리포트 내용을 줄 단위로 구성
    lines = [
        f"# Dataset Validation Report\n",
        f"- **검수 시각**: {timestamp}\n",
        f"- **총 레코드**: {total}\n",
        f"- **불량 제거**: {bad}\n",
        f"- **최종 유효**: {clean}\n",
        "\n## 불량 레코드 목록\n",
    ]
    if invalid_rows:
        # 불량 레코드가 있으면 Markdown 테이블로 출력
        lines.append("| index | file_name | 사유 |\n")
        lines.append("|---|---|---|\n")
        # 각 불량 레코드를 테이블 행으로 추가
        for r in invalid_rows:
            lines.append(f"| {r['index']} | {r['file_name']} | {r['reasons']} |\n")
    else:
        lines.append("불량 레코드 없음. 데이터셋 완벽.\n")

    report_path = os.path.join(dataset_dir, "validation_report.md")
    # 리포트 저장 디렉터리가 없으면 생성
    os.makedirs(dataset_dir, exist_ok=True)
    # 리포트 파일을 UTF-8 로 저장 (기존 파일 덮어씀)
    with open(report_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    logger.info(f"검수 리포트 저장: {report_path}")
