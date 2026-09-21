"""Exercise the real page in headless Chrome, including a data-only new document."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT, build

CHECKS = r'''
<pre id="test-report">PENDING</pre>
<script>
try {
  const find = selector => document.querySelector(selector);
  const assert = (value, message) => { if (!value) throw Error(message); };
  const query = value => { find('#query').value = value; find('#query').dispatchEvent(new Event('input')); };
  const select = (selector, value) => { find(selector).value = value; find(selector).dispatchEvent(new Event('change')); };
  assert(find('#book').options.length === Object.keys(window.AP_INDEX_DATA).length, 'document discovery');
  assert(find('#book').value === 'legacy-manual', 'document order');
  query('DNS'); assert(document.querySelectorAll('.item').length === 1, 'legacy format search');
  assert(find('.note').textContent === '要確認 · 索引 p.100', 'legacy index page');
  select('#book', 'extra-manual'); query('ＤＮＳ');
  assert(find('#book').selectedOptions[0].textContent === '操作マニュアル', 'new document title');
  assert(document.querySelectorAll('.item').length === 2, 'new document search and normalization');
  assert(find('.pages').textContent === 'p.30', 'source order');
  select('#order', 'page'); assert(find('.pages').textContent === 'p.2', 'page order');
  find('#review').checked = true; find('#review').dispatchEvent(new Event('change'));
  assert(document.querySelectorAll('.item').length === 1, 'review filter');
  assert(find('.note').textContent === '要確認', 'unknown index page');
  query('does-not-exist'); assert(document.querySelectorAll('.item').length === 0 && find('.empty'), 'no matches');
  query(''); assert(document.querySelectorAll('.item').length === 1, 'review without query');
  find('#review').checked = false; find('#review').dispatchEvent(new Event('change'));
  query('literal'); assert(find('.term').textContent.includes('<img'), 'literal term');
  assert(!find('#results img') && !window.unsafe, 'safe rendering');
  assert(document.documentElement.scrollWidth <= window.innerWidth, 'mobile page width');
  find('#test-report').textContent = 'PASS: discovery, existing and new documents, search, order, review, safe rendering, mobile width';
} catch (error) { document.querySelector('#test-report').textContent = 'FAIL: ' + error.message; }
</script>
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', default='google-chrome')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        legacy = root / 'data/legacy-manual'
        legacy.mkdir(parents=True)
        (legacy / 'document.json').write_text(json.dumps({'title': '元の文書', 'order': 10}), encoding='utf-8')
        (legacy / 'entries.json').write_text(json.dumps({'entries': [
            {'word': 'DNS', 'pages': '10', 'indexPage': 100, 'column': 0, 'row': 1, 'needsReview': True},
        ]}), encoding='utf-8')
        extra = root / 'data/extra-manual'
        extra.mkdir()
        (extra / 'document.json').write_text(json.dumps({'title': '操作マニュアル'}), encoding='utf-8')
        (extra / 'entries.json').write_text(json.dumps({'entries': [
            {'word': 'DNS 手順', 'pages': '30', 'needsReview': True},
            {'word': 'DNS 基本', 'pages': '2'},
            {'word': 'literal <img src=x onerror="window.unsafe=true">', 'pages': '44'},
        ]}), encoding='utf-8')
        build(root)
        shutil.copyfile(ROOT / 'app.js', root / 'app.js')
        html = (ROOT / 'index.html').read_text(encoding='utf-8').replace('</body>', CHECKS + '</body>')
        (root / 'index.html').write_text(html, encoding='utf-8')
        result = subprocess.run([
            args.browser, '--headless', '--no-sandbox', '--disable-gpu', '--no-first-run',
            '--no-default-browser-check', '--allow-file-access-from-files',
            '--window-size=390,844', f'--user-data-dir={root / "profile"}',
            '--dump-dom', '--virtual-time-budget=2000', (root / 'index.html').as_uri(),
        ], capture_output=True, encoding='utf-8', errors='replace', timeout=45)
        report = re.search(r'<pre id="test-report">(.*?)</pre>', result.stdout)
        if result.returncode or not report or not report[1].startswith('PASS:'):
            raise RuntimeError(report[1] if report else result.stderr[-4000:] or 'No browser output')
        print(report[1])


if __name__ == '__main__':
    main()
