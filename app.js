(() => {
  const data = window.AP_INDEX_DATA || {};
  const book = document.querySelector('#book');
  const query = document.querySelector('#query');
  const order = document.querySelector('#order');
  const review = document.querySelector('#review');
  const summary = document.querySelector('#summary');
  const results = document.querySelector('#results');
  const documents = window.AP_INDEX_DOCUMENTS || Object.keys(data).map(id => ({ id, title: id }));
  book.replaceChildren();
  for (const item of documents) {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = item.title;
    book.append(option);
  }
  for (const control of [book, query, order, review]) control.disabled = !documents.length;
  const normalize = s => String(s || '').normalize('NFKC').toLowerCase().replace(/[\s\u3000・･.．‐‑–—−ー_()（）/／]/g, '');
  const firstPage = s => Number(String(s).match(/\d+/)?.[0] || 9999);

  function draw() {
    if (!documents.length) {
      summary.textContent = '0件の文書';
      const p = document.createElement('p'); p.className = 'empty'; p.textContent = '検索できる文書がありません。'; results.replaceChildren(p); return;
    }
    const items = data[book.value] || [];
    const words = normalize(query.value);
    if (!words && !review.checked) {
      summary.textContent = `${items.length.toLocaleString()}件の索引語`;
      const p = document.createElement('p'); p.className = 'empty'; p.textContent = '検索する言葉を入力してください。'; results.replaceChildren(p); return;
    }
    const matches = items.filter(x => (!words || normalize(x.word).includes(words)) && (!review.checked || x.needsReview));
    if (order.value === 'page') matches.sort((a, b) => firstPage(a.pages) - firstPage(b.pages) || a.word.localeCompare(b.word, 'ja'));
    else matches.sort((a, b) => a.indexPage - b.indexPage || a.column - b.column || a.row - b.row);
    results.replaceChildren();
    summary.textContent = `${matches.length.toLocaleString()}件 / ${items.length.toLocaleString()}件`;
    if (!matches.length) {
      const p = document.createElement('p'); p.className = 'empty'; p.textContent = words ? '該当する索引語がありません。' : 'データがありません。'; results.append(p); return;
    }
    const fragment = document.createDocumentFragment();
    for (const item of matches) {
      const article = document.createElement('article'); article.className = 'item';
      const left = document.createElement('div');
      const term = document.createElement('div'); term.className = 'term'; term.textContent = item.word;
      left.append(term);
      if (item.needsReview) {
        const note = document.createElement('div'); note.className = 'note';
        note.textContent = item.indexPage ? `要確認 · 索引 p.${item.indexPage}` : '要確認'; left.append(note);
      }
      const pages = document.createElement('div'); pages.className = 'pages'; pages.textContent = `p.${item.pages}`;
      article.append(left, pages); fragment.append(article);
    }
    results.append(fragment);
  }
  for (const elem of [book, query, order, review]) elem.addEventListener(elem === query ? 'input' : 'change', draw);
  draw();
})();
