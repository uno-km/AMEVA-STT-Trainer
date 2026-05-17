"""
scripts/merge_lora.py
[하위 호환성 브릿지] 최신 MLOps 표준 모델 추출 엔진(03_export_model.py)으로 안전하게 위임 가동합니다.
기존 외부 CLI 호출이나 CI/CD 자동화 시스템의 중단 없는 무장애 연동을 보장합니다.
"""
import sys
import subprocess
import os

def main():
    print("\n" + "=" * 80)
    print("📢 [AMEVA Legacy Bridge] scripts/merge_lora.py 실행 감지")
    print("💡 안전한 MLOps 3단계 표준 엔진(scripts/03_export_model.py)으로 자동 위임 가동합니다.")
    print("   이 조치를 통해 병합 완료에 따른 DB 상태 자동 업데이트 및 안전 해제 공정이 완료됩니다.")
    print("=" * 80 + "\n")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_script = os.path.join(script_dir, "03_export_model.py")

    cmd = [sys.executable, target_script]
    args = sys.argv[1:]
    
    # 레거시 merge 스크립트는 whisper.cpp 전용 양자화(quantization)를 수행하지 않으므로 --no-quantize 자동 부여
    if "--no-quantize" not in args:
        args.append("--no-quantize")
    cmd.extend(args)

    try:
        res = subprocess.run(cmd)
        sys.exit(res.returncode)
    except Exception as e:
        print(f"❌ [Bridge Error] 3단계 표준 엔진 위임 호출 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
