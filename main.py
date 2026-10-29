"""Agentic Workflow Engine - Streamlit + Gemini (REST, auto model discovery).
Single file. Asks the API which models your key can use and falls back
automatically, so retired model names never cause a 404.
"""
from datetime import datetime

import requests
import streamlit as st

BASE = "https://generativelanguage.googleapis.com/v1beta"
PREFERRED = [
    "gemini-3.6-flash", "gemini-3.1-flash-lite", "gemini-flash-latest",
    "gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite",
]
SKIP = ("image", "live", "tts", "audio", "embedding", "robotics", "computer-use", "nano-banana")

MODES = {
    "Direct Prompt": (
        "You are an expert AI automation engineer. Answer the request clearly and directly. "
        "Be concise and practical."
    ),
    "Workflow Pipeline": (
        "You are an expert AI automation architect (n8n, Make, Zapier, LLM APIs). "
        "Respond as a structured pipeline with these sections: 1) Trigger, 2) Steps (numbered, with the "
        "tool/node used at each step), 3) Data mapping, 4) Error handling & retries, 5) Scaling notes."
    ),
    "API Payload": (
        "You generate API payloads. Return ONLY valid JSON for the requested webhook/API payload, "
        "no commentary. Use realistic field names and example values."
    ),
}
MODE_HINTS = {
    "Direct Prompt": "Ask anything, get a direct answer.",
    "Workflow Pipeline": "Trigger → steps → error handling → scaling.",
    "API Payload": "Returns clean, copy-ready JSON.",
}

EXAMPLES = [
    ("Order-status bot", "Design a workflow in n8n that answers WhatsApp order-status questions using an LLM and a Shopify lookup."),
    ("Ticket triage", "Design a multi-step webhook pipeline that classifies support tickets, scores priority and escalates urgent ones to Slack."),
    ("Refund payload", "Generate a webhook JSON payload for a refund-request event from an eCommerce store."),
]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, .stApp, .stMarkdown, p, li, label, input, textarea, button { font-family: 'Inter', sans-serif; }
.stApp { background: #0a0f1e; color: #e6e9f2; }
.stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: #e6e9f2; }
[data-testid="stToolbar"], footer, #MainMenu { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 860px; padding-top: 2.4rem; padding-bottom: 6rem; }

section[data-testid="stSidebar"] { background: #0d1326; border-right: 1px solid #19223f; }
section[data-testid="stSidebar"] * { color: #cfd6ea; }
.side-title { font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; color: #6f7b9c !important; margin: 1.1rem 0 .4rem; font-weight: 600; }

.hero h1 { font-size: 2.1rem; font-weight: 700; letter-spacing: -0.025em; margin: 0; color: #f4f6fb; }
.hero h1 span { background: linear-gradient(90deg, #34d399, #60a5fa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.hero p { color: #8a94b3 !important; margin: .35rem 0 1rem; font-size: .98rem; }

.chip { display: inline-flex; align-items: center; gap: .5rem; padding: .28rem .75rem; border: 1px solid #1f2b50; border-radius: 999px; background: #0f1830; color: #a9b6d6; font-size: .78rem; margin-right: .4rem; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #34d399; box-shadow: 0 0 9px #34d399; }
.dot.off { background: #f59e0b; box-shadow: 0 0 9px #f59e0b; }

[data-testid="stChatMessage"] { background: #0f1830; border: 1px solid #1a2547; border-radius: 14px; padding: 1rem 1.15rem; margin-bottom: .7rem; }
[data-testid="stChatInput"] { border-radius: 14px; }
[data-testid="stChatInput"] textarea { color: #e6e9f2; }

.stButton > button, .stDownloadButton > button { border-radius: 10px; border: 1px solid #243360; background: #0f1830; color: #cfd6ea; transition: all .15s; }
.stButton > button:hover, .stDownloadButton > button:hover { border-color: #34d399; color: #34d399; background: #0f1d2e; }

.empty { border: 1px dashed #22305a; border-radius: 14px; padding: 1.4rem 1.3rem; background: #0c1428; margin: 1.2rem 0 1rem; }
.empty h3 { margin: 0 0 .3rem; font-size: 1.05rem; font-weight: 600; }
.empty p { margin: 0; color: #8a94b3 !important; font-size: .92rem; }
pre, code { border-radius: 10px !important; }
</style>
"""

st.set_page_config(page_title="Agentic Workflow Engine", page_icon="⚡", layout="centered",
                   initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)
st.session_state.setdefault("messages", [])
st.session_state.setdefault("logs", [])


# ---------------- Gemini helpers ----------------
@st.cache_data(ttl=3600, show_spinner=False)
def list_models(api_key: str) -> list:
    r = requests.get(f"{BASE}/models", params={"key": api_key, "pageSize": 1000}, timeout=30)
    if r.status_code in (400, 401, 403):
        raise ValueError(f"API key rejected ({r.status_code}). Key dobara check karo.")
    r.raise_for_status()
    return [
        m["name"].split("/", 1)[1]
        for m in r.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]


def candidates(api_key: str) -> list:
    available = list_models(api_key)
    order = [m for m in PREFERRED if m in available]
    extra = [m for m in available if "flash" in m and not any(s in m for s in SKIP) and m not in order]
    order += sorted(extra, reverse=True)
    if not order:
        raise ValueError("Is key par koi usable Gemini model nahi mila.")
    return order


def run_engine(api_key: str, system: str, history: list):
    """Returns (text, model_used). Auto-falls back if a model 404s."""
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [
            {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
            for m in history
        ],
        "generationConfig": {"temperature": 0.3},
    }
    errors = []
    for name in candidates(api_key):
        r = requests.post(f"{BASE}/models/{name}:generateContent", params={"key": api_key},
                          json=body, timeout=90)
        if r.status_code in (400, 404) or r.status_code >= 500:
            errors.append(f"{name}: {r.status_code}")
            continue
        if r.status_code == 429:
            raise ValueError("Quota/rate limit (429). Thodi der ruk kar try karo.")
        r.raise_for_status()
        data = r.json()
        cands = data.get("candidates") or []
        if not cands or "content" not in cands[0]:
            raise ValueError(f"Response blocked/empty: {data.get('promptFeedback', {})}")
        return "".join(p.get("text", "") for p in cands[0]["content"].get("parts", [])), name
    raise ValueError("Saare models fail hue: " + ", ".join(errors))


def log(msg: str):
    st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def export_markdown() -> str:
    out = [f"# Workflow session - {datetime.now().strftime('%d %b %Y, %H:%M')}\n"]
    for m in st.session_state.messages:
        out.append(f"## {'Request' if m['role'] == 'user' else 'Response'}\n\n{m['content']}\n")
    return "\n".join(out)


# ---------------- Sidebar ----------------
with st.sidebar:
    st.markdown("### ⚡ Workflow Engine")
    st.markdown('<div class="side-title">Connection</div>', unsafe_allow_html=True)
    api_token = st.text_input("Gemini API key", type="password", label_visibility="collapsed",
                              placeholder="Paste your Gemini API key")
    st.markdown('<div class="side-title">Mode</div>', unsafe_allow_html=True)
    mode = st.radio("Mode", list(MODES.keys()), label_visibility="collapsed")
    st.caption(MODE_HINTS[mode])
    st.markdown('<div class="side-title">Session</div>', unsafe_allow_html=True)
    n_req = sum(1 for m in st.session_state.messages if m["role"] == "user")
    st.metric("Requests", n_req)
    if st.session_state.messages:
        st.download_button("Export session (.md)", export_markdown(), file_name="workflow-session.md",
                           use_container_width=True)
    if st.button("Clear session", use_container_width=True):
        st.session_state.messages, st.session_state.logs = [], []
        st.rerun()
    with st.expander("Execution logs"):
        st.code("\n".join(st.session_state.logs) or "No activity yet.", language="text")

# ---------------- Header ----------------
st.markdown(
    '<div class="hero"><h1>Agentic <span>Workflow Engine</span></h1>'
    "<p>Describe an automation. Get a production-ready pipeline, trigger map or API payload.</p></div>",
    unsafe_allow_html=True,
)

active_model = None
if api_token:
    try:
        models_ok = candidates(api_token)
        active_model = models_ok[0]
        st.markdown(
            f'<span class="chip"><span class="dot"></span>Engine ready</span>'
            f'<span class="chip">Model · {active_model}</span>'
            f'<span class="chip">Mode · {mode}</span>',
            unsafe_allow_html=True,
        )
    except Exception as initialization_error:
        st.markdown('<span class="chip"><span class="dot off"></span>Connection issue</span>',
                    unsafe_allow_html=True)
        st.error(f"Initialization fault: {initialization_error}")
        st.stop()
else:
    st.markdown('<span class="chip"><span class="dot off"></span>Waiting for API key</span>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="empty"><h3>Connect to get started</h3>'
        "<p>Paste your Gemini API key in the sidebar to initialize the execution engine.</p></div>",
        unsafe_allow_html=True,
    )
    st.stop()

# ---------------- Conversation ----------------
for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="🧑‍💻" if m["role"] == "user" else "⚡"):
        st.markdown(m["content"])
        if m.get("model"):
            st.caption(f"Generated with {m['model']}")

if not st.session_state.messages:
    st.markdown(
        '<div class="empty"><h3>What do you want to automate?</h3>'
        "<p>Pick a starter below or type your own request.</p></div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(len(EXAMPLES))
    for col, (label, text) in zip(cols, EXAMPLES):
        if col.button(label, use_container_width=True):
            st.session_state.pending_prompt = text
            st.rerun()

pending = st.session_state.pop("pending_prompt", None)
prompt = st.chat_input("Describe a workflow, event trigger, or payload...") or pending

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)
    log(f"Mode='{mode}' | prompt received ({len(prompt)} chars)")
    used = None
    with st.chat_message("assistant", avatar="⚡"):
        try:
            with st.spinner("Building your workflow..."):
                reply, used = run_engine(api_token, MODES[mode], st.session_state.messages[-12:])
            st.markdown(reply)
            log(f"Success via {used}")
        except Exception as e:
            reply = f"Execution fault occurred: {e}"
            st.error(reply)
            log(f"FAULT: {e}")
    st.session_state.messages.append({"role": "assistant", "content": reply, "model": used})
    st.rerun()
