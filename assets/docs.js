// Documentation pages: search box, copy buttons, mobile menu, "On this page" highlight.
(function () {
  // Copy buttons on code blocks
  document.querySelectorAll('.codeblock .copy').forEach(function (b) {
    b.addEventListener('click', function () {
      var code = b.closest('.codeblock').querySelector('code').innerText;
      navigator.clipboard.writeText(code).then(function () {
        b.textContent = 'Copied'; b.classList.add('done');
        setTimeout(function () { b.textContent = 'Copy'; b.classList.remove('done'); }, 1200);
      });
    });
  });

  // Mobile menu
  var menu = document.querySelector('.menu');
  if (menu) menu.addEventListener('click', function () {
    var open = document.body.classList.toggle('nav-open');
    menu.setAttribute('aria-expanded', open);
  });

  // "On this page": highlight the section in view
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('.toc a'));
  if (tocLinks.length && 'IntersectionObserver' in window) {
    var byId = {};
    tocLinks.forEach(function (a) { byId[decodeURIComponent(a.hash.slice(1))] = a; });
    var heads = Array.prototype.slice.call(document.querySelectorAll('.prose h2[id], .prose h3[id]'));
    var visible = {};
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { visible[e.target.id] = e.isIntersecting; });
      var first = heads.find(function (h) { return visible[h.id]; });
      if (!first) return;
      tocLinks.forEach(function (a) { a.classList.remove('active'); });
      if (byId[first.id]) byId[first.id].classList.add('active');
    }, { rootMargin: '-70px 0px -70% 0px' });
    heads.forEach(function (h) { obs.observe(h); });
  }

  // Search
  var input = document.querySelector('.search input');
  var list = document.querySelector('.search .results');
  if (!input || !list) return;
  var index = null, active = -1;

  function load() {
    if (index) return Promise.resolve(index);
    return fetch('/docs/search.json').then(function (r) { return r.json(); }).then(function (d) { index = d; return d; });
  }
  function esc(s) { return s.replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function mark(s, terms) {
    var out = esc(s);
    terms.forEach(function (t) {
      out = out.replace(new RegExp('(' + t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig'), '<mark>$1</mark>');
    });
    return out;
  }
  function snippet(x, terms) {
    var lx = x.toLowerCase(), i = -1;
    terms.some(function (t) { i = lx.indexOf(t); return i >= 0; });
    if (i < 0) return x.slice(0, 120);
    var start = Math.max(0, i - 40);
    return (start ? '… ' : '') + x.slice(start, start + 140);
  }
  function search(q) {
    var terms = q.toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) { list.hidden = true; return; }
    var hits = [];
    index.forEach(function (e) {
      var t = e.t.toLowerCase(), x = e.x.toLowerCase(), score = 0;
      for (var i = 0; i < terms.length; i++) {
        var w = terms[i];
        if (t.indexOf(w) >= 0) score += t === w ? 12 : 6;
        else if (x.indexOf(w) >= 0) score += 1;
        else return;
      }
      if (!e.u.includes('#')) score += 1;
      hits.push({ e: e, s: score });
    });
    hits.sort(function (a, b) { return b.s - a.s; });
    hits = hits.slice(0, 10);
    active = -1;
    list.innerHTML = hits.length
      ? hits.map(function (h) {
          return '<li><a href="' + h.e.u + '"><small>' + esc(h.e.p) + '</small><b>' + mark(h.e.t, terms) +
            '</b><span>' + mark(snippet(h.e.x, terms), terms) + '</span></a></li>';
        }).join('')
      : '<li class="empty">No results for “' + esc(q) + '”</li>';
    list.hidden = false;
  }
  input.addEventListener('focus', load);
  input.addEventListener('input', function () { load().then(function () { search(input.value.trim()); }); });
  input.addEventListener('keydown', function (ev) {
    var links = list.querySelectorAll('a');
    if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
      if (!links.length) return;
      ev.preventDefault();
      active = (active + (ev.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length;
      links.forEach(function (a, i) { a.classList.toggle('active', i === active); });
      links[active].scrollIntoView({ block: 'nearest' });
    } else if (ev.key === 'Enter') {
      var a = links[active >= 0 ? active : 0];
      if (a) { ev.preventDefault(); location.href = a.href; }
    } else if (ev.key === 'Escape') {
      list.hidden = true; input.blur();
    }
  });
  document.addEventListener('click', function (ev) { if (!ev.target.closest('.search')) list.hidden = true; });
  document.addEventListener('keydown', function (ev) {
    if (ev.key === '/' && document.activeElement !== input && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) {
      ev.preventDefault(); input.focus();
    }
  });
})();
