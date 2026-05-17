import os
import pandas as pd
import re

def clean_text(text):
    text = str(text).replace('\n', ' ')
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\[.*?\]|\(.*?\)', '', text)
    
    fillers = [
        '음', '어', '그', '아니', '이제', '막', '근데', '사실', '어떻게', '보면',
        '약간', '그게', '진짜', '그니까', '막말로', '뭐', '뭐냐', '일단', '그다음에',
        '자', '아', '하', '참', '어우', '야'
    ]
    
    for f in fillers:
        text = re.sub(rf'(^|\s){f}[,\.\!\?]*(?=\s|$)', ' ', text)
    
    return re.sub(r'\s+', ' ', text).strip()

dataset_dir = r"C:\ameva\AMEVA-STT-Trainer\dataset"
total_count = 0

for root, dirs, files in os.walk(dataset_dir):
    for f in files:
        if f == "metadata.csv":
            path = os.path.join(root, f)
            df = pd.read_csv(path)
            if "transcription" in df.columns:
                df["transcription"] = df["transcription"].apply(clean_text)
                df.to_csv(path, index=False, encoding="utf-8-sig")
                total_count += len(df)
                print(f"Cleaned: {path}")

print(f"Total records sanitized: {total_count}")
