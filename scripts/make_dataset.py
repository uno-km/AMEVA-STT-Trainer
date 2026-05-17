"""
scripts/make_dataset.py
[하위 호환성 브릿지] 최신 MLOps 표준 데이터셋 빌드 엔진(01_build_dataset.py)으로 안전하게 위임 가동합니다.
기존 외부 CLI 호출이나 CI/CD 자동화 시스템의 중단 없는 무장애 연동을 보장합니다.
"""
import sys
import subprocess
import os

def main():
    print("\n" + "=" * 80)
    print("📢 [AMEVA Legacy Bridge] scripts/make_dataset.py 실행 감지")
    print("💡 안전한 MLOps 1단계 표준 엔진(scripts/01_build_dataset.py)으로 자동 위임 가동합니다.")
    print("   이 조치를 통해 SQLite 실시간 기록, 정교한 중복 제거 및 무결성 검증이 자동 활성화됩니다.")
    print("=" * 80 + "\n")

    # 프로젝트 루트 기준 상대 경로로 01_build_dataset.py 탐색
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_script = os.path.join(script_dir, "01_build_dataset.py")

    cmd = [sys.executable, target_script]
    # 호출 시 넘어온 CLI 인수(--source_type, --folder, --url 등)를 그대로 표준 엔진에 포워딩
    cmd.extend(sys.argv[1:])

    try:
        res = subprocess.run(cmd)
        sys.exit(res.returncode)
    except Exception as e:
        print(f"❌ [Bridge Error] 1단계 표준 엔진 위임 호출 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
