import pandas as pd
from collections import Counter

df = pd.read_csv('dataset/metadata.csv')
print("=" * 60)
print("Check Flagged Stutter Data (Top 20)")
print("=" * 60)

count = 0
for text in df['transcription'].fillna(''):
    words = str(text).split()
    if len(words) > 5:
        trigrams = [" ".join(words[i:i+3]) for i in range(len(words)-2)]
        if trigrams:
            mc, tri_c = Counter(trigrams).most_common(1)[0]
            if tri_c > 1:
                print(f"[{count+1}] {text}")
                print(f"   -> Repeated: '{mc}' ({tri_c} times)")
                print("-" * 40)
                count += 1
                if count >= 20:
                    break
