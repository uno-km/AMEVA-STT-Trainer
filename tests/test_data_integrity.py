"""
tests/test_data_integrity.py
데이터 전처리 및 연속 반복 감지 알고리즘 검증을 위한 단위 테스트(Unit Test) 스위트.
"""
import re
import unittest

def detect_adjacent_repeat(text: str, n_set=(1, 2, 3)) -> bool:
    """
    단일 텍스트 청크에서 정규화된 한글/영문/숫자 토큰 단위로
    인접 비중첩 n-gram(1~3 gram)의 연속 반복 등장 여부를 판정한다.
    """
    # 1. 특수문자, 문장부호, 침묵 마커(. .) 등을 무시하기 위해 정규식 기반 토큰화 수행
    words = [w for w in str(text).split() if w and re.match(r'^[a-zA-Z0-9가-힣]+$', w)]
    if len(words) < 2:
        return False
        
    # 2. 지정된 gram 수 단위로 슬라이딩하며 연속 반복 패턴 검사 (Adjacent non-overlapping n-gram)
    for n in n_set:
        if len(words) >= n * 2:
            grams = [tuple(words[i:i+n]) for i in range(len(words)-n+1)]
            for i in range(len(grams) - n):
                if grams[i] == grams[i+n]:
                    return True
    return False


class TestDataRepetitionIntegrity(unittest.TestCase):
    """데이터 전처리 및 연속 반복 알고리즘 정합성 검증 테스트 클래스"""

    def test_consecutive_1gram_repeat_detected(self):
        """1-gram 단어 연속 반복 감지 테스트 (예: '두산이야 두산이야')"""
        text = "두산이야 두산이야"
        self.assertTrue(detect_adjacent_repeat(text))

    def test_consecutive_2gram_repeat_detected(self):
        """2-gram 구문 연속 반복 감지 테스트 (예: '정말 대단해 정말 대단해')"""
        text = "정말 대단해 정말 대단해"
        self.assertTrue(detect_adjacent_repeat(text))

    def test_consecutive_3gram_repeat_detected(self):
        """3-gram 연속 반복 감지 테스트 (예: '오피셜 최강국 오피셜 최강국')"""
        text = "오피셜 최강국 오피셜 최강국"
        self.assertTrue(detect_adjacent_repeat(text))

    def test_normal_text_no_repeat_ignored(self):
        """반복이 없는 일반 텍스트 감지 테스트 (False 기대)"""
        text = "자, 두 번째 얘기는 여러분들 좋아하는 얘기입니다."
        self.assertFalse(detect_adjacent_repeat(text))

    def test_punctuation_silence_not_counted(self):
        """침묵 마커(. . .) 및 문장부호 연속 등장 시 오탐 배제 테스트 (False 기대)"""
        text = "참고로 . . . 야구장 여신이 뉴스에 나왔어 ."
        self.assertFalse(detect_adjacent_repeat(text))


if __name__ == "__main__":
    unittest.main()
