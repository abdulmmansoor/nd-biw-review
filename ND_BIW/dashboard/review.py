"""Review version only (copied by build_review.py into the review copy as dashboard/review.py).

1. A reviewer password gate. Community Cloud allows one private app per workspace, and ND Fiscal and Economic Watch
   uses it, so this review app is a public app from a PUBLIC repository (the password covers the pages only; the code
   and tables can be read on GitHub) and asks for a review password
   before showing anything. Set_Review_Password.bat makes a salted PBKDF2-SHA256 hash; only the hash goes into the
   app's secrets ([review] block, Streamlit Community Cloud: app > Settings > Secrets). The password itself is never
   stored. If the hosted app has no [review] block, it stays closed (fails closed). Start_Review_Locally.bat sets
   ND_BIW_REVIEW_LOCAL=1 so the copy opens without a password on this computer.
   Wrong attempts pause sign-in: 5 in one browser session pause that session for 10 minutes, 20 across all sessions
   pause sign-in for everyone for 10 minutes.
2. A draft label and a "Comment on this page" button that opens the Microsoft Form in review_settings.toml, with the
   page name filled in.
"""
import hashlib
import hmac
import os
import time
import tomllib
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import streamlit as st

SETTINGS = Path(__file__).resolve().parents[1] / "review_settings.toml"
ITERATIONS = 600_000                   # OWASP 2023 guidance for PBKDF2-HMAC-SHA256
MAX_TRIES, MAX_TRIES_ALL, LOCK_SECONDS = 5, 20, 600


# ------------------------------------------------------------------ password gate
def hash_password(password, salt_hex, iterations=ITERATIONS):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)).hex()


def config():
    """The [review] block from Streamlit secrets, or None when the password is not set up."""
    try:
        c = st.secrets.get("review")
    except Exception:                  # no secrets at all
        return None
    if not c or not all(k in c for k in ("salt", "password_hash")):
        return None
    return dict(c)


def verify(password, conf):
    if not conf or not password:
        return False
    h = hash_password(password, conf["salt"], conf.get("iterations", ITERATIONS))
    return hmac.compare_digest(h.encode(), str(conf["password_hash"]).encode())


@st.cache_resource
def _failures():
    """Failed attempts across all sessions of this server (timestamps)."""
    return []


def _wait():
    now = time.time()
    f = _failures()
    f[:] = [t for t in f if now - t < LOCK_SECONDS]
    mine = st.session_state.get("review_lock_until", 0) - now
    return max(mine, (f[0] + LOCK_SECONDS - now) if len(f) >= MAX_TRIES_ALL else 0)


def gate():
    """Stop the page unless this browser session has entered the review password."""
    s = st.session_state
    if os.environ.get("ND_BIW_REVIEW_LOCAL") == "1" or s.get("review_ok"):
        return
    st.markdown("## ND Business and Innovation Watch: review draft")
    conf = config()
    if not conf:
        st.info("This review site is not open yet.")
        st.stop()
    st.markdown("This draft is shared with invited reviewers. Please enter the review password from your invitation "
                "email.")
    wait = _wait()
    if wait > 0:
        st.warning(f"Sign-in is paused after too many attempts. Try again in {int(wait // 60) + 1} minutes.")
        st.stop()
    with st.form("review_sign_in"):
        pw = st.text_input("Review password", type="password")
        go = st.form_submit_button("Open the review draft")
    if go:
        if verify(pw, conf):
            s.review_ok = True
            s.pop("review_tries", None)
            st.rerun()
        s.review_tries = s.get("review_tries", 0) + 1
        _failures().append(time.time())
        if s.review_tries >= MAX_TRIES or _wait() > 0:
            s.review_lock_until, s.review_tries = time.time() + LOCK_SECONDS, 0
            st.rerun()                                     # show the pause at once, without the sign-in box
        st.error("That password is not right.")
    st.caption("Institute of Policy and Business Analytics, University of North Dakota. If you need access, reply to the "
               "invitation email.")
    st.stop()


# ------------------------------------------------------------------ label and comment button
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
