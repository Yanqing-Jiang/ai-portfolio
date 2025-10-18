from pathlib import Path
text = Path(r'components/analytics/common/AnalysisCard.tsx').read_text(encoding='utf-8')
start = text.index('{snippet && (')
end = start
while not text[end:end+3] == '\n                )}':
    end += 1
end += len('\n                )}')
print('len', end-start)
print(repr(text[start:end]))
