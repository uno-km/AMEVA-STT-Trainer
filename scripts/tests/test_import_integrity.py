"""
scripts/tests/test_import_integrity.py
AMEVA-STT-Trainer QA Automation: Python File Compile & Import Smoke Tester
- Blacklists virtual environments, third-party libraries, and legacy code.
- Uses strict try-except blocks to catch compile-time and import-time tracebacks.
"""
import os
import sys
import py_compile
import traceback
import importlib.util

# 블랙리스트 디렉터리 목록 (스캔 대상에서 완전히 제외)
BLACKLIST_DIRS = {
    "venv",
    ".git",
    "third_party",
    "legacy",
    "__pycache__",
    "build",
    "dist",
    ".gemini"
}

def scan_python_files(root_path):
    py_files = []
    for root, dirs, files in os.walk(root_path):
        # 블랙리스트에 걸리는 디렉터리 하위 스캔 차단
        dirs[:] = [d for d in dirs if d not in BLACKLIST_DIRS]
        for file in files:
            if file.endswith(".py"):
                # 현재 실행 중인 테스트 스크립트 자신은 제외
                full_path = os.path.abspath(os.path.join(root, file))
                if not full_path.endswith("test_import_integrity.py"):
                    py_files.append(full_path)
    return py_files

def run_smoke_test():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    print("\n" + "=" * 80)
    print(">>> QA Smoke Test: Python Syntax & Load-Time Import Integrity Scan")
    print(f"[*] Scanning under Project Root: {project_root}")
    print("=" * 80 + "\n")

    py_files = scan_python_files(project_root)
    print(f"[*] Target Python files found: {len(py_files)}\n")

    failed_count = 0
    passed_count = 0

    for idx, file_path in enumerate(py_files, 1):
        rel_path = os.path.relpath(file_path, project_root)
        print(f"[{idx:02d}/{len(py_files):02d}] Verifying: {rel_path} ...", end="", flush=True)

        # 1. 정적 컴파일 및 문법 검수
        try:
            py_compile.compile(file_path, doraise=True)
        except Exception as err:
            print(" [FAILED: Syntax]")
            print(f"    executed python file : {rel_path}\n    generated error : {err}\n")
            failed_count += 1
            continue

        # 2. 동적 모듈 로드 및 임포트 검수 (src 라이브러리 디렉토리 대상)
        if "src" in file_path:
            # 스크립트 실행 형태의 메인 파일은 제외
            basename = os.path.basename(file_path)
            if basename in ["dashboard.py", "main.py"]:
                print(" [PASS: Static]")
                passed_count += 1
                continue

            rel_no_ext = os.path.splitext(rel_path)[0]
            module_name = rel_no_ext.replace(os.sep, ".")
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec is None or spec.loader is None:
                    raise ImportError("Failed to load module spec")
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                print(" [PASS]")
                passed_count += 1
            except Exception as err:
                print(" [FAILED: Import]")
                tb_str = "".join(traceback.format_exception(*sys.exc_info()))
                print(f"    executed python file : {rel_path}\n    generated error :\n{tb_str}\n")
                failed_count += 1
        else:
            print(" [PASS: Static]")
            passed_count += 1

    print("\n" + "=" * 80)
    print(">>> QA Verification Summary")
    print(f"[*] Total Passed: {passed_count}/{len(py_files)}")
    print(f"[*] Total Failed: {failed_count}/{len(py_files)}")
    print("=" * 80 + "\n")

    if failed_count > 0:
        print("[!] QA Test: FAILED due to compilation or import errors.")
        sys.exit(1)
    else:
        print("[+] QA Test: SUCCESS! All python files are perfectly compiled and importable.")
        sys.exit(0)

if __name__ == "__main__":
    run_smoke_test()
