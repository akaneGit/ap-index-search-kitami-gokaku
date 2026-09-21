"""Rebuild file:// compatible search data after editing data/*.json."""
from pathlib import Path
import json, csv

ROOT = Path(__file__).resolve().parent
books = {}
review_rows = []
for book in ('kitami', 'gokaku'):
    entries = []
    for path in sorted((ROOT / 'data' / book).glob('*.json')):
        page = json.loads(path.read_text(encoding='utf-8'))
        for row in page['entries']:
            if book == 'kitami' and row.get('needsReview'):
                review_rows.append([row.get('indexPage'), row.get('column', 0) + 1, row.get('row'), row.get('word'), row.get('pages'), row.get('reviewReason', ''), row.get('alternatives', {}).get('rapidOCR', ''), row.get('alternatives', {}).get('tesseract', '')])
            if row.get('word') and row.get('pages'):
                entries.append({key: row.get(key, 0) for key in ('word', 'pages', 'indexPage', 'column', 'row', 'needsReview')})
    books[book] = entries
target = ROOT / 'index-data.js'
target.write_text('window.AP_INDEX_DATA = ' + json.dumps(books, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
with (ROOT / '要確認一覧.csv').open('w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(['索引ページ','列','行','用語','掲載ページ','要確認の理由','読み取り候補1','読み取り候補2']); w.writerows(review_rows)
print(f'{target.name}: ' + ', '.join(f'{k} {len(v)}件' for k,v in books.items()))
