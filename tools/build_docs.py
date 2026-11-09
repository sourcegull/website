"""Builds the documentation pages under docs/ from the Markdown in sourcegull/sourcegull.

Usage: python tools/build_docs.py [ref]   (default: the latest release tag)

Downloads the source tarball of `ref` from GitHub, renders each page listed in NAV to
docs/<slug>/index.html with the site's header, a sidebar, an "On this page" list and
prev/next links, and writes docs/search.json for the search box. Links to other rendered
pages become site links; links to anything else in the repository go to GitHub at `ref`.
"""

import html
import io
import json
import os
import posixpath
import re
import shutil
import sys
import tarfile
import urllib.request

from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

REPO = "sourcegull/sourcegull"
SITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(SITE_ROOT, "docs")

# (group, [(source path in the repository, URL slug under /docs/, sidebar label)])
NAV = [
    ("Get started", [
        ("docs/README.md", "", "Overview"),
        ("docs/install.md", "install", "Install"),
        ("docs/configuration.md", "configuration", "Configuration"),
        ("docs/permissions.md", "permissions", "Permissions and sign-in"),
    ]),
    ("Use", [
        ("docs/search.md", "search", "Search"),
        ("docs/code-navigation.md", "code-navigation", "Code navigation"),
        ("docs/mcp.md", "mcp", "AI agents (MCP)"),
        ("docs/bulk-changes.md", "bulk-changes", "Bulk changes"),
        ("docs/features.md", "features", "Other features"),
    ]),
    ("Operate", [
        ("deploy/docker/upgrade.md", "upgrade-compose", "Upgrade (Docker Compose)"),
        ("deploy/helm/sourcegull/README.md", "helm", "Helm chart"),
        ("deploy/helm/sourcegull/SIZING.md", "helm-sizing", "Sizing"),
        ("docs/observability/README.md", "observability", "Monitoring"),
        ("docs/observability/dashboards.md", "observability/dashboards", "Dashboards"),
        ("docs/observability/alerts.md", "observability/alerts", "Alerts"),
    ]),
    ("Contribute", [
        ("docs/architecture.md", "architecture", "Architecture"),
        ("docs/development.md", "development", "Development"),
        ("docs/roadmap.md", "roadmap", "Roadmap"),
    ]),
]
PAGES = [p for _, items in NAV for p in items]
BY_SOURCE = {src: slug for src, slug, _ in PAGES}
CURRENT = ' aria-current="page"'


def url_for(slug):
    return "/docs/" + (slug + "/" if slug else "")


def latest_tag():
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "sourcegull-website-build"},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)["tag_name"]


def fetch(ref):
    url = f"https://codeload.github.com/{REPO}/tar.gz/{ref}"
    with urllib.request.urlopen(url) as r:
        data = r.read()
    files, dirs = {}, set()
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for m in tar.getmembers():
            path = m.name.split("/", 1)[1] if "/" in m.name else ""
            if not path:
                continue
            if m.isdir():
                dirs.add(path.rstrip("/"))
            elif m.isfile():
                parent = posixpath.dirname(path)
                while parent:
                    dirs.add(parent)
                    parent = posixpath.dirname(parent)
                if path.endswith(".md") or path.startswith("docs/assets/"):
                    files[path] = tar.extractfile(m).read()
                else:
                    files.setdefault(path, None)
    return files, dirs


def gh_slug(text, seen):
    s = text.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    s = s.replace(" ", "-")
    n = seen.get(s, 0)
    seen[s] = n + 1
    return s if n == 0 else f"{s}-{n}"


def code_html(code, lang):
    lang = (lang or "").strip().split()[0] if lang else ""
    alias = {"jsonc": "javascript", "promql": "text", "sh": "bash", "": "text"}.get(lang, lang)
    try:
        lexer = get_lexer_by_name(alias)
    except ClassNotFound:
        lexer = get_lexer_by_name("text")
    body = highlight(code, lexer, HtmlFormatter(nowrap=True))
    label = html.escape(lang or "text")
    return (
        f'<div class="codeblock"><div class="codebar"><span>{label}</span>'
        f'<button class="copy" type="button" aria-label="Copy">Copy</button></div>'
        f'<pre class="hl"><code>{body}</code></pre></div>\n'
    )


class Renderer:
    def __init__(self, ref, files, dirs):
        self.ref, self.files, self.dirs = ref, files, dirs
        self.md = MarkdownIt("commonmark", {"html": True, "linkify": False, "typographer": False}).enable("table").enable("strikethrough")
        self.md.add_render_rule("fence", self.fence)
        self.md.add_render_rule("code_block", self.fence)
        self.assets = set()

    def fence(self, tokens, idx, options, env):
        t = tokens[idx]
        return code_html(t.content, t.info)

    def resolve(self, href, src):
        if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I) or href.startswith("//"):
            return href
        path, _, frag = href.partition("#")
        if not path:
            return "#" + frag if frag else href
        target = posixpath.normpath(posixpath.join(posixpath.dirname(src), path))
        if target in self.dirs and target + "/README.md" in BY_SOURCE:
            target += "/README.md"
        if target in BY_SOURCE:
            out = url_for(BY_SOURCE[target])
        elif target.startswith("docs/assets/") and target in self.files:
            self.assets.add(target)
            out = "/docs/" + target[len("docs/"):]
        else:
            kind = "tree" if target in self.dirs else "blob"
            out = f"https://github.com/{REPO}/{kind}/{self.ref}/{target}"
        return out + ("#" + frag if frag else "")

    def render(self, src):
        text = self.files[src].decode("utf-8")
        tokens = self.md.parse(text)
        seen, toc, title = {}, [], None
        sections, current = [], None
        for i, t in enumerate(tokens):
            if t.type == "heading_open":
                inline = tokens[i + 1]
                plain = "".join(c.content for c in inline.children if c.type in ("text", "code_inline"))
                slug = gh_slug(plain, seen)
                t.attrSet("id", slug)
                level = int(t.tag[1])
                if level == 1 and title is None:
                    title = plain
                elif level in (2, 3):
                    toc.append((level, slug, plain))
                current = {"anchor": slug if level > 1 else "", "title": plain, "text": []}
                sections.append(current)
            elif t.type == "inline":
                for c in t.children or []:
                    if c.type == "link_open":
                        c.attrSet("href", self.resolve(c.attrGet("href"), src))
                        if c.attrGet("href").startswith("http"):
                            c.attrSet("rel", "noopener")
                    elif c.type == "image":
                        c.attrSet("src", self.resolve(c.attrGet("src"), src))
                if current is not None and tokens[i - 1].type != "heading_open":
                    current["text"].append(t.content)
        body = self.md.renderer.render(tokens, self.md.options, {})
        body = re.sub(r"<table>", '<div class="table"><table>', body).replace("</table>", "</table></div>")
        body = re.sub(
            r'<(h[23]) id="([^"]+)">(.*?)</h[23]>',
            r'<\1 id="\2"><a class="anchor" href="#\2" aria-hidden="true">#</a>\3</\1>',
            body,
        )
        return title or src, body, toc, sections


def page_html(ref, src, slug, label, title, body, toc, prev, nxt):
    nav = []
    for group, items in NAV:
        links = "".join(
            f'<li><a href="{url_for(s)}"{CURRENT if s == slug else ""}>{html.escape(l)}</a></li>'
            for _, s, l in items
        )
        nav.append(f'<div class="navgroup"><p>{html.escape(group)}</p><ul>{links}</ul></div>')
    toc_html = "".join(
        f'<li class="l{lvl}"><a href="#{a}">{html.escape(t)}</a></li>' for lvl, a, t in toc
    )
    pn = '<nav class="pager" aria-label="Pages">'
    if prev:
        pn += f'<a class="prev" href="{url_for(prev[1])}"><span>Previous</span><b>{html.escape(prev[2])}</b></a>'
    else:
        pn += "<span></span>"
    if nxt:
        pn += f'<a class="next" href="{url_for(nxt[1])}"><span>Next</span><b>{html.escape(nxt[2])}</b></a>'
    pn += "</nav>"
    edit = f"https://github.com/{REPO}/blob/main/{src}"
    page_title = "Sourcegull documentation" if not slug else f"{title} · Sourcegull docs"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(page_title)}</title>
  <meta name="color-scheme" content="light dark" />
  <link rel="icon" type="image/png" href="/favicon.png" />
  <link rel="stylesheet" href="/style.css" />
  <link rel="stylesheet" href="/assets/docs.css" />
</head>
<body class="docs">
  <header class="topbar">
    <div class="topbar-inner wide">
      <button class="menu" type="button" aria-label="Menu" aria-expanded="false"><span></span></button>
      <a class="brand" href="/"><img src="/favicon.png" width="28" height="28" alt="" /><span>Source<b>gull</b></span><em>docs</em></a>
      <div class="search">
        <input type="search" placeholder="Search the docs" aria-label="Search the docs" autocomplete="off" />
        <kbd>/</kbd>
        <ul class="results" hidden></ul>
      </div>
      <nav class="topnav" aria-label="Site">
        <a href="/#features">Features</a>
        <a href="/docs/install/">Install</a>
        <a href="https://github.com/{REPO}">GitHub</a>
      </nav>
    </div>
  </header>
  <div class="docs-layout">
    <aside class="sidebar">
      <p class="version">Version <b>{html.escape(ref)}</b></p>
      {"".join(nav)}
    </aside>
    <main class="doc">
      <article class="prose">
{body}
      </article>
      <p class="edit"><a href="{edit}">Edit this page on GitHub</a></p>
      {pn}
    </main>
    <aside class="toc">
      {"<p>On this page</p><ul>" + toc_html + "</ul>" if toc else ""}
    </aside>
  </div>
  <script src="/assets/docs.js" defer></script>
</body>
</html>
"""


def main():
    ref = sys.argv[1] if len(sys.argv) > 1 else latest_tag()
    files, dirs = fetch(ref)
    missing = [src for src, _, _ in PAGES if src not in files]
    if missing:
        sys.exit(f"missing in {ref}: {', '.join(missing)}")
    r = Renderer(ref, files, dirs)
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    index = []
    for i, (src, slug, label) in enumerate(PAGES):
        title, body, toc, sections = r.render(src)
        prev = PAGES[i - 1] if i > 0 else None
        nxt = PAGES[i + 1] if i + 1 < len(PAGES) else None
        dest = os.path.join(OUT, slug, "index.html")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w") as f:
            f.write(page_html(ref, src, slug, label, title, body, toc, prev, nxt))
        for s in sections:
            text = re.sub(r"[`*_\[\]]|\]\([^)]*\)", "", " ".join(s["text"]))
            text = re.sub(r"\(([^)]*\.md[^)]*|https?://[^)]*)\)", "", text)
            index.append({
                "p": label,
                "t": s["title"],
                "u": url_for(slug) + ("#" + s["anchor"] if s["anchor"] else ""),
                "x": re.sub(r"\s+", " ", text)[:600],
            })
    for a in r.assets:
        dest = os.path.join(OUT, a[len("docs/"):])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(files[a])
    with open(os.path.join(OUT, "search.json"), "w") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(PAGES)} pages from {REPO}@{ref}, {len(index)} search entries")


if __name__ == "__main__":
    main()
