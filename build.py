"""Build offline-compatible search data from data/<document>/*.json."""
from pathlib import Path
import csv
import json
import sys

ROOT = Path(__file__).resolve().parent


def read_object(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as error:
        raise ValueError(f'{path}: {error}') from error
    if not isinstance(value, dict):
        raise ValueError(f'{path}: JSON must be an object')
    return value


def nonnegative_integer(value, context):
    if type(value) is not int or value < 0:
        raise ValueError(f'{context}: must be a non-negative integer')
    return value


def build(root=ROOT):
    root = Path(root)
    data_dir = root / 'data'
    if not data_dir.is_dir():
        raise ValueError(f'{data_dir}: data directory not found')

    documents = []
    books = {}
    review_rows = []
    skipped = 0
    for folder in sorted(data_dir.iterdir()):
        if not folder.is_dir() or folder.name.startswith('.'):
            continue
        paths = sorted(path for path in folder.glob('*.json') if path.name != 'document.json')
        if not paths:
            continue
        metadata_path = folder / 'document.json'
        metadata = read_object(metadata_path) if metadata_path.exists() else {}
        title = metadata.get('title', folder.name)
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f'{metadata_path}: title must be a non-empty string')
        order = nonnegative_integer(metadata.get('order', 100), f'{metadata_path}: order')
        documents.append({'id': folder.name, 'title': title, 'order': order})
        entries = []
        position = 0
        for path in paths:
            page = read_object(path)
            if not isinstance(page.get('entries'), list):
                raise ValueError(f'{path}: entries must be an array')
            for number, row in enumerate(page['entries'], 1):
                position += 1
                context = f'{path}: entries[{number - 1}]'
                if not isinstance(row, dict):
                    raise ValueError(f'{context}: entry must be an object')
                if 'word' not in row or 'pages' not in row:
                    raise ValueError(f'{context}: word and pages are required')
                word = row['word']
                pages = row['pages']
                if not isinstance(word, str) or not isinstance(pages, str):
                    raise ValueError(f'{context}: word and pages must be strings')
                needs_review = row.get('needsReview', False)
                if type(needs_review) is not bool:
                    raise ValueError(f'{context}: needsReview must be true or false')
                index_page = row.get('indexPage', page.get('indexPage', 0))
                index_page = nonnegative_integer(index_page, f'{context}: indexPage')
                column = nonnegative_integer(row.get('column', 0), f'{context}: column')
                line = nonnegative_integer(row.get('row', position), f'{context}: row')
                if needs_review:
                    alternatives = row.get('alternatives', {})
                    if not isinstance(alternatives, dict):
                        raise ValueError(f'{context}: alternatives must be an object')
                    review_rows.append([
                        folder.name, title, path.relative_to(root).as_posix(),
                        index_page or '', column + 1, line, word, pages,
                        row.get('reviewReason', ''), alternatives.get('rapidOCR', ''),
                        alternatives.get('tesseract', ''),
                    ])
                # Keep unreadable OCR rows in the source/review CSV, but not in search results.
                if not word.strip() or not pages.strip():
                    skipped += 1
                    continue
                entries.append({
                    'word': word, 'pages': pages, 'indexPage': index_page,
                    'column': column, 'row': line, 'needsReview': needs_review,
                })
        books[folder.name] = entries

    documents.sort(key=lambda document: (document['order'], document['id']))
    documents = [{'id': document['id'], 'title': document['title']} for document in documents]
    books = {document['id']: books[document['id']] for document in documents}
    # Validate every document before replacing either generated file.
    serialized = json.dumps(books, ensure_ascii=False, separators=(',', ':'))
    catalog = json.dumps(documents, ensure_ascii=False, separators=(',', ':'))
    (root / 'index-data.js').write_text(
        f'window.AP_INDEX_DATA = {serialized};\nwindow.AP_INDEX_DOCUMENTS = {catalog};\n',
        encoding='utf-8', newline='\n',
    )
    with (root / '要確認一覧.csv').open('w', newline='', encoding='utf-8-sig') as output:
        writer = csv.writer(output)
        writer.writerow([
            '文書ID', '文書名', '元ファイル', '索引ページ', '列', '行', '用語',
            '掲載ページ', '要確認の理由', '読み取り候補1', '読み取り候補2',
        ])
        writer.writerows(review_rows)
    print('index-data.js: ' + ', '.join(f'{key} {len(value)} entries' for key, value in books.items()))
    if skipped:
        print(f'Skipped {skipped} OCR rows with empty word/pages (preserved in source).', file=sys.stderr)
    return documents, books


if __name__ == '__main__':
    try:
        build()
    except ValueError as error:
        print(error, file=sys.stderr)
        sys.exit(1)
