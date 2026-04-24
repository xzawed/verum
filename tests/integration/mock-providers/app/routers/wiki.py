from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from ._common import log_call

router = APIRouter()
_WIKI_DIR = Path(__file__).parent.parent.parent / "fixtures" / "wiki"


@router.get("/{slug}")
async def get_wiki(slug: str, request: Request):
    log_call(request, f"wiki/{slug}", {})
    html_path = _WIKI_DIR / f"{slug}.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    # Default generic tarot content
    return HTMLResponse(f"""<!DOCTYPE html><html><body>
    <h1>타로 카드 {slug}</h1>
    <p>타로 카드는 고대부터 내려오는 점술 도구입니다. 78장의 카드로 구성되며 Major Arcana 22장과 Minor Arcana 56장으로 이루어집니다.</p>
    <p>Celtic Cross 스프레드는 가장 널리 사용되는 배열법으로 10장의 카드로 과거, 현재, 미래를 읽어냅니다.</p>
    <p>The Fool, The Magician, The High Priestess, The Empress, The Emperor 등 Major Arcana 카드들은 각각 깊은 상징적 의미를 가지고 있습니다.</p>
    </body></html>""")
