import os
import pandas as pd
from collections import Counter

METADATA_PATH = "dataset/metadata.csv"
DATASET_DIR = "dataset"

def full_investigation():
    print("=" * 60)
    print("Full Dataset Investigation (2,342 samples)")
    print("=" * 60)

    if not os.path.exists(METADATA_PATH):
        print("[ERROR] metadata.csv not found.")
        return

    df = pd.read_csv(METADATA_PATH)
    total_records = len(df)
    print(f"1. Total Records: {total_records}")

    # 2. File Integrity
    missing_files = []
    for idx, row in df.iterrows():
        abs_path = os.path.join(DATASET_DIR, row['file_name'])
        if not os.path.exists(abs_path):
            missing_files.append(row['file_name'])
    
    print(f"2. File Integrity: {total_records - len(missing_files)}/{total_records} exist")
    if missing_files:
        print(f"   Missing files: {len(missing_files)}")

    # 3. Text Duplication Analysis (STUTTER CHECK)
    duplicate_count = 0
    for idx, row in df.iterrows():
        text = str(row['transcription'])
        words = text.split()
        if len(words) > 5:
            # Check for repeating bigrams
            bigrams = [" ".join(words[i:i+2]) for i in range(len(words)-1)]
            if len(bigrams) > 0:
                most_common_bi, bi_count = Counter(bigrams).most_common(1)[0]
                if bi_count > 2: # Repetition detected
                    duplicate_count += 1

    print(f"3. Text Duplication (Stuttering): {duplicate_count} items ({(duplicate_count/total_records)*100:.1f}%)")

    # 4. Date Analysis (NA folders)
    na_records = df[df['file_name'].str.startswith('NA')].shape[0]
    print(f"4. Date Missing (NA folder): {na_records} items ({(na_records/total_records)*100:.1f}%)")
    
    print("-" * 60)
    print("Investigation Complete")

if __name__ == "__main__":
    full_investigation()
