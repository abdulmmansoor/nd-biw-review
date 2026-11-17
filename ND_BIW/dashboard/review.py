"""Review version only: a draft label and a "Comment on this page" button (see review_settings.toml)."""
import tomllib
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import streamlit as st

SETTINGS = Path(__file__).resolve().parents[1] / "review_settings.toml"


def settings():
    try:
        return tomllib.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def form_link(url, page):
    """The form address with the page name filled in where the pre-filled link has the word PAGE."""
    p = urlsplit(url)
    q = [(k, page if v == "PAGE" else v) for k, v in parse_qsl(p.query, keep_blank_values=True)]
    return urlunsplit(p._replace(query=urlencode(q)))


def bar(nav):
    s = settings()
    label, url = s.get("label", ""), s.get("form_url", "").strip()
    prefix = s.get("page_prefix", "")
    if not (label or url):
        return
    c = st.columns([5, 2], vertical_alignment="center")
    if label:
        c[0].markdown(f'<div class="review-label">{label}</div>', unsafe_allow_html=True)
    if url.startswith("https://"):
        c[1].link_button("Comment on this page", form_link(url, prefix + nav.title), icon=":material/rate_review:",
                         width="stretch")
    st.markdown("<style>.review-label{font-size:.82rem;color:#E9ECEF;background:#3A3F4B;border-left:3px solid #C9B37E;"
                "padding:6px 10px;border-radius:4px}</style>", unsafe_allow_html=True)
