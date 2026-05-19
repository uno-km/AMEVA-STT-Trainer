#!/usr/bin/env python
"""
run_all_tests.py
Unified Test Runner for AMEVA-STT-Trainer QA verification.
Executes all codebase tests in isolated subprocesses using the current Python interpreter.
"""
import sys
import os
import subprocess

def main():
    project_root = os.path.abspath(os.path.dirname(__file__))
    
    # 4개 핵심 테스트 파일 리스트
    test_files = [
        "scripts/tests/test_import_integrity.py",
        "scripts/tests/test_database_integrity.py",
        "scripts/tests/test_api_endpoints.py",
        "tests/test_data_integrity.py"
    ]
    
    print("\n" + "=" * 80)
    print(">>> AMEVA STT-Trainer: Unified Test Runner (Unified pytests equivalent)")
    print(f"[*] Python Interpreter: {sys.executable}")
    print(f"[*] Project Root: {project_root}")
    print("=" * 80 + "\n")
    
    results = {}
    failed = False
    
    for idx, test_file in enumerate(test_files, 1):
        full_path = os.path.join(project_root, test_file.replace("/", os.sep))
        print(f"\n[{idx}/{len(test_files)}] Running Test Script: {test_file}")
        print("-" * 60)
        
        if not os.path.exists(full_path):
            print(f"[ERROR] Test file not found: {test_file}")
            results[test_file] = "NOT FOUND"
            failed = True
            continue
            
        # 서브프로세스로 테스트 실행 (현재 사용 중인 python 인터프리터 주입)
        try:
            args = [sys.executable, full_path]
            res = subprocess.run(args, cwd=project_root)
            if res.returncode == 0:
                print(f"\n[PASS] {test_file}: PASSED")
                results[test_file] = "PASSED"
            else:
                print(f"\n[FAIL] {test_file}: FAILED (Exit Code: {res.returncode})")
                results[test_file] = f"FAILED (Exit Code: {res.returncode})"
                failed = True
        except Exception as e:
            print(f"\n[ERROR] {test_file}: EXCEPTION ({str(e)})")
            results[test_file] = f"EXCEPTION ({str(e)})"
            failed = True
            
    print("\n" + "=" * 80)
    print(">>> Test Run Summary")
    print("=" * 80)
    for test_file, status in results.items():
        print(f" - {test_file:50s} : {status}")
    print("=" * 80 + "\n")
    
    if failed:
        print("[!] Unified Test Run: FAILED.")
        sys.exit(1)
    else:
        print("[+] Unified Test Run: SUCCESS! All tests passed successfully.")
        sys.exit(0)

if __name__ == "__main__":
    main()
