"""
scripts/export_gguf.py
[안내] Whisper 모델을 GGUF 포맷으로 변환하기 위한 절차 가이드.
직접 변환 로직을 수행하지 않고, 필요한 명령어들을 출력하여 사용자를 안내함.
"""
import os

def main():
    # 터미널 가독성을 위한 상단 경계선 출력
    print("=" * 60)
    print("  Whisper.cpp (GGUF) Conversion Guide")
    print("=" * 60)
    
    # GGUF 변환을 위한 단계별 안내 문구 출력
    print("\nTo convert your merged model to GGUF format for use in whisper.cpp:")
    
    # 1단계: 변환 도구 획득 (공식 whisper.cpp 저장소)
    print("\n1. Clone whisper.cpp repository:")
    print("   git clone https://github.com/ggerganov/whisper.cpp.git")
    
    # 2단계: 변환 스크립트 실행에 필요한 라이브러리 설치
    print("\n2. Install conversion dependencies (if not already met):")
    print("   pip install numpy sentencepiece")
    
    # 3단계: HuggingFace 포맷 모델을 GGUF 바이너리로 변환하는 명령어
    print("\n3. Run the conversion script within whisper.cpp folder:")
    print("   python whisper.cpp/models/convert-h5-to-gguf.py outputs/merged_model/ .")
    
    # 4단계: 모델 용량 최적화를 위한 4비트 양자화 명령어 (whisper.cpp 빌드 후 실행 가능)
    print("\n4. Quantize the model (after building whisper.cpp):")
    print("   ./whisper.cpp/quantize ggml-model.bin ggml-model-q4_0.bin q4_0")
    
    # 현재 프로젝트 내 병합된 모델의 위치를 다시 한번 명시
    print("\n" + "-" * 30)
    print("Current Merged Model Path: outputs/merged_model/")
    print("-" * 30)

if __name__ == "__main__":
    # 가이드 출력 실행
    main()
