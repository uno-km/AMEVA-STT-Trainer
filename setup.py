"""
setup.py
AMEVA-STT-Trainer Unified Auto-Installer Launcher.
Detects OS in runtime and routes execution to OS-specific hidden scripts:
  - Windows: setup/setup_env.ps1
  - Linux/macOS: setup/setup_env.sh
"""
import os
import sys
import platform
import subprocess

def main():
    print("=" * 60)
    print("   AMEVA-STT-Trainer Unified Setup Launcher")
    print("=" * 60)
    
    current_os = platform.system()
    print(f"[INFO] Detected Operating System: {current_os}")
    
    # Paths to the modularized environment scripts under setup/
    ps_script = os.path.join("setup", "setup_env.ps1")
    sh_script = os.path.join("setup", "setup_env.sh")
    
    if current_os == "Windows":
        print("\n[INFO] Launching Windows PowerShell Environment Setup...")
        if not os.path.exists(ps_script):
            print(f"[ERROR] Modularized script not found at: {ps_script}")
            sys.exit(1)
        try:
            # Execute Windows PowerShell script with Bypass policy
            cmd = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", ps_script]
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] PowerShell setup execution failed: {e}")
            sys.exit(1)
        except FileNotFoundError:
            print("\n[ERROR] PowerShell executable (powershell.exe) was not found in PATH.")
            sys.exit(1)
    else:
        print("\n[INFO] Launching Unix Bash Environment Setup...")
        if not os.path.exists(sh_script):
            print(f"[ERROR] Modularized script not found at: {sh_script}")
            sys.exit(1)
        try:
            # Set executable permissions on the shell script
            os.chmod(sh_script, 0o755)
            # Execute Bash script
            cmd = ["bash", sh_script]
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] Bash setup execution failed: {e}")
            sys.exit(1)
        except FileNotFoundError:
            print("\n[ERROR] Bash executable was not found in PATH.")
            sys.exit(1)

if __name__ == "__main__":
    main()
