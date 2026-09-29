#!/usr/bin/env python3
"""Render trusted project Markdown as offline HTML; never target evidence.

Run with Markdown==3.10.2. --check detects stale generated documents.
Raw HTML in trusted project Markdown is preserved: this is not a sanitizer
and must never process untrusted target evidence. The static document CSP
blocks scripts and subresource loads, allowing inline styles only, as
defense in depth; it does not change that trust boundary.
"""
import argparse
import hashlib
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re

import markdown

DOCUMENTS = [
    ("Omnis_Implementation_Plan", "Omnis — plan de implementare v2"),
    ("Omnis_MVP_Architecture", "Omnis — arhitectura MVP v1"),
    ("Omnis_UI_UX_Spec", "Omnis — specificație UI/UX"),
    ("Omnis_Stack_Baseline", "Omnis — stack și versiuni"),
    ("Omnis_Implementation_Readiness_Review", "Omnis — review de readiness"),
]
CSS = """
:root{color-scheme:light;--paper:#faf9f6;--ink:#262923;--muted:#5f6458;--line:#d9ddd1;--accent:#245c44;--nav:#f0f0e9}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.7 'Segoe UI','Liberation Sans',Arial,sans-serif}
a{color:var(--accent);text-underline-offset:3px;overflow-wrap:anywhere}a:focus-visible,summary:focus-visible,[tabindex]:focus-visible{outline:3px solid var(--accent);outline-offset:4px}.skip{position:fixed;top:-100px;left:16px;background:white;padding:12px;z-index:10}.skip:focus{top:12px}
.sidebar{position:fixed;inset:0 auto 0 0;width:272px;padding:28px 22px;overflow-y:auto;background:var(--nav);border-right:1px solid var(--line)}.wordmark{letter-spacing:.14em;font-size:23px;font-weight:700}.note{font-size:13px;color:var(--muted)}nav ul{list-style:none;padding:0}nav a{display:block;padding:8px 0;min-height:44px;font-size:13px;line-height:1.5;text-decoration:none}nav a:hover{text-decoration:underline}
.page{margin-left:272px;padding:30px clamp(22px,4vw,64px) 70px}main{max-width:1050px;min-width:0;margin:auto}.topline{display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px;font-size:13px;color:var(--muted);padding-bottom:18px;border-bottom:1px solid var(--line)}.status{background:#edf3ec;padding:3px 9px;border-radius:4px}
h1{font:400 clamp(32px,3.5vw,52px)/1.16 Georgia,'Liberation Serif',serif;letter-spacing:-.025em;margin:40px 0 24px}h2{font:400 clamp(25px,2.5vw,33px)/1.3 Georgia,'Liberation Serif',serif;margin:56px 0 20px;padding-top:25px;border-top:1px solid var(--line);scroll-margin-top:24px}h3{font-size:20px;margin-top:32px}p,li{overflow-wrap:anywhere}li{margin:7px 0}code{font:13px/1.6 'Liberation Mono',Consolas,monospace;overflow-wrap:anywhere;background:#e9ece5;border-radius:3px;padding:2px 4px}pre{background:#18251f;color:#eef3ec;padding:20px;overflow-x:auto;border-radius:6px;max-width:100%;line-height:1.6}pre code{background:none;padding:0;color:inherit;white-space:pre;overflow-wrap:normal}.table-wrap{max-width:100%;overflow-x:auto;border:1px solid var(--line);border-radius:5px;margin:24px 0}table{border-collapse:collapse;width:100%;min-width:650px;font-size:14px;line-height:1.6}th,td{padding:12px 14px;vertical-align:top;text-align:left;border-bottom:1px solid var(--line);overflow-wrap:anywhere}th{background:var(--nav);font-weight:600}td{min-width:155px}tr:last-child td{border-bottom:0}blockquote{margin:24px 0;padding:16px 20px;background:#edf3ec}.mobile-nav{display:none}footer{margin-top:48px;padding-top:20px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}.links{display:flex;gap:16px;flex-wrap:wrap}
@media(max-width:1000px){.sidebar{width:224px;padding:22px 16px}.page{margin-left:224px;padding-inline:26px}}@media(max-width:760px){.sidebar{display:none}.page{margin:0;padding:20px 18px 48px}.mobile-nav{display:block;background:var(--nav);padding:0 18px;border-bottom:1px solid var(--line)}summary{min-height:48px;padding:12px 0;cursor:pointer}body{font-size:16px}h1{margin-top:28px}pre{padding:14px}}
@media print{@page{size:A4;margin:18mm}.sidebar,.mobile-nav,.skip,.topline{display:none}.page{margin:0;padding:0}body{background:white;font-size:12pt;line-height:1.5}h1{font-size:26pt}h2{font-size:20pt;break-after:avoid}h3{font-size:14pt;break-after:avoid}.table-wrap{overflow:visible;border:0}table{min-width:0;table-layout:fixed;font-size:12pt}td,th{min-width:0;padding:7px}pre,pre code{font-size:12pt;white-space:pre-wrap;background:#f0f0ed;color:#222}code{font-size:12pt}a{color:inherit}p,li{orphans:3;widows:3}footer{font-size:12pt}}
"""


class HeadingText(HTMLParser):
    """Extract heading labels, not a sanitizer for document HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def heading_label(fragment: str) -> str:
    parser = HeadingText()
    parser.feed(fragment)
    parser.close()
    return escape(''.join(parser.parts))


def render(text: str, title: str, source_name: str) -> str:
    converter = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists"])
    body = converter.convert(text)
    body = body.replace("<table>", '<div class="table-wrap" role="region" aria-label="Tabel cu derulare orizontală" tabindex="0"><table>')
    body = body.replace("</table>", "</table></div>")
    headings = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body, re.S)
    nav = '<nav aria-label="Cuprins"><ul>' + ''.join(
        f'<li><a href="#{escape(anchor, quote=True)}">{heading_label(label)}</a></li>'
        for anchor, label in headings
    ) + '</ul></nav>'
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    safe_title, safe_source = escape(title), escape(source_name, quote=True)
    return f'''<!doctype html>
<html lang="ro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; base-uri 'none'"><title>{safe_title}</title><style>{CSS}</style></head>
<body><a class="skip" href="#content">Sari la conținut</a>
<aside class="sidebar"><p class="wordmark">OMNIS</p><p class="note">Baseline de implementare<br>Document, nu aplicație.</p>{nav}<p class="note">Offline · Ctrl+P pentru print<br>Markdown este sursa editabilă.</p></aside>
<details class="mobile-nav"><summary>OMNIS · Cuprins</summary>{nav}</details>
<div class="page"><main id="content" tabindex="-1"><div class="topline"><span>OMNIS / IMPLEMENTATION BASELINE</span><span class="status">Specificat · starea implementării în document</span></div>
{body}
<footer><div class="links"><a href="{safe_source}">Sursa Markdown</a><a href="Omnis_Implementation_Plan.html">Plan</a><a href="Omnis_MVP_Architecture.html">Arhitectură</a><a href="Omnis_UI_Prototype.html">Prototip DEMO</a></div><p>Generat reproductibil din Markdown. Source SHA-256: <code>{digest}</code>.</p></footer>
</main></div></body></html>
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    docs = Path(__file__).resolve().parents[1] / "documents"
    failed = False
    for name, title in DOCUMENTS:
        source, output = docs / (name + ".md"), docs / (name + ".html")
        if not source.is_file():
            print(f"MISSING source: {source.name}")
            failed = True
            continue
        html = render(source.read_text(encoding="utf-8"), title, source.name)
        if args.check:
            matches = output.is_file() and output.read_text(encoding="utf-8") == html
            print(f"{'OK' if matches else 'STALE'} {output.name}")
            failed |= not matches
        else:
            output.write_text(html, encoding="utf-8")
            print(f"RENDERED {output.name}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
