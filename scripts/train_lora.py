"""
scripts/train_lora.py
[하위 호환성 브릿지] 최신 MLOps 표준 학습 가동 엔진(02_start_training.py)으로 안전하게 위임 가동합니다.
기존 외부 CLI 호출이나 CI/CD 자동화 시스템의 중단 없는 무장애 연동을 보장합니다.
"""
import sys
import subprocess
import os

def main():
    print("\n" + "=" * 80)
    print("📢 [AMEVA Legacy Bridge] scripts/train_lora.py 실행 감지")
    print("💡 안전한 MLOps 2단계 표준 엔진(scripts/02_start_training.py)으로 자동 위임 가동합니다.")
    print("   이 조치를 통해 가상 메모리 에러 방지(IterableDataset), 대시보드 실시간 메트릭 스트리밍이 가동됩니다.")
    print("=" * 80 + "\n")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_script = os.path.join(script_dir, "02_start_training.py")

    cmd = [sys.executable, target_script]
    args = sys.argv[1:]
    
    # 레거시 호출은 대시보드 없이 개별 CLI 구동이 기본이므로, 중복 전처리 빌드 스킵(--skip) 자동 부여
    if "--skip" not in args:
        args.append("--skip")
    cmd.extend(args)

    try:
        res = subprocess.run(cmd)
        sys.exit(res.returncode)
    except Exception as e:
        print(f"❌ [Bridge Error] 2단계 표준 엔진 위임 호출 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
