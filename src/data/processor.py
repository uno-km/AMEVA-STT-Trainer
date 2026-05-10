"""
src/data/processor.py
VTT 자막을 파싱하고, 오디오를 청크로 분할하여 저장한다.
metadata.csv 레코드 목록을 반환한다.

방법 A (누적 분할):
  - 자막 타임스탬프를 순서대로 읽으며 텍스트를 누적한다.
  - 누적 길이가 MAX_CHUNK_DURATION_MS를 초과하면 그 지점에서 청크를 확정한다.
  - file_name 컬럼: YYYY/MM/DD/{video_id}/chunks/chunk_XXXX.wav (상대경로)
"""
import os
import re
import webvtt
from typing import List, Dict, Optional

from src.core.config import CFG, DATASET_DIR
from src.core.exceptions import TranscriptError, exception_guard
from src.utils import logger
from src.utils.audio_utils import load_wav, export_chunk, slice_audio, normalize_audio, trim_silence


# ---------------------------------------------------------------------------- #
#  텍스트 정제 및 병합                                                            #
# ---------------------------------------------------------------------------- #

def clean_text(text: str) -> str:
    """
    STT 학습에 불필요한 노이즈 태그를 제거한다.
    제거 대상: [음악], (웃음), <c> HTML 태그, 음표, 다중 공백
    """
    # 줄바꿈 문자를 공백으로 치환하여 단일 라인으로 만듦
    text = text.replace("\n", " ")
    # VTT HTML 태그 제거 (예: <c>, </c>)
    text = re.sub(r"<[^>]+>", "", text)
    # 대괄호·소괄호 표현 제거 (예: [음악], (웃음))
    text = re.sub(r"\[.*?\]|\(.*?\)", "", text)
    # 음표 기호 및 HTML 공백 엔티티 제거
    text = text.replace("♪", "").replace("&nbsp;", " ")
    # 연속 공백을 단일 공백으로 정규화하고 앞뒤 공백 제거
    text = re.sub(r"\s+", " ", text).strip()
    return text

def remove_fillers(text: str) -> str:
    """한국어 및 슈카 특화 추임새(Filler)를 대폭 제거한다."""
    # 슈카 아저씨 및 일반 한국어 다빈도 추임새
    fillers = [
        "음", "어", "그", "아니", "이제", "막", "근데", "사실", "어떻게", "보면",
        "약간", "그게", "진짜", "그니까", "막말로", "뭐", "뭐냐", "일단", "그다음에"
    ]
    # 단어 경계(\b)와 문장 부호를 고려한 정규식
    for f in fillers:
        text = re.sub(rf"\b{f}[,\.]*(?=\s|$)", "", text)
    return re.sub(r"\s+", " ", text).strip()

def standardize_numbers(text: str) -> str:
    """숫자와 단위를 표준화한다."""
    # 예: '1,000' -> '1000'
    text = re.sub(r"(\d),(\d)", r"\1\2", text)
    # 기호 변환
    text = text.replace("%", "퍼센트").replace("$", "달러")
    return text

def merge_texts(old_text: str, new_text: str) -> str:
    """
    유튜브 자동 자막의 특징(이전 텍스트 반복)을 고려하여 중복 없이 병합한다.
    글자 단위로 겹치는 구간을 찾아 가장 긴 일치 구간을 제거한다.
    """
    if not old_text: return new_text
    if not new_text: return old_text
    
    # 1. 두 텍스트가 완전히 포함 관계인 경우
    if old_text in new_text: return new_text
    if new_text in old_text: return old_text
    
    # 2. 글자 단위 매칭 (가장 긴 접미사-접두사 일치 확인)
    # 최소 2글자 이상 겹칠 때만 처리 (너무 짧으면 우연일 수 있음)
    max_overlap = 0
    min_len = min(len(old_text), len(new_text))
    
    for i in range(min_len, 1, -1):
        if old_text.endswith(new_text[:i]):
            max_overlap = i
            break
            
    if max_overlap > 0:
        return old_text + new_text[max_overlap:]
    
    # 3. 어절 단위 매칭 (글자 단위 실패 시 대비)
    old_words = old_text.split()
    new_words = new_text.split()
    word_overlap = 0
    for i in range(min(len(old_words), len(new_words)), 0, -1):
        if old_words[-i:] == new_words[:i]:
            word_overlap = i
            break
            
    if word_overlap > 0:
        return " ".join(old_words + new_words[word_overlap:])
    
    # 겹치는 게 전혀 없으면 공백으로 연결
    return old_text + " " + new_text


# ---------------------------------------------------------------------------- #
#  VTT 파싱                                                                      #
# ---------------------------------------------------------------------------- #

@exception_guard(location="parse_vtt() -> webvtt 파싱")
def parse_vtt(vtt_path: str) -> List[Dict]:
    """
    VTT 파일을 파싱하여 [{'start_ms', 'end_ms', 'text'}] 리스트를 반환한다.
    빈 텍스트 캡션은 자동으로 제거한다.
    """
    # VTT 파일이 실제로 존재하는지 확인
    if not os.path.exists(vtt_path):
        raise TranscriptError(f"VTT 파일 없음: {vtt_path}")

    # 유효한 캡션 딕셔너리를 담을 리스트
    captions = []
    # webvtt-py 라이브러리로 VTT 파일의 각 캡션을 순회
    last_raw_text = ""
    for cap in webvtt.read(vtt_path):
        # 원본 텍스트를 정제
        raw_text = cap.text.strip()
        # 이전 캡션과 내용이 거의 같으면 중복으로 간주하고 스킵
        if raw_text == last_raw_text:
            continue
        
        text = clean_text(raw_text)
        
        # 정제 후 텍스트가 비어있으면 해당 캡션은 건너뜀
        if not text:
            continue
            
        captions.append({
            "start_ms": _time_to_ms(cap.start),
            "end_ms"  : _time_to_ms(cap.end),
            "text"    : text,
            "raw"     : raw_text # 중복 체크용
        })
        last_raw_text = raw_text
        
    return captions


def _time_to_ms(time_str: str) -> int:
    """'HH:MM:SS.mmm' 또는 'MM:SS.mmm' 형식을 밀리초로 변환한다."""
    # 콤마를 소수점으로 통일 후 콜론 기준으로 분리
    parts = time_str.replace(",", ".").split(":")
    if len(parts) == 3:
        # HH:MM:SS.mmm 형식
        h, m, s = parts
    else:
        # MM:SS.mmm 형식 (시간 없음)
        h, m, s = 0, parts[0], parts[1]
    # 초와 밀리초 분리 (소수점 이하 최대 3자리, 없으면 "0" 추가)
    sec, ms_part = (s.split(".") + ["0"])[:2]
    # 시·분·초·밀리초를 모두 밀리초 단위로 환산하여 합산
    total_ms = (
        int(h) * 3_600_000
        + int(m) * 60_000
        + int(sec) * 1_000
        + int(ms_part[:3].ljust(3, "0"))  # 밀리초 자릿수를 3자리로 맞춤
    )
    return total_ms


# ---------------------------------------------------------------------------- #
#  청크 분할 및 저장                                                              #
# ---------------------------------------------------------------------------- #

@exception_guard(location="process_video() -> 청크 분할")
def process_video(
    video_id  : str,
    date_str  : str,   # 'YYYYMMDD'
    audio_path: str,
    vtt_path  : str,
    mode      : str = "basic"
) -> List[Dict[str, str]]:
    """
    단일 영상의 오디오를 VTT 기반으로 청크로 분할하고,
    metadata.csv 레코드 리스트를 반환한다.

    Returns:
        [{'file_name': '2026/04/23/{id}/chunks/chunk_0001.wav',
          'transcription': '...'}]
    """
    # VTT 파싱 결과 캡션 리스트 수신
    captions = parse_vtt(vtt_path)
    if not captions:
        # 유효 자막이 없으면 처리할 것이 없으므로 빈 리스트 반환
        logger.warning(f"유효한 자막 없음, 스킵: {video_id}")
        return []

    # 오디오 파일을 AudioSegment 객체로 로드
    audio = load_wav(audio_path)
    if audio is None:
        return []

    # 날짜 기반 청크 저장 폴더 경로 계산
    y, m, d = date_str[:4], date_str[4:6], date_str[6:8]
    chunks_abs_dir = os.path.join(DATASET_DIR, y, m, d, video_id, "chunks")
    # 청크 저장 디렉터리 생성 (이미 있으면 무시)
    os.makedirs(chunks_abs_dir, exist_ok=True)

    # 설정에서 최대 청크 길이(밀리초) 로드
    max_dur = CFG["max_chunk_duration_ms"]
    
    # [심화 모드 전용 설정]
    if mode == "advanced":
        logger.info(f"[{video_id}] 심화(Advanced) 모드 전처리 적용 중...")
        max_dur = 15000  # 15초로 단축 (더 많은 데이터셋 확보)
        audio = normalize_audio(audio) # 전체 음량 평준화
    
    # metadata.csv 에 추가될 레코드 목록
    entries = []
    # 현재 누적 중인 청크의 텍스트
    cur_text = ""
    # 현재 청크의 시작 밀리초 (-1은 아직 초기화 전을 의미)
    cur_start_ms = -1
    # 현재 청크의 끝 밀리초
    cur_end_ms = 0
    # 저장된 청크 번호 (파일명 생성에 사용)
    chunk_idx = 0

    def _flush(start_ms: int, end_ms: int, text: str) -> None:
        """현재 누적된 청크를 저장하는 내부 헬퍼."""
        # nonlocal 선언으로 외부 스코프의 chunk_idx 를 수정 가능하게 함
        nonlocal chunk_idx
        # 4자리 0패딩 청크 파일명 생성 (예: chunk_0001.wav)
        chunk_filename = f"chunk_{chunk_idx:04d}.wav"
        # 절대 경로로 저장 위치 결정
        chunk_abs = os.path.join(chunks_abs_dir, chunk_filename)
        # file_name에는 dataset/ 기준 상대 경로를 저장
        chunk_rel = os.path.join(y, m, d, video_id, "chunks", chunk_filename)

        # 오디오 슬라이싱 (앞뒤 패딩 포함)
        # [심화 모드 전용] 스마트 오버랩 적용 (앞으로 2초 더 가져옴)
        actual_start = start_ms
        if mode == "advanced" and start_ms > 2000:
            actual_start = start_ms - 2000
            
        sliced = slice_audio(audio, actual_start, end_ms)
        
        # [심화 모드 전용] 오디오 고도화 보정
        if mode == "advanced":
            # 1. 저주파 노이즈 억제 (High-pass filter 느낌)
            sliced = sliced.low_pass_filter(5000).high_pass_filter(200)
            # 2. 침묵 제거
            sliced = trim_silence(sliced)
            # 3. 텍스트 추임새 및 숫자 표준화
            text = remove_fillers(text)
            text = standardize_numbers(text)

        # WAV 파일로 저장 성공 시 entries 에 레코드 추가
        if export_chunk(sliced, chunk_abs):
            entries.append({"file_name": chunk_rel, "transcription": text})
            chunk_idx += 1

    # 모든 캡션을 순서대로 순회하며 청크를 누적·저장
    for cap in captions:
        # 현재 캡션의 시작·끝 밀리초와 정제된 텍스트 추출
        start_ms = cap["start_ms"]
        end_ms   = cap["end_ms"]
        text     = cap["text"]

        if cur_start_ms == -1:
            # 첫 캡션: 시작점 초기화
            cur_start_ms = start_ms
            cur_text     = text
            cur_end_ms   = end_ms
            continue

        # [전문가 모드] 문장 경계 보호 및 동적 분할 로직
        duration = end_ms - cur_start_ms
        is_sentence_end = any(cur_text.rstrip().endswith(p) for p in [".", "?", "!", " "])
        
        # 분할 결정 로직
        should_flush = False
        if mode == "advanced":
            # 심화 모드: 15초가 넘었을 때 문장이 끝났거나, 혹은 도저히 안 끝나서 30초를 넘겼을 때만 자름
            if duration > 15000 and is_sentence_end:
                should_flush = True
            elif duration > 30000: # 문장이 안 끝나도 30초면 강제 절삭 (Whisper 한계)
                should_flush = True
        else:
            # 기본 모드: 그냥 25초 넘으면 무조건 자름
            if duration > max_dur:
                should_flush = True

        if should_flush:
            # 현재까지 누적분을 저장 후 초기화
            _flush(cur_start_ms, cur_end_ms, cur_text)
            cur_start_ms = start_ms
            cur_end_ms   = end_ms
            cur_text     = text
        else:
            # 텍스트 병합 시 중복 제거 로직 적용
            cur_text = merge_texts(cur_text, text)
            cur_end_ms = end_ms

    # 루프 종료 후 남은 마지막 청크 저장
    if cur_text and cur_start_ms != -1:
        _flush(cur_start_ms, cur_end_ms, cur_text)

    logger.info(f"[{video_id}] 청크 {chunk_idx}개 생성 완료")
    return entries
