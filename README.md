# sourcegull/website

The project site at https://sourcegull.org: a hand-written landing page (`index.html`,
`style.css`) and documentation pages generated from the Markdown in sourcegull/sourcegull.

- `docs/` is generated; don't edit it. Rebuild it with `tools/build-docs.sh [ref]` (Docker;
  default ref is the latest release tag), after each release or docs fix. Pages, their order
  and their sidebar groups are listed in `NAV` in `tools/build_docs.py`; the build also writes
  `sitemap.xml` from that list, so commit it with `docs/` when `NAV` changes.
- `robots.txt` points crawlers to the sitemap.
- `assets/docs.css` and `assets/docs.js` style the docs pages and run their search box.
- Screenshots and the wordmark are copies of `docs/assets/` in sourcegull/sourcegull; the icons
  come from `ui/static/`.

Preview: `python3 -m http.server 8090`, then open http://localhost:8090.
GitHub Pages serves the `main` branch as is; `CNAME` holds the domain.
