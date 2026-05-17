import os
import glob

folder_path = "C:/ameva/AMEVA-STT-Trainer/dataset/2026/05/09"
normalized_path = os.path.normpath(folder_path)

print("1. 원본 경로 테스트:")
pattern1 = os.path.join(folder_path, "**", "*.wav")
print(f"패턴: {pattern1}")
files1 = glob.glob(pattern1, recursive=True)
print(f"찾은 파일 수: {len(files1)}")

print("\n2. 정규화 경로 테스트:")
pattern2 = os.path.join(normalized_path, "**", "*.wav")
print(f"패턴: {pattern2}")
files2 = glob.glob(pattern2, recursive=True)
print(f"찾은 파일 수: {len(files2)}")
if files2:
    print(f"예시 파일: {files2[0]}")
