"""
setup/download_models_interactive.py
설정 및 설치 과정에서 대화형(y/n)으로 Whisper Tiny/Small 모델을 미리 다운로드할 수 있도록 지원하는 스크립트입니다.
"""
import sys
import os

# 프로젝트 루트를 PATH에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Hugging Face 모델 캐시 디렉토리를 외부 공통 폴더로 지정
os.environ["HF_HOME"] = r"C:\ameva\models\stt"

def download_model(model_id: str):
    print(f"\n[정보] {model_id} 모델 다운로드/확인 시작...")
    try:
        from transformers import WhisperForConditionalGeneration, WhisperProcessor, WhisperTokenizer, WhisperFeatureExtractor
        
        print(f"  -> [{model_id}] 모델 가중치(Weights) 확인 및 다운로드 중...")
        WhisperForConditionalGeneration.from_pretrained(model_id, local_files_only=False)
        
        print(f"  -> [{model_id}] 토크나이저 및 프로세서 파일 확인 중...")
        WhisperProcessor.from_pretrained(model_id, local_files_only=False)
        WhisperTokenizer.from_pretrained(model_id, local_files_only=False)
        WhisperFeatureExtractor.from_pretrained(model_id, local_files_only=False)
        
        print(f"[✓] {model_id} 모델 및 프로세서 확인/다운로드 완료!")
    except Exception as e:
        print(f"[오류] {model_id} 다운로드 실패: {e}")

def ask_yes_no(question: str, default: str = "n") -> bool:
    hint = "[y/N]" if default.lower() == "n" else "[Y/n]"
    val = input(f"{question} {hint}: ").strip().lower()
    if not val:
        val = default.lower()
    return val.startswith("y")

def main():
    print("\n" + "=" * 60)
    print("   Whisper 로컬 모델 다운로드 및 검증 (대화형)")
    print("=" * 60)
    print("이 도구는 오프라인/인터넷 차단 환경에서 정상 구동되도록 모델을 로컬 캐시에 저장합니다.")
    print("이미 로컬에 다운로드되어 있는 경우 자동으로 확인(Skip) 처리됩니다.")
    
    try:
        # 1. Tiny Model Download Query
        if ask_yes_no("Whisper Tiny 모델(openai/whisper-tiny)을 확인 및 다운로드하시겠습니까?", default="y"):
            download_model("openai/whisper-tiny")
        else:
            print("[패스] Tiny 모델 다운로드를 생략합니다.")
            
        # 2. Small Model Download Query
        if ask_yes_no("Whisper Small 모델(openai/whisper-small)을 확인 및 다운로드하시겠습니까?", default="y"):
            download_model("openai/whisper-small")
        else:
            print("[패스] Small 모델 다운로드를 생략합니다.")
            
    except KeyboardInterrupt:
        print("\n[정보] 사용자에 의해 다운로드가 취소되었습니다.")
    
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()

