import os
import glob

folder_path = "C:/ameva/AMEVA-STT-Trainer/dataset/2026/05/09"
video_list = []
skipped_chunks = 0
skipped_no_vtt = 0

print("🔍 지능형 디렉터리 매칭 시뮬레이션 시작...")
wav_files = glob.glob(os.path.join(folder_path, "**", "*.wav"), recursive=True)

for wav_path in wav_files:
    # 렉 유도 방지
    if "chunks" in wav_path.replace("\\", "/").split("/"):
        skipped_chunks += 1
        continue
        
    parent_dir = os.path.dirname(wav_path)
    video_id = os.path.basename(parent_dir)
    
    local_vtts = glob.glob(os.path.join(parent_dir, "*.vtt"))
    vtt_path = None
    
    if local_vtts:
        for vf in local_vtts:
            if os.path.basename(vf).startswith(video_id):
                vtt_path = vf
                break
        if not vtt_path and len(local_vtts) == 1:
            vtt_path = local_vtts[0]
            
    if vtt_path:
        video_list.append((video_id, "20260517", wav_path, vtt_path))
    else:
        skipped_no_vtt += 1

print(f"📊 시뮬레이션 요약:")
print(f"  - 전체 탐색된 .wav 개수: {len(wav_files)}")
print(f"  - chunks 폴더 스킵 개수: {skipped_chunks}")
print(f"  - 자막 매칭 실패 스킵 개수: {skipped_no_vtt}")
print(f"  - ✅ 최종 매칭 성공 개수 (video_list): {len(video_list)}")

if video_list:
    print(f"\n매칭 성공 샘플 3개:")
    for item in video_list[:3]:
        print(f"  ID: {item[0]} | WAV: {os.path.basename(item[2])} | VTT: {os.path.basename(item[3])}")
