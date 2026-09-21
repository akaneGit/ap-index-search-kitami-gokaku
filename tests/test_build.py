import contextlib
import csv
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import build


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'data').mkdir()

    def write(self, relative, value, encoding='utf-8'):
        path = self.root / 'data' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding=encoding)

    def run_build(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return build(self.root)

    def test_folder_alone_adds_document_and_preserves_file_order(self):
        self.write('manual/01.json', {'entries': [{'word': '設定', 'pages': '12,15'}]})
        self.write('manual/02.json', {'entries': [{'word': '起動', 'pages': '2-4'}]}, 'utf-8-sig')
        documents, books = self.run_build()
        self.assertEqual(documents, [{'id': 'manual', 'title': 'manual'}])
        self.assertEqual([row['word'] for row in books['manual']], ['設定', '起動'])
        self.assertEqual([row['row'] for row in books['manual']], [1, 2])
        self.assertFalse(books['manual'][0]['needsReview'])
        script = (self.root / 'index-data.js').read_text(encoding='utf-8')
        self.assertIn('window.AP_INDEX_DOCUMENTS = [{"id":"manual","title":"manual"}]', script)

    def test_optional_titles_order_and_empty_folders(self):
        for name in ('a', 'b', 'c'):
            self.write(f'{name}/entries.json', {'entries': [{'word': name, 'pages': '1'}]})
        self.write('c/document.json', {'title': '先頭の文書', 'order': 0})
        self.write('draft/document.json', {'title': '準備中'})
        documents, _ = self.run_build()
        self.assertEqual([item['id'] for item in documents], ['c', 'a', 'b'])
        self.assertEqual(documents[0]['title'], '先頭の文書')

    def test_review_csv_covers_every_document_including_unreadable_rows(self):
        for name in ('manual', 'guide'):
            self.write(f'{name}/index.json', {'indexPage': 50, 'entries': [
                {'word': '確認用', 'pages': '10', 'needsReview': True},
                {'word': '', 'pages': '20', 'needsReview': True},
            ]})
        _, books = self.run_build()
        self.assertEqual(len(books['manual']), 1)
        self.assertEqual(books['manual'][0]['indexPage'], 50)
        with (self.root / '要確認一覧.csv').open(encoding='utf-8-sig', newline='') as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 4)
        self.assertEqual({row['文書ID'] for row in rows}, {'manual', 'guide'})
        self.assertIn('data/manual/index.json', {row['元ファイル'] for row in rows})

    def test_invalid_data_identifies_file_and_keeps_previous_build(self):
        self.write('manual/index.json', {'entries': [{'word': '正常', 'pages': '1'}]})
        self.run_build()
        outputs = {name: (self.root / name).read_bytes() for name in ('index-data.js', '要確認一覧.csv')}
        invalid_values = [
            {}, {'entries': {}}, {'entries': [None]},
            {'entries': [{'word': 'ページなし'}]},
            {'entries': [{'word': '数値', 'pages': 1}]},
            {'entries': [{'word': '型', 'pages': '1', 'needsReview': 'false'}]},
            {'entries': [{'word': '位置', 'pages': '1', 'indexPage': -1}]},
        ]
        for value in invalid_values:
            with self.subTest(value=value):
                self.write('manual/index.json', value)
                with self.assertRaisesRegex(ValueError, r'index\.json'):
                    self.run_build()
                for name, previous in outputs.items():
                    self.assertEqual((self.root / name).read_bytes(), previous)
        (self.root / 'data/manual/index.json').write_text('{', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, r'index\.json'):
            self.run_build()

    def test_invalid_metadata_is_reported(self):
        self.write('manual/index.json', {'entries': []})
        for metadata in ({'title': ''}, {'order': 'first'}, {'order': True}):
            self.write('manual/document.json', metadata)
            with self.assertRaisesRegex(ValueError, r'document\.json'):
                self.run_build()

    def test_removing_a_document_removes_generated_entries(self):
        self.write('manual/index.json', {'entries': [{'word': '削除前', 'pages': '1'}]})
        self.run_build()
        shutil.rmtree(self.root / 'data/manual')
        documents, books = self.run_build()
        self.assertEqual((documents, books), ([], {}))
        self.assertNotIn('削除前', (self.root / 'index-data.js').read_text(encoding='utf-8'))

    def test_legacy_index_coordinates_are_preserved(self):
        entry = {'word': '既存用語', 'pages': '123,125', 'indexPage': 940,
                 'column': 1, 'row': 12, 'needsReview': True}
        verified = dict(entry, word='確認済み', indexPage=0, needsReview=False)
        self.write('legacy/index.json', {'indexPage': 940, 'entries': [entry]})
        self.write('legacy/verified-extra.json', {'indexPage': 'verified-extra', 'entries': [verified]})
        _, books = self.run_build()
        self.assertEqual(books['legacy'], [entry, verified])


if __name__ == '__main__':
    unittest.main()
