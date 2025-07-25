import re

REPORTING_VERBS = r"(?:said|stated|announced|added|noted|remarked|commented|explained|mentioned)"
COLON_RE = re.compile(rf"\b({REPORTING_VERBS}),\s*([“\"'])", re.IGNORECASE)

def enforce_colon_before_quote(text: str) -> str:
    return COLON_RE.sub(r"\1: \2", text)

def list_colon_fixes(text: str) -> list[str]:
    """Return human‑readable comments for every change (for the UI)."""
    return [f"Use colon after reporting verb (‘{m.group(1)}’) before quotation."
            for m in COLON_RE.finditer(text)]