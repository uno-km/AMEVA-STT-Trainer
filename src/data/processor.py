"""
src/data/processor.py
STT 학습용 데이터셋 구축을 위한 전문 전처리 엔진 (최종 무결성 패치).
공백/구두점 차이로 인한 텍스트 손상을 방지하기 위해 정교한 중복 제거 로직을 적용함.
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
#  텍스트 정제 및 중복 제거 로직 (Integrity Enhanced)                            #
# ---------------------------------------------------------------------------- #

def clean_text(text: str, for_training: bool = True) -> str:
    """STT 전처리: 학습용은 정합성 유지, 자막용은 가독성 위주."""
    text = text.replace("\n", " ")
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("♪", "").replace("&nbsp;", " ")

    def paren_filter(m):
        inside = (m.group(1) or m.group(2) or "").strip()
        if not inside: return ""
        if re.fullmatch(r"[A-Z0-9][A-Z0-9\-\.\s]{0,20}", inside):
            return inside 
        tags = ["음악", "박수", "웃음", "환호", "BGM", "Laughter", "Applause"]
        if any(tag in inside for tag in tags):
            return ""
        return ""

    text = re.sub(r"\[(.*?)\]|\((.*?)\)", paren_filter, text)
    text = re.sub(r"(\d),(\d)", r"\1\2", text)
    text = text.replace("%", "퍼센트").replace("$", "달러")
    text = re.sub(r"([,\.?!])([가-힣a-zA-Z])", r"\1 \2", text)

    if not for_training:
        # 가독성 전용: 추임새 제거
        fillers = [
            "음", "어", "그", "아니", "이제", "막", "근데", "사실", "사실은", "어떻게", "보면",
            "약간", "그게", "진짜", "그니까", "그러니까", "막말로", "뭐", "뭐냐", "일단", "그다음에",
            "자", "아", "하", "참", "어우", "야", "저기", "그죠", "거죠", "에"
        ]
        for f in fillers:
            text = re.sub(rf"(^|\s){f}[,\.\!\?]*(?=\s|$)", " ", text)

    return re.sub(r"\s+", " ", text).strip()

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


# ---------------------------------------------------------------------------- #
#  VTT 파싱                                                                      #
# ---------------------------------------------------------------------------- #

@exception_guard(location="parse_vtt() -> webvtt 파싱")
def parse_vtt(vtt_path: str) -> List[Dict]:
    if not os.path.exists(vtt_path):
        raise TranscriptError(f"VTT 파일 없음: {vtt_path}")

    captions = []
    last_tail = "" # 500자 보관
    
    for cap in webvtt.read(vtt_path):
        raw_text = cap.text.strip()
        if not raw_text: continue
        
        # 1. 텍스트 정제
        text_full = clean_text(raw_text, for_training=True)
        
        # 2. 정교한 중복 제거 (이전 텍스트와의 비교)
        new_only = get_new_only(last_tail, text_full)
        if not new_only: continue
        
        captions.append({
            "start_ms": _time_to_ms(cap.start),
            "end_ms"  : _time_to_ms(cap.end),
            "text": new_only,
            "text_clean": clean_text(new_only, for_training=False)
        })
        
        # 다음 비교를 위해 꼬리 업데이트 (공백 포함 원문 유지)
        last_tail = (last_tail + " " + new_only)[-500:].strip()
        
    return captions

def _time_to_ms(time_str: str) -> int:
    parts = time_str.replace(",", ".").split(":")
    h, m, s = (parts if len(parts) == 3 else [0] + parts)
    sec, ms_part = (s.split(".") + ["0"])[:2]
    return (int(h) * 3600000 + int(m) * 60000 + int(sec) * 1000 + int(ms_part[:3].ljust(3, "0")))


# ---------------------------------------------------------------------------- #
#  청크 분할 및 저장                                                              #
# ---------------------------------------------------------------------------- #

@exception_guard(location="process_video() -> 청크 분할")
def process_video(
    video_id: str, date_str: str, audio_path: str, vtt_path: str, mode: str = "basic", output_dir: Optional[str] = None
) -> List[Dict[str, str]]:
    captions = parse_vtt(vtt_path)
    if not captions: return []
    audio = load_wav(audio_path)
    if audio is None: return []

    y, m, d = date_str[:4], date_str[4:6], date_str[6:8]
    # 격리된 output_dir을 지정했다면 해당 폴더 기준으로 chunks 디렉토리 형성
    base_out_dir = output_dir if output_dir else DATASET_DIR
    chunks_abs_dir = os.path.join(base_out_dir, y, m, d, video_id, "chunks")
    os.makedirs(chunks_abs_dir, exist_ok=True)

    max_dur = min(CFG["max_chunk_duration_ms"], 30000)
    entries, cur_text, cur_text_clean, cur_start_ms, cur_end_ms, chunk_idx = [], "", "", -1, 0, 0

    def _flush(start_ms, end_ms, text, text_clean):
        nonlocal chunk_idx
        chunk_filename = f"chunk_{chunk_idx:04d}.wav"
        chunk_abs = os.path.join(chunks_abs_dir, chunk_filename)
        chunk_rel = os.path.join(y, m, d, video_id, "chunks", chunk_filename)
        
        sliced = slice_audio(audio, start_ms, end_ms)
        
        # [고도화] 오디오 트리밍(trim_silence)을 먼저 수행하여 절대 노이즈 플로어를 유지한 채 잘라내고,
        # 잘린 최종 음성 파형에 대해 Peak Normalization(normalize_audio)을 가동하여 노이즈 증폭 문제를 원천 방지함!
        sliced = trim_silence(sliced)
        sliced = normalize_audio(sliced)
        
        if export_chunk(sliced, chunk_abs):
            entries.append({
                "file_name": chunk_rel, 
                "transcription": re.sub(r"\s+", " ", text).strip(), 
                "transcription_clean": re.sub(r"\s+", " ", text_clean).strip()
            })
            chunk_idx += 1

    for cap in captions:
        start_ms, end_ms, text, text_cln = cap["start_ms"], cap["end_ms"], cap["text"], cap["text_clean"]
        
        # [고도화] 1단계: 원본 자막 자체가 이미 깨진 데이터(역전/길이 0)인 경우 원천 스킵
        if end_ms <= start_ms:
            continue
            
        # 2단계: 자막 타임라인 겹침 보정 (이전 캡션 범위 내에 속할 때만 clamp 하되, clamp 후 음수 슬라이스 방지 가드 탑재)
        if cur_start_ms != -1 and start_ms < cur_end_ms:
            start_ms = cur_end_ms
            if end_ms <= start_ms:
                continue
        
        if cur_start_ms == -1:
            cur_start_ms, cur_text, cur_text_clean, cur_end_ms = start_ms, text, text_cln, end_ms
            continue

        duration = end_ms - cur_start_ms
        
        # [고도화] 3단계: 겹침 보정 이전의 오리지널 타임스탬프로 정확한 캡션 스트림 침묵 갭(Silence Gap) 스캔
        caption_gap_ms = cap["start_ms"] - cur_end_ms
        is_silence_gap = caption_gap_ms > 1500
        
        # 2. 고도화된 한국어 종결 및 인용부호 닫힘 문맥 경계(Sentence Boundary) 감지
        is_sentence_end = bool(re.search(r"(다|요|죠|니|까)[\.\?\!\s]*[\'\"\]\)]*$", cur_text.strip())) or cur_text.strip().endswith((".", "?", "!"))
        
        # 3. 복합 하이브리드 청킹 판단 트리거
        # (A) Whisper 최대 인코더 윈도우 한계인 30초에 도달했을 때 (max_dur)
        # (B) 10초 이상의 유효 발화가 채워진 상태에서 1.5초 이상의 대화 공백이 탐지되어 단락이 전환될 때
        # (C) 15초 이상의 유효 발화가 채워진 상태에서 문장 종결 어미가 완성되어 문맥이 끊어지지 않게 마감될 때
        should_flush = (
            duration > max_dur or 
            (duration > 10000 and is_silence_gap) or 
            (duration > 15000 and is_sentence_end)
        )
        
        if should_flush:
            _flush(cur_start_ms, cur_end_ms, cur_text, cur_text_clean)
            cur_start_ms, cur_text, cur_text_clean, cur_end_ms = start_ms, text, text_cln, end_ms
        else:
            cur_text += " " + text
            cur_text_clean += " " + text_cln
            cur_end_ms = end_ms

    if cur_text and cur_start_ms != -1:
        _flush(cur_start_ms, cur_end_ms, cur_text, cur_text_clean)
    return entries
