"""The public privacy policy and support pages, served on the API domain.

The App Store listing and the app's Settings link here, so no second domain
is needed. The texts are Markdown in ``app/pages``, German in ``*.de.md``:
``?lang=de`` picks it (the app passes its language), otherwise the browser's.
"""
from __future__ import annotations

import html
from functools import lru_cache
from pathlib import Path

import markdown
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.config import settings

router = APIRouter(include_in_schema=False)

_PAGES = Path(__file__).resolve().parents[2] / "pages"

_TEMPLATE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ color-scheme: light dark; --text: #1c1c1e; --muted: #6e6e73; --bg: #ffffff; --line: #d2d2d7; --accent: #6366f1; }}
@media (prefers-color-scheme: dark) {{ :root {{ --text: #f2f2f7; --muted: #a1a1a6; --bg: #000000; --line: #38383a; --accent: #818cf8; }} }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 17px/1.55 -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif; }}
main {{ max-width: 680px; margin: 0 auto; padding: 32px 16px 64px; }}
h1 {{ font-size: 28px; line-height: 1.2; }}
h2 {{ font-size: 20px; margin-top: 32px; }}
a {{ color: var(--accent); }}
table {{ border-collapse: collapse; width: 100%; font-size: 15px; display: block; overflow-x: auto; }}
th, td {{ border-bottom: 1px solid var(--line); padding: 8px 8px 8px 0; text-align: left; vertical-align: top; }}
code {{ font-size: 15px; }}
</style>
</head>
<body><main>
{body}
</main></body>
</html>
"""


_TITLES = {
    "privacy": {"en": "AlibiMe privacy policy", "de": "AlibiMe Datenschutzerklärung"},
    "support": {"en": "AlibiMe support", "de": "AlibiMe Hilfe"},
}


def _language(request: Request) -> str:
    asked = request.query_params.get("lang")
    if asked in ("en", "de"):
        return asked
    first = request.headers.get("accept-language", "").split(",")[0].strip().lower()
    return "de" if first.startswith("de") else "en"


@lru_cache
def _render(name: str, lang: str) -> str:
    suffix = ".de" if lang == "de" else ""
    text = (_PAGES / f"{name}{suffix}.md").read_text(encoding="utf-8")
    email = settings.support_email or "[support email]"
    text = text.replace("{support_email}", f"[{email}](mailto:{email})" if settings.support_email else email)
    body = markdown.markdown(text, extensions=["tables"])
    return _TEMPLATE.format(lang=lang, title=html.escape(_TITLES[name][lang]), body=body)


@router.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request) -> str:
    return _render("privacy", _language(request))


@router.get("/support", response_class=HTMLResponse)
def support(request: Request) -> str:
    return _render("support", _language(request))
