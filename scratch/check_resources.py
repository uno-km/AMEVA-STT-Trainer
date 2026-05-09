import psutil
import os

def get_system_status():
    mem = psutil.virtual_memory()
    print(f"시스템 전체 메모리: {mem.total / 1024**3:.2f} GB")
    print(f"현재 사용 중인 메모리: {mem.used / 1024**3:.2f} GB ({mem.percent}%)")
    print("-" * 50)
    print(f"{'PID':>8} | {'CPU%':>6} | {'MEM%':>6} | {'Name'}")
    print("-" * 50)

    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            # cpu_percent는 처음 호출 시 0.0일 수 있으므로 한 번 더 호출하거나 interval을 줌
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # CPU 점유율이 0으로 잡히는 것 방지 위해 짧게 대기 후 재측정
    import time
    time.sleep(0.5)
    
    final_procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            final_procs.append(p.info)
        except:
            pass

    # 메모리 점유율 순으로 정렬
    sorted_procs = sorted(final_procs, key=lambda x: x['memory_percent'], reverse=True)
    
    for p in sorted_procs[:15]:
        name = p['name'][:25]
        print(f"{p['pid']:>8} | {p['cpu_percent']:>6.1f} | {p['memory_percent']:>6.1f} | {name}")

if __name__ == "__main__":
    get_system_status()
