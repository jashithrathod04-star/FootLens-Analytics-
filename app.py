# -*- coding: utf-8 -*-
"""
FOOTLENS 3.0 — Football Injury Intelligence Platform
Run with:  streamlit run app.py
Needs footlens_cleaned_injuries.csv beside this file (or upload one in the sidebar).
"""

import hashlib
import html as _html
import inspect
import re
from datetime import datetime
from io import BytesIO
from urllib.parse import quote

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# ==========================================================
# PAGE CONFIG
# ==========================================================

st.set_page_config(
    page_title="FootLens | Injury Intelligence",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Rows without an injury date are kept unless the person narrows the date range.
# Set to False to restore the original behaviour (undated rows always dropped).
KEEP_UNDATED_RECORDS = True

# ==========================================================
# DESIGN TOKENS
# ==========================================================

PAL = dict(
    cyan="#22d3ee", emerald="#2ef2a0", violet="#9b7bff",
    amber="#ffb454", coral="#ff6b7d", ink="#eaf2ff", mute="#8fa3bf",
)

CAT_COLORS = {
    "Muscle": "#22d3ee",
    "Ligament & tendon": "#9b7bff",
    "Joint & other": "#2ef2a0",
    "Bone & fracture": "#ffb454",
    "Knock & bruise": "#ff9f7a",
    "Head & neck": "#6ea8ff",
    "Illness": "#ff6b7d",
    "Unspecified": "#6b7f9c",
    "Other": "#4f6382",
}
GROUP_COLORS = {
    "Goalkeeper": "#ffb454", "Defender": "#22d3ee",
    "Midfielder": "#2ef2a0", "Forward": "#9b7bff", "Other": "#6b7f9c",
}
AURORA = [[0, "#09172e"], [0.35, "#1c5fb0"], [0.7, "#22d3ee"], [1, "#2ef2a0"]]
VIOLET_SCALE = [[0, "#0d1530"], [0.5, "#5b3fd6"], [1, "#b79cff"]]
GRID = "rgba(150,180,220,.08)"

MONTHS_SEASON = ["August", "September", "October", "November", "December",
                 "January", "February", "March", "April", "May", "June", "July"]
AGE_ORDER = ["≤21", "22–25", "26–29", "30–33", "34+"]
BAND_ORDER = ["1–7 d", "8–14 d", "15–28 d", "29–60 d", "61–120 d", "120+ d"]

NAV_ITEMS = [
    ("Command Centre", "grid"),
    ("Injury Intelligence", "pulse"),
    ("Player Recovery Lab", "user"),
    ("Club Comparison Studio", "bars"),
    ("Data Explorer", "table"),
    ("Methodology", "book"),
]

ICON_PATHS = {
    "grid": "<rect x='3' y='3' width='7' height='9' rx='1.5'/><rect x='14' y='3' width='7' height='5' rx='1.5'/><rect x='14' y='12' width='7' height='9' rx='1.5'/><rect x='3' y='16' width='7' height='5' rx='1.5'/>",
    "pulse": "<path d='M3 12h4l2-6 4 12 2-6h6'/>",
    "user": "<circle cx='12' cy='8' r='4'/><path d='M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7'/>",
    "bars": "<path d='M6 20V10M12 20V4M18 20v-7'/>",
    "table": "<rect x='3' y='4' width='18' height='16' rx='2'/><path d='M3 10h18M9 4v16'/>",
    "book": "<path d='M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2z'/><path d='M4 19V5'/>",
    "clock": "<circle cx='12' cy='12' r='9'/><path d='M12 7v5l3 2'/>",
    "trend": "<path d='M3 17l6-6 4 4 8-8'/><path d='M15 7h6v6'/>",
    "shield": "<path d='M12 3l8 3v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6z'/>",
    "download": "<path d='M12 4v11M7 11l5 5 5-5M5 20h14'/>",
    "filter": "<path d='M4 5h16l-6 7v6l-4 2v-8z'/>",
}


def icon_svg(name, size=18, color="currentColor", sw=1.8):
    return (
        f"<svg width='{size}' height='{size}' viewBox='0 0 24 24' fill='none' "
        f"stroke='{color}' stroke-width='{sw}' stroke-linecap='round' "
        f"stroke-linejoin='round'>{ICON_PATHS.get(name, '')}</svg>"
    )


def _icon_uri(name):
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' "
        "stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>"
        + ICON_PATHS[name] + "</svg>"
    )
    return "url(\"data:image/svg+xml," + quote(svg) + "\")"


def _nav_icon_css():
    out = []
    for i, (_, icon) in enumerate(NAV_ITEMS, start=1):
        uri = _icon_uri(icon)
        out.append(
            "section[data-testid='stSidebar'] div[role='radiogroup'] > label:nth-of-type(%d)::before"
            "{-webkit-mask-image:%s;mask-image:%s;}" % (i, uri, uri)
        )
    return "\n".join(out)


# ==========================================================
# GENERIC HELPERS
# ==========================================================

def esc(value):
    return _html.escape("" if value is None else str(value), quote=True)


def H(markup):
    """Collapse whitespace so Markdown never mistakes HTML for a code block."""
    markup = re.sub(r"\n\s*", " ", markup)
    return re.sub(r">\s+<", "><", markup).strip()


def render(markup):
    st.markdown(H(markup), unsafe_allow_html=True)


def _stretch(fn):
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return {}
    if "use_container_width" in params:
        return {"use_container_width": True}
    if "width" in params:
        return {"width": "stretch"}
    return {}


SK_CHART = _stretch(st.plotly_chart)
SK_DF = _stretch(st.dataframe)
SK_BTN = _stretch(st.button)
SK_DL = _stretch(st.download_button)
SK_FORM = _stretch(st.form_submit_button)
PLOT_CONFIG = {"displayModeBar": False, "displaylogo": False, "responsive": True}


def show(fig, key):
    st.plotly_chart(fig, config=PLOT_CONFIG, theme=None, key=key, **SK_CHART)


def safe_num(frame, col):
    if col in frame.columns:
        return pd.to_numeric(frame[col], errors="coerce")
    return pd.Series(np.nan, index=frame.index, dtype=float)


def fmt_mean(series, decimals=1, suffix=""):
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return "—"
    return f"{values.mean():,.{decimals}f}{suffix}"


def first_existing(frame, candidates):
    return next((c for c in candidates if c in frame.columns), None)


def pct(part, whole):
    return 0.0 if not whole else 100.0 * part / whole


def hue_of(text):
    return int(hashlib.md5(str(text).encode("utf-8")).hexdigest()[:6], 16) % 360


# ==========================================================
# CHART STYLING
# ==========================================================

def style_fig(fig, height=380, legend=False):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, sans-serif", color="#c9d8ee", size=12),
        margin=dict(l=18, r=18, t=26, b=22),
        height=height,
        showlegend=legend,
        legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)",
                    title=dict(text=""), font=dict(size=11)),
        hoverlabel=dict(
            bgcolor="rgba(7,14,29,.96)", bordercolor=PAL["cyan"],
            font=dict(family="DM Sans, sans-serif", color="#f2f7ff", size=12),
        ),
        transition=dict(duration=450, easing="cubic-in-out"),
    )
    axis = dict(
        gridcolor=GRID, zeroline=False, showline=False,
        tickfont=dict(size=11, color="#8fa3bf"),
        title_font=dict(size=11, color="#8fa3bf"),
    )
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


def gradient_area(x, y, color_rgb, name, hover):
    """Gradient-filled area; falls back to a flat fill on older Plotly."""
    base = dict(
        x=x, y=y, name=name, mode="lines+markers",
        line=dict(color=f"rgb({color_rgb})", width=2.6, shape="spline", smoothing=0.7),
        marker=dict(size=6, color="#07101f", line=dict(color=f"rgb({color_rgb})", width=2)),
        fill="tozeroy", hovertemplate=hover,
    )
    try:
        return go.Scatter(
            **base,
            fillgradient=dict(
                type="vertical",
                colorscale=[[0, f"rgba({color_rgb},0)"], [1, f"rgba({color_rgb},.42)"]],
            ),
        )
    except (ValueError, TypeError):
        return go.Scatter(**base, fillcolor=f"rgba({color_rgb},.16)")


# ==========================================================
# GLOBAL CSS (injected once per run)
# ==========================================================

BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=Manrope:wght@400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');

:root{
  --obsidian:#050912; --navy:#0a1428; --navy2:#0f1d3a;
  --cyan:#22d3ee; --emerald:#2ef2a0; --violet:#9b7bff; --amber:#ffb454; --coral:#ff6b7d;
  --ink:#eaf2ff; --mute:#8fa3bf; --line:rgba(150,180,220,.15);
  --glass:linear-gradient(150deg,rgba(30,50,92,.58),rgba(9,18,36,.62));
}
html{color-scheme:dark}
.stApp{
  color:var(--ink);
  font-family:'DM Sans',sans-serif;
  background:
    linear-gradient(rgba(120,160,220,.035) 1px,transparent 1px),
    linear-gradient(90deg,rgba(120,160,220,.035) 1px,transparent 1px),
    radial-gradient(ellipse at 50% 120%,rgba(34,211,238,.07),transparent 50%),
    #050912;
  background-size:46px 46px,46px 46px,auto,auto;
  background-attachment:fixed;
}
/* aurora + particles live on pseudo-elements so no DOM is injected */
.stApp::before{
  content:"";position:fixed;inset:-30% -15% auto -15%;height:100vh;z-index:0;pointer-events:none;
  background:
    radial-gradient(ellipse 38% 52% at 18% 32%,rgba(34,211,238,.22),transparent 70%),
    radial-gradient(ellipse 34% 48% at 68% 18%,rgba(155,123,255,.22),transparent 70%),
    radial-gradient(ellipse 28% 42% at 92% 58%,rgba(46,242,160,.15),transparent 70%);
  filter:blur(34px);animation:aurora 24s ease-in-out infinite alternate;
}
.stApp::after{
  content:"";position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.7;
  background-image:
    radial-gradient(circle,rgba(255,255,255,.55) 0 1px,transparent 1.6px),
    radial-gradient(circle,rgba(34,211,238,.6) 0 1.3px,transparent 2.2px),
    radial-gradient(circle,rgba(155,123,255,.55) 0 1.1px,transparent 2px);
  background-size:230px 230px,340px 340px,470px 470px;
  background-position:20px 40px,110px 150px,210px 70px;
  animation:drift 80s linear infinite;
  -webkit-mask-image:radial-gradient(ellipse at 50% 40%,#000 25%,transparent 85%);
  mask-image:radial-gradient(ellipse at 50% 40%,#000 25%,transparent 85%);
}
@keyframes aurora{
  0%{transform:translate3d(-3%,0,0) scale(1) rotate(0deg)}
  50%{transform:translate3d(3%,-4%,0) scale(1.08) rotate(2deg)}
  100%{transform:translate3d(-1%,3%,0) scale(1.03) rotate(-2deg)}
}
@keyframes drift{
  to{background-position:20px -190px,110px -190px,210px -400px}
}
@keyframes rise{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
@keyframes pulseDot{0%{box-shadow:0 0 0 0 rgba(46,242,160,.55)}100%{box-shadow:0 0 0 10px rgba(46,242,160,0)}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(7px)}}
@keyframes marquee{to{transform:translateX(-50%)}}
@keyframes sheen{0%{background-position:-120% 0}100%{background-position:220% 0}}
@keyframes revealIn{from{opacity:0;transform:translateY(36px) scale(.98)}to{opacity:1;transform:none}}
@keyframes splashOut{to{opacity:0;visibility:hidden}}
@keyframes loadbar{0%{transform:translateX(-110%)}100%{transform:translateX(260%)}}

[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:transparent;position:relative;z-index:1}
[data-testid="stHeader"]{background:transparent}
footer{visibility:hidden}
.block-container{max-width:1560px;padding-top:2.4rem;padding-bottom:3rem}

h1,h2,h3,h4{font-family:'Space Grotesk',sans-serif!important;letter-spacing:-.035em;color:#f3f8ff}
p,li,label,span{font-family:'DM Sans',sans-serif}
.mono{font-family:'DM Mono',monospace}
.grad{background:linear-gradient(95deg,var(--a,#22d3ee),var(--b,#9b7bff));-webkit-background-clip:text;background-clip:text;color:transparent}
.rise{animation:rise .65s cubic-bezier(.2,.7,.2,1) both;animation-delay:calc(var(--i,0)*70ms)}
@supports (animation-timeline:view()){
  .reveal{animation:revealIn linear both;animation-timeline:view();animation-range:entry 0% cover 30%}
}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"]{
  background:linear-gradient(180deg,rgba(10,19,38,.88),rgba(5,9,19,.94));
  backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);
  border-right:1px solid var(--line);box-shadow:14px 0 50px rgba(0,0,0,.28);
}
section[data-testid="stSidebar"] > div{padding-top:.4rem}
.brand{display:flex;align-items:center;gap:.75rem;padding:.4rem .2rem 1rem}
.brand-name{font:700 1.18rem 'Space Grotesk';letter-spacing:.14em;color:#f4f9ff}
.brand-sub{font:500 .58rem 'DM Mono';letter-spacing:.16em;color:var(--mute);margin-top:2px}
.ring-spin{transform-origin:50% 50%;animation:spin 14s linear infinite}
.analyst{display:flex;gap:.75rem;align-items:center;padding:.8rem;border-radius:16px;margin-bottom:.9rem;
  background:linear-gradient(150deg,rgba(34,211,238,.09),rgba(155,123,255,.06));
  border:1px solid rgba(34,211,238,.2);box-shadow:inset 0 1px 0 rgba(255,255,255,.06)}
.analyst b{font:700 .92rem 'Manrope';color:#f2f8ff;display:block}
.analyst span{font:500 .62rem 'DM Mono';color:var(--mute);letter-spacing:.06em}
.side-label{font:500 .62rem 'DM Mono';letter-spacing:.18em;color:#6f86a6;text-transform:uppercase;margin:1.1rem 0 .5rem}
.status{display:flex;align-items:center;gap:.6rem;padding:.65rem .8rem;border-radius:14px;margin-top:.8rem;
  background:rgba(7,14,29,.7);border:1px solid var(--line);
  box-shadow:inset 2px 2px 7px rgba(0,0,0,.4),inset -1px -1px 3px rgba(130,170,230,.05)}
.status .dot{width:9px;height:9px;border-radius:50%;background:var(--emerald);animation:pulseDot 1.8s infinite}
.status.warn .dot{background:var(--amber);animation:none}
.status b{font:600 .78rem 'Manrope';color:#e7f1ff;display:block}
.status span{font:500 .62rem 'DM Mono';color:var(--mute)}

/* navigation radio -> custom nav */
section[data-testid="stSidebar"] div[role="radiogroup"]{display:flex;flex-direction:column;gap:.3rem}
section[data-testid="stSidebar"] div[role="radiogroup"] > label{
  position:relative;margin:0;padding:.72rem .9rem .72rem 2.9rem;border-radius:13px;
  border:1px solid transparent;cursor:pointer;
  transition:background .25s ease,border-color .25s ease,transform .25s ease,box-shadow .25s ease;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child{display:none!important}
section[data-testid="stSidebar"] div[role="radiogroup"] > label p{
  font:600 .88rem 'Manrope',sans-serif;color:#a4b8d4;margin:0;transition:color .25s ease}
section[data-testid="stSidebar"] div[role="radiogroup"] > label::before{
  content:"";position:absolute;left:.95rem;top:50%;width:19px;height:19px;margin-top:-9.5px;
  background:#7088aa;-webkit-mask-size:contain;mask-size:contain;-webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;
  transition:background .25s ease,transform .3s cubic-bezier(.3,1.6,.5,1);
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label::after{
  content:"";position:absolute;left:0;top:24%;height:52%;width:3px;border-radius:3px;
  background:linear-gradient(180deg,var(--cyan),var(--violet));
  transform:scaleY(0);transition:transform .3s cubic-bezier(.3,1.4,.5,1);
  box-shadow:0 0 14px rgba(34,211,238,.8);
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover{
  background:rgba(120,160,230,.08);transform:translateX(3px)}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover::before{background:#cfe3ff;transform:scale(1.12)}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover p{color:#eaf3ff}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked){
  background:linear-gradient(90deg,rgba(34,211,238,.17),rgba(155,123,255,.07));
  border-color:rgba(34,211,238,.3);
  box-shadow:0 0 26px rgba(34,211,238,.12),inset 0 1px 0 rgba(255,255,255,.07);
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked)::after{transform:scaleY(1)}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked)::before{background:var(--cyan)}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p{color:#fff}

/* ---------- hero + page identity ---------- */
.hero{position:relative;overflow:hidden;border-radius:30px;padding:clamp(1.8rem,4vw,3.6rem);
  border:1px solid rgba(139,190,240,.2);
  background:linear-gradient(120deg,rgba(14,32,62,.78),rgba(12,22,48,.62) 60%,rgba(18,50,60,.55));
  box-shadow:0 30px 90px rgba(0,0,0,.35),inset 0 1px 0 rgba(255,255,255,.08);backdrop-filter:blur(18px)}
.page-hero{--a:#22d3ee;--b:#9b7bff;position:relative;overflow:hidden;border-radius:26px;
  padding:clamp(1.4rem,3vw,2.3rem) clamp(1.4rem,3vw,2.6rem);margin-bottom:1.4rem;
  border:1px solid rgba(150,190,240,.18);
  background:
    radial-gradient(ellipse 50% 90% at 100% 0%,color-mix(in srgb,var(--a) 22%,transparent),transparent 70%),
    linear-gradient(135deg,rgba(14,28,56,.78),rgba(8,16,34,.7));
  box-shadow:0 24px 70px rgba(0,0,0,.32),inset 0 1px 0 rgba(255,255,255,.07);
  animation:rise .7s cubic-bezier(.2,.7,.2,1) both}
.page-hero::after{content:"";position:absolute;left:0;right:0;bottom:0;height:2px;
  background:linear-gradient(90deg,transparent,var(--a),var(--b),transparent);opacity:.7;
  transform-origin:left;animation:grow 1.2s cubic-bezier(.2,.7,.2,1) both}
.page-hero h1,.hero h1,.profile .nm{padding:0!important}
.page-hero h1{font:700 clamp(1.9rem,3.6vw,3.1rem)/1.04 'Space Grotesk';margin:.5rem 0 .6rem;max-width:760px}
.page-hero p{color:#aabdd8;max-width:640px;font-size:.98rem;line-height:1.65;margin:0}
.page-hero .motif{position:absolute;right:2%;top:50%;transform:translateY(-50%);opacity:.55;pointer-events:none}
.eyebrow{display:inline-flex;align-items:center;gap:.55rem;font:500 .68rem 'DM Mono',monospace;letter-spacing:.17em;
  text-transform:uppercase;color:var(--a,#2ef2a0);
  background:linear-gradient(90deg,var(--a,#2ef2a0),#c8fff0,var(--a,#2ef2a0));background-size:220% 100%;
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;animation:sheen 6s linear infinite}
.eyebrow::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--a,#2ef2a0);
  -webkit-text-fill-color:initial;animation:pulseDot 1.8s infinite}

/* ---------- panels ---------- */
.panel{position:relative;overflow:hidden;border-radius:20px;padding:1.15rem 1.25rem;
  background:var(--glass);border:1px solid rgba(155,190,230,.17);
  box-shadow:0 18px 50px rgba(0,0,0,.25),inset 0 1px 0 rgba(255,255,255,.06);
  backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);
  transition:transform .3s cubic-bezier(.2,.7,.2,1),border-color .3s ease,box-shadow .3s ease}
.panel:hover{transform:translateY(-4px);border-color:rgba(34,211,238,.4);
  box-shadow:0 26px 60px rgba(0,0,0,.34),0 0 30px rgba(34,211,238,.08)}
.panel.flat:hover{transform:none}
.sec-kicker{font:500 .66rem 'DM Mono';letter-spacing:.16em;text-transform:uppercase;color:var(--cyan);margin-top:.4rem}
.sec-title{font:700 1.35rem 'Space Grotesk';letter-spacing:-.03em;margin:.15rem 0 .2rem;color:#f4f9ff}
.sec-desc{color:#8fa3bf;font-size:.86rem;line-height:1.5;margin-bottom:.55rem;max-width:760px}
.chip{display:inline-flex;align-items:center;gap:.4rem;border-radius:99px;padding:.34rem .7rem;margin:.18rem .25rem .18rem 0;
  font:500 .68rem 'DM Mono';letter-spacing:.04em;color:#bff7ea;background:rgba(46,242,160,.08);border:1px solid rgba(46,242,160,.25)}
.chip.c{color:#b6f1ff;background:rgba(34,211,238,.08);border-color:rgba(34,211,238,.28)}
.chip.v{color:#d9ccff;background:rgba(155,123,255,.1);border-color:rgba(155,123,255,.3)}
.chip.a{color:#ffe2b8;background:rgba(255,180,84,.09);border-color:rgba(255,180,84,.3)}
.chip.r{color:#ffc9d0;background:rgba(255,107,125,.09);border-color:rgba(255,107,125,.3)}
.divider{height:1px;margin:1.6rem 0;background:linear-gradient(90deg,transparent,rgba(140,180,230,.28),transparent)}
.callout{padding:1rem 1.25rem;border-radius:0 14px 14px 0;border-left:3px solid var(--emerald);
  background:linear-gradient(90deg,rgba(46,242,160,.08),rgba(46,242,160,.01));color:#b9cbe0;font-size:.9rem;line-height:1.6}

.insight{display:flex;gap:.85rem;align-items:flex-start;--t:var(--cyan)}
.insight .ico{flex:none;width:38px;height:38px;border-radius:12px;display:grid;place-items:center;color:var(--t);
  background:color-mix(in srgb,var(--t) 11%,#0a1428);border:1px solid color-mix(in srgb,var(--t) 35%,transparent);
  box-shadow:3px 3px 9px rgba(0,0,0,.4),-2px -2px 6px rgba(120,160,230,.05)}
.insight .t{font:600 .64rem 'DM Mono';letter-spacing:.14em;text-transform:uppercase;color:var(--t)}
.insight .h{font:700 1.12rem 'Manrope';color:#f3f8ff;margin:.2rem 0 .25rem;letter-spacing:-.02em}
.insight .b{color:#9db1ca;font-size:.83rem;line-height:1.55}

.meter{margin:.7rem 0}
.meter .row{display:flex;justify-content:space-between;font-size:.8rem;color:#c3d3e8}
.meter .row b{font:600 .74rem 'DM Mono';color:#eaf3ff}
.meter .track{height:8px;border-radius:9px;margin-top:.4rem;background:rgba(8,16,32,.8);
  box-shadow:inset 1px 2px 4px rgba(0,0,0,.55);overflow:hidden}
.meter .track i{display:block;height:100%;border-radius:9px;transform-origin:left;animation:grow 1.1s cubic-bezier(.2,.7,.2,1) both;
  background:linear-gradient(90deg,var(--c1,#22d3ee),var(--c2,#2ef2a0));box-shadow:0 0 12px rgba(34,211,238,.45)}
.lb{display:grid;grid-template-columns:1.6rem 1fr auto;gap:.2rem .75rem;align-items:center;padding:.5rem 0;
  border-bottom:1px solid rgba(150,180,220,.08)}
.lb:last-child{border-bottom:none}
.lb .rk{font:500 .7rem 'DM Mono';color:#5f7696}
.lb .nm{font:600 .86rem 'Manrope';color:#e8f1ff}
.lb .vl{font:600 .78rem 'DM Mono';color:#bff7ea}
.lb .bar{grid-column:2 / 4;height:4px;border-radius:4px;background:rgba(150,180,220,.1);overflow:hidden}
.lb .bar i{display:block;height:100%;transform-origin:left;animation:grow 1s cubic-bezier(.2,.7,.2,1) both;
  background:linear-gradient(90deg,var(--cyan),var(--violet))}

/* player profile */
.profile{display:grid;grid-template-columns:auto 1fr auto;gap:1.6rem;align-items:center;padding:1.6rem;border-radius:28px;
  border:1px solid rgba(150,190,240,.2);position:relative;overflow:hidden;
  background:
    radial-gradient(ellipse 45% 120% at 0% 0%,color-mix(in srgb,var(--h,#22d3ee) 22%,transparent),transparent 70%),
    linear-gradient(135deg,rgba(14,28,56,.82),rgba(8,16,34,.72));
  box-shadow:0 28px 80px rgba(0,0,0,.35),inset 0 1px 0 rgba(255,255,255,.07)}
.profile .nm{font:700 clamp(1.8rem,3.4vw,3rem)/1 'Space Grotesk';letter-spacing:-.04em;color:#f6faff}
.profile .meta{margin-top:.7rem}
.status-glow{display:inline-flex;align-items:center;gap:.5rem;padding:.5rem .9rem;border-radius:99px;font:600 .78rem 'DM Mono';
  color:var(--t);background:color-mix(in srgb,var(--t) 10%,transparent);border:1px solid color-mix(in srgb,var(--t) 40%,transparent);
  box-shadow:0 0 24px color-mix(in srgb,var(--t) 28%,transparent)}
.status-glow i{width:8px;height:8px;border-radius:50%;background:var(--t);box-shadow:0 0 10px var(--t)}
.tl{position:relative;padding-left:1.6rem;margin-left:.4rem}
.tl::before{content:"";position:absolute;left:5px;top:6px;bottom:6px;width:2px;
  background:linear-gradient(180deg,var(--cyan),var(--violet),transparent);transform-origin:top;animation:grow 1.4s ease both;
  -webkit-mask-image:none}
.tl-item{position:relative;margin-bottom:.9rem;animation:rise .6s cubic-bezier(.2,.7,.2,1) both;animation-delay:calc(var(--i,0)*120ms)}
.tl-item::before{content:"";position:absolute;left:-1.6rem;top:1rem;width:12px;height:12px;border-radius:50%;
  background:#07101f;border:2px solid var(--t,var(--cyan));box-shadow:0 0 14px var(--t,var(--cyan))}
.tl-card{padding:.9rem 1.1rem;border-radius:16px;background:var(--glass);border:1px solid rgba(155,190,230,.16);
  transition:transform .25s ease,border-color .25s ease}
.tl-card:hover{transform:translateX(5px);border-color:color-mix(in srgb,var(--t,#22d3ee) 55%,transparent)}
.tl-card .d{font:500 .66rem 'DM Mono';color:#7f95b4;letter-spacing:.08em}
.tl-card .n{font:700 1.02rem 'Manrope';color:#f1f7ff;margin:.2rem 0 .45rem}

.skel{border-radius:18px;background:linear-gradient(90deg,rgba(255,255,255,.035),rgba(255,255,255,.1),rgba(255,255,255,.035));
  background-size:200% 100%;animation:shimmer 1.5s linear infinite;border:1px solid var(--line)}

/* ---------- splash (cosmetic intro, shown once per session) ---------- */
.splash{position:fixed;inset:0;z-index:99999;display:grid;place-items:center;text-align:center;
  background:radial-gradient(ellipse at 50% 40%,#0b1c3a,#050912 70%);animation:splashOut .7s ease 1.5s forwards}
.splash .logo{filter:drop-shadow(0 0 22px rgba(34,211,238,.6))}
.splash h2{font:700 2.1rem 'Space Grotesk';letter-spacing:.3em;margin:1.1rem 0 .4rem;color:#f4f9ff}
.splash p{font:500 .7rem 'DM Mono';letter-spacing:.24em;color:var(--mute);margin:0}
.splash .bar{width:220px;height:3px;margin:1.6rem auto 0;border-radius:3px;overflow:hidden;background:rgba(150,180,220,.14)}
.splash .bar i{display:block;width:40%;height:100%;border-radius:3px;background:linear-gradient(90deg,var(--cyan),var(--violet));animation:loadbar 1.1s ease-in-out infinite}

/* ---------- landing extras ---------- */
.ticker{overflow:hidden;border-block:1px solid var(--line);padding:.85rem 0;margin:1.2rem 0 .4rem;
  -webkit-mask-image:linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent);mask-image:linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent)}
.ticker .rail{display:flex;gap:3rem;width:max-content;animation:marquee 38s linear infinite}
.ticker span{font:500 .74rem 'DM Mono';letter-spacing:.12em;color:#8fa3bf;white-space:nowrap;text-transform:uppercase}
.ticker b{color:#bff7ea;font-weight:500}
.scroll-hint{display:flex;align-items:center;gap:.8rem;color:#6f86a6;font:500 .64rem 'DM Mono';letter-spacing:.2em;margin-top:1.6rem}
.scroll-hint .m{width:20px;height:32px;border:1.5px solid rgba(150,190,240,.4);border-radius:11px;position:relative}
.scroll-hint .m::after{content:"";position:absolute;left:50%;top:6px;width:3px;height:7px;margin-left:-1.5px;border-radius:3px;
  background:var(--cyan);animation:bob 1.5s ease-in-out infinite}
.feat{padding:1.3rem;min-height:190px}
.feat .ico{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;color:var(--cyan);margin-bottom:.9rem;
  background:linear-gradient(145deg,#0f2040,#081428);border:1px solid rgba(34,211,238,.25);
  box-shadow:5px 5px 14px rgba(0,0,0,.5),-3px -3px 9px rgba(120,160,230,.06)}
.feat .ft{font:700 1.02rem 'Manrope';color:#f1f7ff}
.feat .fc{color:#98acc6;font-size:.84rem;line-height:1.55;margin-top:.4rem}
.site-foot{margin-top:3rem;padding:2rem 0 .6rem;border-top:1px solid var(--line);display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr;gap:2rem}
.site-foot h5{font:500 .62rem 'DM Mono';letter-spacing:.18em;color:#6f86a6;margin:0 0 .7rem;text-transform:uppercase}
.site-foot p,.site-foot li{color:#8fa3bf;font-size:.82rem;line-height:1.7;margin:0;list-style:none;padding:0}
.legal{text-align:center;color:#566c88;font:500 .62rem 'DM Mono';letter-spacing:.12em;padding:1.4rem 0 .2rem}

/* ---------- streamlit widgets ---------- */
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{
  position:relative;overflow:hidden;border-radius:13px!important;padding:.62rem 1.15rem!important;
  font:700 .88rem 'Manrope',sans-serif!important;letter-spacing:.01em;
  border:1px solid rgba(150,190,240,.28)!important;color:#dbe9ff!important;
  background:linear-gradient(150deg,rgba(30,50,92,.7),rgba(10,20,40,.8))!important;
  box-shadow:5px 5px 14px rgba(0,0,0,.4),-2px -2px 8px rgba(120,160,230,.05),inset 0 1px 0 rgba(255,255,255,.07);
  transition:transform .22s cubic-bezier(.2,.7,.2,1),box-shadow .22s ease,border-color .22s ease!important}
.stButton>button:hover,.stDownloadButton>button:hover,.stFormSubmitButton>button:hover{
  transform:translateY(-3px);border-color:rgba(34,211,238,.6)!important;
  box-shadow:0 14px 34px rgba(0,0,0,.4),0 0 24px rgba(34,211,238,.22)}
.stButton>button:active,.stDownloadButton>button:active,.stFormSubmitButton>button:active{transform:translateY(1px) scale(.985);transition-duration:.06s!important}
.stButton>button:focus-visible,.stDownloadButton>button:focus-visible{outline:2px solid var(--cyan);outline-offset:3px}
button[data-testid="stBaseButton-primary"],button[kind="primary"],button[data-testid="stBaseButton-primaryFormSubmit"]{
  color:#04141d!important;border-color:rgba(46,242,160,.55)!important;
  background:linear-gradient(100deg,#22d3ee,#2ef2a0,#22d3ee)!important;background-size:220% 100%!important;
  box-shadow:0 8px 30px rgba(34,211,238,.28),inset 0 1px 0 rgba(255,255,255,.4)}
button[data-testid="stBaseButton-primary"]:hover,button[kind="primary"]:hover,button[data-testid="stBaseButton-primaryFormSubmit"]:hover{
  background-position:100% 0!important;box-shadow:0 16px 44px rgba(34,211,238,.42),0 0 30px rgba(46,242,160,.3)}
button[data-testid="stBaseButton-primary"] p,button[kind="primary"] p{color:#04141d!important}
div[class*="st-key-cta_"] button p::after{content:"\\2192";display:inline-block;margin-left:.55rem;transition:transform .25s cubic-bezier(.3,1.6,.5,1)}
div[class*="st-key-cta_"] button:hover p::after{transform:translateX(6px)}

div[data-baseweb="input"],div[data-baseweb="base-input"],div[data-baseweb="select"] > div,div[data-baseweb="textarea"]{
  background:rgba(6,13,28,.75)!important;border-color:rgba(150,180,220,.16)!important;border-radius:12px!important;
  box-shadow:inset 2px 2px 7px rgba(0,0,0,.5),inset -1px -1px 3px rgba(130,170,230,.05)}
div[data-baseweb="input"]:focus-within,div[data-baseweb="select"] > div:focus-within{
  border-color:rgba(34,211,238,.65)!important;box-shadow:inset 2px 2px 7px rgba(0,0,0,.5),0 0 0 3px rgba(34,211,238,.14)}
span[data-baseweb="tag"]{background:rgba(34,211,238,.14)!important;border:1px solid rgba(34,211,238,.3);border-radius:8px!important}
span[data-baseweb="tag"] span{color:#c4f4ff!important}
div[data-testid="stSlider"] [role="slider"]{background:var(--cyan)!important;box-shadow:0 0 14px rgba(34,211,238,.7)}
label[data-testid="stWidgetLabel"] p,.stSelectbox label p,.stMultiSelect label p,.stTextInput label p{
  font:500 .7rem 'DM Mono'!important;letter-spacing:.1em;color:#8fa3bf!important;text-transform:uppercase}

.stTabs [data-baseweb="tab-list"]{gap:.3rem;padding:.35rem;border-radius:15px;background:rgba(6,13,28,.7);border:1px solid var(--line);
  box-shadow:inset 2px 2px 8px rgba(0,0,0,.45);flex-wrap:wrap}
.stTabs [data-baseweb="tab"]{border-radius:11px;padding:.5rem 1rem;color:#9db1ca;font:600 .85rem 'Manrope';transition:all .22s ease;height:auto}
.stTabs [data-baseweb="tab"]:hover{background:rgba(120,160,230,.1);color:#fff}
.stTabs [aria-selected="true"]{background:linear-gradient(135deg,rgba(34,211,238,.2),rgba(155,123,255,.14))!important;color:#fff!important;
  box-shadow:0 0 18px rgba(34,211,238,.18),inset 0 0 0 1px rgba(34,211,238,.3)}
.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{display:none}
div[data-testid="stExpander"]{border:1px solid var(--line);border-radius:16px;background:rgba(10,20,40,.55);backdrop-filter:blur(14px)}
div[data-testid="stExpander"] summary:hover{color:var(--cyan)}
[data-testid="stMetric"]{background:var(--glass);border:1px solid var(--line);padding:.9rem 1rem;border-radius:16px;
  box-shadow:4px 4px 12px rgba(0,0,0,.35),-2px -2px 7px rgba(120,160,230,.04)}
[data-testid="stMetricLabel"] p{font:500 .66rem 'DM Mono'!important;letter-spacing:.12em;text-transform:uppercase;color:#8fa3bf!important}
[data-testid="stMetricValue"]{font-family:'Manrope',sans-serif;font-weight:800;color:#f2f8ff}
div[data-testid="stPlotlyChart"]{border:1px solid rgba(150,185,225,.15);border-radius:20px;padding:.3rem;
  background:linear-gradient(160deg,rgba(18,32,60,.5),rgba(7,14,29,.5));box-shadow:0 14px 40px rgba(0,0,0,.22);
  transition:border-color .3s ease,box-shadow .3s ease,transform .3s cubic-bezier(.2,.7,.2,1)}
div[data-testid="stPlotlyChart"]:hover{border-color:rgba(34,211,238,.4);box-shadow:0 22px 54px rgba(0,0,0,.32),0 0 26px rgba(34,211,238,.07);transform:translateY(-2px)}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:16px;overflow:hidden;box-shadow:0 14px 40px rgba(0,0,0,.25)}
[data-testid="stSpinner"] p,.stSpinner p{font:500 .75rem 'DM Mono'!important;letter-spacing:.14em;color:var(--cyan)!important;text-transform:uppercase}
div[data-testid="stForm"]{border:1px solid rgba(150,190,240,.18);border-radius:22px;padding:1.3rem;background:var(--glass);backdrop-filter:blur(16px)}
iframe{border:0;color-scheme:dark}

@media(max-width:900px){
  .profile{grid-template-columns:1fr;text-align:left}
  .site-foot{grid-template-columns:1fr 1fr}
  .page-hero .motif{display:none}
}
@media(max-width:640px){
  .block-container{padding-left:1rem;padding-right:1rem;padding-top:1.6rem}
  .site-foot{grid-template-columns:1fr}
  .hero{border-radius:22px}
  .insight .h{font-size:1rem}
}
@media(prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important;scroll-behavior:auto!important}
  .splash{display:none}
  .stApp::after{display:none}
}
"""


# ==========================================================
# SIDEBAR FILTER PANEL ("DATA CONTROL") — sidebar-scoped styling only
# ==========================================================

_SIDEBAR_FILTER_CSS = """
@keyframes ctlGlow{0%,100%{box-shadow:0 0 0 0 rgba(34,211,238,.35),0 0 18px rgba(34,211,238,.25)}50%{box-shadow:0 0 0 6px rgba(34,211,238,0),0 0 26px rgba(46,242,160,.35)}}
@keyframes ctlSweep{0%{transform:translateX(-130%)}100%{transform:translateX(130%)}}

/* make sure the sidebar itself can scroll */
@SB{backdrop-filter:none!important;-webkit-backdrop-filter:none!important}
@SB > div:first-child,@SB [data-testid="stSidebarContent"]{max-height:100vh;max-height:100dvh;overflow-y:auto!important;overflow-x:hidden!important;overscroll-behavior:contain}
@SB [data-testid="stSidebarUserContent"]{padding-bottom:5rem}

/* header */
@SB .ctl-head{position:relative;overflow:hidden;display:flex;align-items:center;gap:.7rem;padding:.85rem .85rem;margin-top:1.2rem;border-radius:18px;
  background:radial-gradient(ellipse 80% 130% at 0% 0%,rgba(34,211,238,.17),transparent 70%),linear-gradient(150deg,rgba(18,34,66,.78),rgba(7,14,29,.84));
  border:1px solid rgba(34,211,238,.24);box-shadow:0 14px 34px rgba(0,0,0,.35),inset 0 1px 0 rgba(255,255,255,.07)}
@SB .ctl-head::after{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(105deg,transparent 40%,rgba(255,255,255,.07) 50%,transparent 60%);animation:ctlSweep 7s ease-in-out infinite}
@SB .ctl-ico{flex:none;width:38px;height:38px;border-radius:12px;display:grid;place-items:center;color:#22d3ee;
  background:linear-gradient(145deg,#0f2040,#081428);border:1px solid rgba(34,211,238,.4);animation:ctlGlow 3.2s ease-in-out infinite}
@SB .ctl-title{font:700 .92rem 'Space Grotesk',sans-serif;letter-spacing:.17em;color:#f4f9ff}
@SB .ctl-sub{font:500 .56rem 'DM Mono',monospace;letter-spacing:.1em;color:#8fa3bf;margin-top:2px}
@SB .ctl-live{margin-left:auto;display:inline-flex;align-items:center;gap:.4rem;padding:.25rem .5rem;border-radius:99px;
  font:500 .52rem 'DM Mono',monospace;letter-spacing:.14em;color:#bff7ea;background:rgba(46,242,160,.09);border:1px solid rgba(46,242,160,.3)}
@SB .ctl-live i{width:6px;height:6px;border-radius:50%;background:#2ef2a0;animation:pulseDot 1.8s infinite}
@SB .ctl-state{display:flex;align-items:center;justify-content:space-between;gap:.6rem;margin:.65rem .15rem .2rem;
  font:500 .6rem 'DM Mono',monospace;letter-spacing:.16em;color:#6f86a6;transition:color .3s ease}
@SB .ctl-state.on{color:#7fe9ff}
@SB .ctl-seg{display:flex;gap:4px}
@SB .ctl-seg i{width:16px;height:4px;border-radius:4px;background:rgba(150,180,220,.16);transition:background .3s ease,box-shadow .3s ease}
@SB .ctl-seg i.on{background:linear-gradient(90deg,#22d3ee,#9b7bff);box-shadow:0 0 10px rgba(34,211,238,.7)}
@SB .ctl-rule{height:1px;margin:.5rem 0 .2rem;background:linear-gradient(90deg,transparent,rgba(34,211,238,.6),rgba(155,123,255,.5),transparent);box-shadow:0 0 12px rgba(34,211,238,.35)}

/* group + module labels */
@SB .fg{display:flex;align-items:center;gap:.6rem;margin:1.15rem 0 .1rem;font:500 .56rem 'DM Mono',monospace;letter-spacing:.22em;text-transform:uppercase;color:#5f7696}
@SB .fg::after{content:"";flex:1;height:1px;background:linear-gradient(90deg,rgba(150,180,220,.22),transparent)}
@SB .fm{display:flex;align-items:center;justify-content:space-between;gap:.5rem;margin:.7rem .1rem .3rem}
@SB .fm-name{display:inline-flex;align-items:center;gap:.45rem;font:600 .76rem 'Manrope',sans-serif;color:#b9cbe3;transition:color .25s ease}
@SB .fm-name svg{color:#5f7696;transition:color .25s ease,filter .25s ease}
@SB .fm-badge{display:inline-flex;align-items:center;gap:.35rem;padding:.16rem .5rem;border-radius:99px;font:500 .54rem 'DM Mono',monospace;letter-spacing:.1em;
  color:#7f95b4;background:rgba(150,180,220,.07);border:1px solid rgba(150,180,220,.16);transition:all .3s ease}
@SB .fm-badge i{width:5px;height:5px;border-radius:50%;background:#5f7696}
@SB .fm.on .fm-name{color:#f2f8ff}
@SB .fm.on .fm-name svg{color:#22d3ee;filter:drop-shadow(0 0 5px rgba(34,211,238,.8))}
@SB .fm.on .fm-badge{color:#d8f8ff;background:linear-gradient(135deg,rgba(34,211,238,.2),rgba(155,123,255,.18));border-color:rgba(34,211,238,.45);box-shadow:0 0 14px rgba(34,211,238,.22)}
@SB .fm.on .fm-badge i{background:#22d3ee;box-shadow:0 0 8px #22d3ee}

/* selectbox / multiselect */
@SB [data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
@SB [data-testid="stSelectbox"] div[data-baseweb="select"] > div{
  background:linear-gradient(160deg,rgba(10,20,42,.92),rgba(5,10,22,.94))!important;border:1px solid rgba(150,185,230,.18)!important;border-radius:14px!important;
  box-shadow:inset 3px 3px 9px rgba(0,0,0,.55),inset -1px -1px 4px rgba(130,170,240,.06)!important;
  transition:border-color .25s ease,box-shadow .25s ease!important}
@SB .st-key-filter_Injury div[data-baseweb="select"] > div{max-height:150px;overflow-y:auto;scrollbar-width:thin;scrollbar-color:rgba(34,211,238,.45) transparent}
@SB [data-testid="stMultiSelect"] div[data-baseweb="select"] > div:hover,
@SB [data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover{border-color:rgba(34,211,238,.5)!important;box-shadow:inset 3px 3px 9px rgba(0,0,0,.55),0 0 18px rgba(34,211,238,.14)!important}
@SB [data-testid="stMultiSelect"] div[data-baseweb="select"] > div:focus-within,
@SB [data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within{border-color:#22d3ee!important;box-shadow:inset 2px 2px 7px rgba(0,0,0,.5),0 0 0 3px rgba(34,211,238,.18),0 0 26px rgba(34,211,238,.22)!important}
@SB [data-testid="stMultiSelect"] span[data-baseweb="tag"]{
  background:linear-gradient(135deg,rgba(34,211,238,.24),rgba(155,123,255,.22))!important;border:1px solid rgba(34,211,238,.42)!important;border-radius:9px!important;
  box-shadow:0 0 12px rgba(34,211,238,.16);transition:box-shadow .2s ease,transform .2s ease}
@SB [data-testid="stMultiSelect"] span[data-baseweb="tag"]:hover{box-shadow:0 0 18px rgba(34,211,238,.4);transform:translateY(-1px)}
@SB [data-testid="stMultiSelect"] span[data-baseweb="tag"] span{font:500 .66rem 'DM Mono',monospace!important;color:#e2f9ff!important;letter-spacing:.02em}

/* slider */
@SB [data-testid="stSlider"]{padding:.3rem .95rem .15rem;border-radius:14px;background:linear-gradient(160deg,rgba(10,20,42,.75),rgba(5,10,22,.78));
  border:1px solid rgba(150,185,230,.15);box-shadow:inset 2px 2px 8px rgba(0,0,0,.45)}
@SB [data-testid="stSlider"] [role="slider"]{background:radial-gradient(circle at 30% 30%,#fff,#22d3ee 55%,#0a8aa6)!important;
  box-shadow:0 0 0 4px rgba(34,211,238,.18),0 0 18px rgba(34,211,238,.8)!important;transition:transform .2s ease,box-shadow .2s ease}
@SB [data-testid="stSlider"] [role="slider"]:hover{transform:scale(1.15)}
@SB [data-testid="stSlider"] [role="slider"]:focus-visible{outline:2px solid #9b7bff;outline-offset:3px}
@SB [data-testid="stSlider"] [data-baseweb="slider"] div[style*="linear-gradient"]{box-shadow:0 0 12px rgba(34,211,238,.45);border-radius:6px}
@SB [data-testid="stSliderThumbValue"]{font:600 .7rem 'DM Mono',monospace!important;color:#bff7ea!important}
@SB [data-testid="stSliderTickBarMin"],@SB [data-testid="stSliderTickBarMax"]{font:500 .58rem 'DM Mono',monospace!important;color:#6f86a6!important}

/* date + text inputs */
@SB [data-testid="stDateInput"] div[data-baseweb="input"],
@SB [data-testid="stTextInput"] div[data-baseweb="input"]{
  background:linear-gradient(160deg,rgba(10,20,42,.92),rgba(5,10,22,.94))!important;border:1px solid rgba(150,185,230,.18)!important;border-radius:14px!important;
  box-shadow:inset 3px 3px 9px rgba(0,0,0,.55),inset -1px -1px 4px rgba(130,170,240,.06)!important;transition:border-color .25s ease,box-shadow .25s ease!important}
@SB [data-testid="stDateInput"] div[data-baseweb="input"]:hover,
@SB [data-testid="stTextInput"] div[data-baseweb="input"]:hover{border-color:rgba(34,211,238,.5)!important}
@SB [data-testid="stDateInput"] div[data-baseweb="input"]:focus-within,
@SB [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within{border-color:#22d3ee!important;box-shadow:inset 2px 2px 7px rgba(0,0,0,.5),0 0 0 3px rgba(34,211,238,.18),0 0 24px rgba(34,211,238,.2)!important}
@SB [data-testid="stDateInput"] input,@SB [data-testid="stTextInput"] input{font:500 .78rem 'DM Mono',monospace!important;color:#e6f2ff!important}

/* checkbox / toggle (present only if a filter uses them) */
@SB [data-testid="stCheckbox"] label p,@SB [data-testid="stToggle"] label p{font:500 .8rem 'DM Sans',sans-serif;color:#c9d8ee}
@SB [data-testid="stCheckbox"] input,@SB [data-testid="stToggle"] input{accent-color:#22d3ee}

/* action buttons (Reset filters / Sign out) */
@SB .stButton>button{position:relative;overflow:hidden;width:100%;border-radius:14px!important;padding:.6rem 1rem!important;
  transition:transform .22s cubic-bezier(.2,.7,.2,1),box-shadow .22s ease,border-color .22s ease!important}
@SB .stButton>button::after{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(105deg,transparent 35%,rgba(255,255,255,.26) 50%,transparent 65%);transform:translateX(-130%);transition:transform .7s ease}
@SB .stButton>button:hover::after{transform:translateX(130%)}
@SB .stButton>button:active{transform:translateY(1px) scale(.98)!important}
@SB .st-key-reset_filters button{background:linear-gradient(100deg,rgba(34,211,238,.26),rgba(46,242,160,.18))!important;border:1px solid rgba(34,211,238,.55)!important;box-shadow:0 8px 24px rgba(34,211,238,.16),inset 0 1px 0 rgba(255,255,255,.12)}
@SB .st-key-reset_filters button p{color:#d9fbff!important}
@SB .st-key-reset_filters button:hover{box-shadow:0 14px 34px rgba(34,211,238,.32),0 0 26px rgba(46,242,160,.22)!important}
@SB .st-key-sign_out button{background:rgba(255,107,125,.06)!important;border:1px solid rgba(255,107,125,.3)!important;box-shadow:none}
@SB .st-key-sign_out button p{color:#ffb3bd!important}
@SB .st-key-sign_out button:hover{border-color:rgba(255,107,125,.65)!important;box-shadow:0 10px 26px rgba(255,107,125,.2)!important}
""".replace("@SB", 'section[data-testid="stSidebar"]')

SIDEBAR_FILTER_CSS = _SIDEBAR_FILTER_CSS


def filter_panel_header(flags):
    n = sum(1 for x in flags if x)
    segs = "".join(f'<i class="{"on" if x else ""}"></i>' for x in flags)
    state = f"{n} ACTIVE" if n else "ALL DATA"
    return f"""
    <div class="ctl-head"><div class="ctl-ico">{icon_svg("filter", 18)}</div>
      <div><div class="ctl-title">DATA CONTROL</div><div class="ctl-sub">SHAPES EVERY WORKSPACE</div></div>
      <div class="ctl-live"><i></i>LIVE FILTERS</div></div>
    <div class="ctl-state{" on" if n else ""}"><span>{state}</span><div class="ctl-seg">{segs}</div></div>
    <div class="ctl-rule"></div>"""


def filter_module_html(label, icon, active, detail):
    return (f'<div class="fm{" on" if active else ""}"><span class="fm-name">{icon_svg(icon, 14)}'
            f'<span>{esc(label)}</span></span><span class="fm-badge"><i></i>{esc(detail)}</span></div>')


def inject_css():
    st.markdown("<style>" + BASE_CSS + _nav_icon_css() + SIDEBAR_FILTER_CSS + "</style>", unsafe_allow_html=True)


# ==========================================================
# CATEGORY RULES (derived, documented in Methodology)
# ==========================================================

_CAT_RULES = [
    ("Illness", r"\bill\b|coronavirus|virus|infection|fever|\bcold\b|tonsillitis|bronchitis|malaria|shingles|quarantine|depression"),
    ("Unspecified", r"unknown|fitness"),
    ("Head & neck", r"head|concussion|neck|facial|nose|cheekbone"),
    ("Ligament & tendon", r"ligament|cruciate|meniscus|tendon|achilles|archilles"),
    ("Bone & fracture", r"fracture|broken|bone|metatarsal|fibula"),
    ("Knock & bruise", r"knock|bruise|dead leg"),
    ("Muscle", r"hamstring|calf|thigh|muscle|muscular|groin|adductor|hip flexor|strain|torn|abdominal|fatigue"),
    ("Joint & other", r"knee|ankle|hip|foot|toe|shoulder|elbow|back|arm|hand|chest|rib|leg|shin"),
]


def classify_injury(text):
    t = str(text).lower()
    for label, pattern in _CAT_RULES:
        if re.search(pattern, t):
            return label
    return "Other"


def position_group(pos):
    if pos is None or pd.isna(pos):
        return "Other"
    p = str(pos).lower()
    if "goalkeeper" in p:
        return "Goalkeeper"
    if "back" in p:
        return "Defender"
    if "midfielder" in p:
        return "Midfielder"
    if "winger" in p or "forward" in p:
        return "Forward"
    return "Other"


HELPER_COLS = [
    "Injury_Clean", "Injury_Category", "Position_Group", "Age_Group",
    "Recovery_Band", "Points_Per_Absence_Match", "Month_Label",
]
# ==========================================================
# DATA LAYER
# ==========================================================

@st.cache_data(show_spinner=False)
def load_dataset(raw_bytes=None):
    if raw_bytes is None:
        data = pd.read_csv("footlens_cleaned_injuries.csv")
    else:
        data = pd.read_csv(BytesIO(raw_bytes))

    data.columns = [str(c).strip() for c in data.columns]

    for col in ["Name", "Team Name", "Position", "Season", "Injury"]:
        if col in data.columns:
            data[col] = data[col].astype("string").str.strip()

    for col in ["Date of Injury", "Date of return"]:
        if col in data.columns:
            data[col] = pd.to_datetime(data[col], errors="coerce")

    numeric_cols = [
        "Age", "FIFA rating", "Recovery_Days",
        "Avg_Pre_Injury_Rating", "Avg_Post_Injury_Rating",
        "Performance_Change", "Wins_During_Absence",
        "Points_During_Absence", "Avg_GD_During_Absence",
        "Absence_Matches_Recorded",
    ]
    numeric_cols += [
        c for c in data.columns
        if c.endswith("_GD") or c.endswith("_Player_rating")
    ]
    for col in set(numeric_cols):
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    before_cols = [c for c in data.columns if "_before_injury_GD" in c]
    if before_cols:
        data["Avg_GD_Before_Injury"] = data[before_cols].mean(axis=1)
    else:
        data["Avg_GD_Before_Injury"] = np.nan

    if "Avg_GD_During_Absence" in data.columns:
        data["Team_Performance_Drop"] = (
            data["Avg_GD_Before_Injury"] - data["Avg_GD_During_Absence"]
        )
    else:
        data["Team_Performance_Drop"] = np.nan

    # ---- derived helper columns (additive; no original column is changed) ----
    inj = data["Injury"].astype("string").str.strip().str.lower().fillna("unknown injury")
    inj = inj.replace({"unknown injur": "unknown injury", "ack injury": "back injury"})
    data["Injury_Clean"] = inj.str.capitalize().astype(object)
    cat_map = {v: classify_injury(v) for v in data["Injury_Clean"].unique()}
    data["Injury_Category"] = data["Injury_Clean"].map(cat_map)
    data["Position_Group"] = data["Position"].map(position_group)

    age = pd.to_numeric(data["Age"], errors="coerce") if "Age" in data.columns else pd.Series(np.nan, index=data.index)
    data["Age_Group"] = pd.cut(
        age, bins=[0, 21, 25, 29, 33, 120], labels=AGE_ORDER
    ).astype(object)

    rec = data["Recovery_Days"] if "Recovery_Days" in data.columns else pd.Series(np.nan, index=data.index)
    data["Recovery_Band"] = pd.cut(
        rec, bins=[0, 7, 14, 28, 60, 120, 100000], labels=BAND_ORDER
    ).astype(object)

    if "Points_During_Absence" in data.columns and "Absence_Matches_Recorded" in data.columns:
        matches = data["Absence_Matches_Recorded"].where(data["Absence_Matches_Recorded"] > 0)
        data["Points_Per_Absence_Match"] = data["Points_During_Absence"] / matches
    else:
        data["Points_Per_Absence_Match"] = np.nan

    if "Injury_Month_Name" in data.columns:
        label = data["Injury_Month_Name"].astype("string").str.strip()
    else:
        label = pd.Series(pd.NA, index=data.index, dtype="string")
    if "Date of Injury" in data.columns:
        label = label.fillna(data["Date of Injury"].dt.month_name().astype("string"))
    data["Month_Label"] = label.astype(object)

    return data


def completeness(frame, col):
    if col not in frame.columns or len(frame) == 0:
        return None
    return 100.0 * frame[col].notna().mean()


# ==========================================================
# REUSABLE UI BUILDERS
# ==========================================================

def section_label(kicker, title, description=None):
    desc = f'<div class="sec-desc">{esc(description)}</div>' if description else ""
    render(
        f'<div class="sec-kicker">{esc(kicker)}</div>'
        f'<div class="sec-title">{esc(title)}</div>{desc}'
    )


MOTIFS = {
    "cc": "<svg width='260' height='170' viewBox='0 0 260 170' fill='none' stroke='#22d3ee' stroke-width='1.4'><circle cx='170' cy='85' r='30'/><circle cx='170' cy='85' r='55' opacity='.6'/><circle cx='170' cy='85' r='80' opacity='.3'/><path d='M0 100h70l12-40 20 80 14-40h30' stroke='#2ef2a0' stroke-width='2'/></svg>",
    "inj": "<svg width='260' height='170' viewBox='0 0 260 170'>" + "".join(
        f"<rect x='{20 + c * 34}' y='{18 + r * 34}' width='28' height='28' rx='6' fill='#9b7bff' opacity='{0.08 + ((c * 3 + r * 5) % 7) * 0.09:.2f}'/>"
        for c in range(7) for r in range(4)) + "</svg>",
    "player": "<svg width='260' height='170' viewBox='0 0 260 170' fill='none' stroke='#2ef2a0' stroke-width='1.4'><path d='M40 150a90 90 0 0 1 180 0' opacity='.35'/><path d='M70 150a60 60 0 0 1 120 0' opacity='.55'/><path d='M100 150a30 30 0 0 1 60 0'/><circle cx='130' cy='62' r='9' fill='#2ef2a0' stroke='none'/></svg>",
    "club": "<svg width='260' height='170' viewBox='0 0 260 170' fill='none' stroke-width='1.6'><circle cx='105' cy='85' r='52' stroke='#22d3ee'/><circle cx='155' cy='85' r='52' stroke='#9b7bff'/><path d='M130 42v86' stroke='#ffffff' opacity='.25'/></svg>",
    "data": "<svg width='260' height='170' viewBox='0 0 260 170'>" + "".join(
        f"<circle cx='{18 + c * 22}' cy='{16 + r * 22}' r='{2 + (c + r) % 3}' fill='#ffb454' opacity='{0.25 + ((c * r) % 5) * 0.12:.2f}'/>"
        for c in range(11) for r in range(7)) + "</svg>",
    "method": "<svg width='260' height='170' viewBox='0 0 260 170' fill='none' stroke='#22d3ee' stroke-width='1.4'><path d='M30 30h180M30 60h140M30 90h170M30 120h110' opacity='.5'/><circle cx='222' cy='120' r='22' stroke='#9b7bff'/><path d='M222 108v14M222 128v1' stroke='#9b7bff' stroke-width='2.4'/></svg>",
}


def page_hero(kicker, lead, accent, copy, a, b, motif):
    render(f"""
    <div class="page-hero" style="--a:{a};--b:{b}">
        <div class="motif">{MOTIFS.get(motif, '')}</div>
        <div class="eyebrow">{esc(kicker)}</div>
        <h1>{esc(lead)} <span class="grad">{esc(accent)}</span></h1>
        <p>{esc(copy)}</p>
    </div>""")


def insight(tone, icon, kicker, headline, body, i=0):
    color = {"cyan": PAL["cyan"], "emerald": PAL["emerald"], "violet": PAL["violet"],
             "amber": PAL["amber"], "coral": PAL["coral"]}.get(tone, PAL["cyan"])
    render(f"""
    <div class="panel insight rise" style="--t:{color};--i:{i}">
        <div class="ico">{icon_svg(icon, 18)}</div>
        <div><div class="t">{esc(kicker)}</div><div class="h">{esc(headline)}</div>
        <div class="b">{esc(body)}</div></div>
    </div>""")


def meter(label, value, note=""):
    if value is None:
        return ""
    v = max(0, min(100, value))
    return f"""
    <div class="meter"><div class="row"><span>{esc(label)}</span><b>{v:.0f}%</b></div>
    <div class="track"><i style="width:{v:.1f}%"></i></div>
    {f'<div class="mono" style="font-size:.62rem;color:#6f86a6;margin-top:.3rem">{esc(note)}</div>' if note else ''}</div>"""


def leaderboard(frame, label_col, value_col, fmt="{:,.0f}", limit=8):
    if frame.empty:
        return '<div class="sec-desc">No data in this selection.</div>'
    top = frame.sort_values(value_col, ascending=False).head(limit)
    peak = float(top[value_col].max()) or 1.0
    rows = []
    for rank, (_, r) in enumerate(top.iterrows(), start=1):
        width = max(3, 100 * float(r[value_col]) / peak)
        rows.append(
            f'<div class="lb"><span class="rk">{rank:02d}</span><span class="nm">{esc(r[label_col])}</span>'
            f'<span class="vl">{fmt.format(r[value_col])}</span>'
            f'<div class="bar"><i style="width:{width:.1f}%;animation-delay:{rank * 70}ms"></i></div></div>'
        )
    return "".join(rows)


def avatar_svg(name, size=96):
    parts = [p for p in re.split(r"\s+", str(name).strip()) if p]
    initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper() if parts else "?"
    h = hue_of(name)
    uid = hashlib.md5(str(name).encode("utf-8")).hexdigest()[:8]
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 100 100" aria-hidden="true">
      <defs>
        <linearGradient id="ag{uid}" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="hsl({h},85%,62%)"/><stop offset="1" stop-color="hsl({(h + 70) % 360},85%,58%)"/>
        </linearGradient>
        <radialGradient id="ab{uid}" cx=".3" cy=".25"><stop offset="0" stop-color="hsl({h},60%,22%)"/><stop offset="1" stop-color="#050912"/></radialGradient>
      </defs>
      <polygon points="50,3 90,26 90,74 50,97 10,74 10,26" fill="url(#ab{uid})" stroke="url(#ag{uid})" stroke-width="2.2"/>
      <polygon class="ring-spin" points="50,12 82,30 82,70 50,88 18,70 18,30" fill="none" stroke="url(#ag{uid})" stroke-width=".8" stroke-dasharray="3 5" opacity=".7"/>
      <text x="50" y="59" text-anchor="middle" font-family="Space Grotesk,sans-serif" font-weight="700" font-size="30" fill="url(#ag{uid})">{esc(initials)}</text>
    </svg>"""


def brand_mark(size=44, uid="a"):
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 64 64" aria-hidden="true">
      <defs><linearGradient id="bm{uid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#22d3ee"/><stop offset=".55" stop-color="#2ef2a0"/><stop offset="1" stop-color="#9b7bff"/></linearGradient></defs>
      <polygon points="32,3 57,17 57,47 32,61 7,47 7,17" fill="rgba(10,20,40,.9)" stroke="url(#bm{uid})" stroke-width="2"/>
      <circle class="ring-spin" cx="32" cy="32" r="17" fill="none" stroke="url(#bm{uid})" stroke-width="1.4" stroke-dasharray="5 4"/>
      <circle cx="32" cy="32" r="8" fill="none" stroke="url(#bm{uid})" stroke-width="2.4"/>
      <path d="M32 24v16M24 32h16" stroke="url(#bm{uid})" stroke-width="1.2" opacity=".6"/>
    </svg>"""


# ==========================================================
# ISOLATED HTML/JS COMPONENTS (real JavaScript inside iframes)
# ==========================================================

def show_component(markup, height):
    components.html(markup, height=height, scrolling=False)


KPI_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8"><meta name="color-scheme" content="dark">
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600&family=Manrope:wght@600;700;800&display=swap');
*{box-sizing:border-box;margin:0}
html,body{background:transparent;font-family:'DM Sans',sans-serif;color:#eaf2ff;overflow:hidden}
.grid{display:grid;grid-template-columns:repeat(__N__,minmax(0,1fr));gap:14px;padding:6px 2px 10px}
.card{--mx:50%;--my:0%;position:relative;overflow:hidden;border-radius:20px;padding:16px 16px 14px;min-height:__CH__px;
  border:1px solid transparent;
  background:linear-gradient(150deg,rgba(24,40,76,.92),rgba(8,16,34,.94)) padding-box,
             linear-gradient(135deg,var(--accent),rgba(255,255,255,.05) 45%,rgba(255,255,255,.02) 70%,var(--accent)) border-box;
  box-shadow:0 18px 44px rgba(0,0,0,.35),8px 8px 20px rgba(0,0,0,.25),-3px -3px 10px rgba(130,170,240,.04),inset 0 1px 0 rgba(255,255,255,.07);
  transition:transform .3s cubic-bezier(.2,.7,.2,1),box-shadow .3s ease;
  animation:rise .7s cubic-bezier(.2,.7,.2,1) both;animation-delay:calc(var(--i)*80ms)}
.card:hover{transform:translateY(-6px);box-shadow:0 28px 56px rgba(0,0,0,.45),0 0 34px color-mix(in srgb,var(--accent) 22%,transparent),inset 0 1px 0 rgba(255,255,255,.1)}
.glow{position:absolute;inset:0;pointer-events:none;opacity:0;transition:opacity .3s;
  background:radial-gradient(220px circle at var(--mx) var(--my),color-mix(in srgb,var(--accent) 24%,transparent),transparent 70%)}
.card:hover .glow{opacity:1}
.top{display:flex;justify-content:space-between;align-items:center;gap:8px;position:relative}
.lbl{font:500 10.5px 'DM Mono',monospace;letter-spacing:.13em;text-transform:uppercase;color:#8fa3bf}
.ico{flex:none;width:34px;height:34px;border-radius:11px;display:grid;place-items:center;color:var(--accent);
  background:linear-gradient(145deg,#0f2040,#081428);border:1px solid color-mix(in srgb,var(--accent) 35%,transparent);
  box-shadow:4px 4px 10px rgba(0,0,0,.5),-2px -2px 6px rgba(130,170,240,.06);transition:transform .35s cubic-bezier(.3,1.6,.5,1)}
.card:hover .ico{transform:rotate(-8deg) scale(1.1)}
.val{position:relative;margin:12px 0 4px;font:800 clamp(24px,2.4vw,34px)/1 'Manrope',sans-serif;letter-spacing:-.03em;
  background:linear-gradient(180deg,#fff,color-mix(in srgb,var(--accent) 45%,#dbeaff));-webkit-background-clip:text;background-clip:text;color:transparent}
.val .suf{font:600 .42em 'DM Mono',monospace;letter-spacing:0;margin-left:5px;-webkit-text-fill-color:#8fa3bf;color:#8fa3bf}
.note{position:relative;font-size:11.5px;line-height:1.45;color:#8fa3bf;min-height:34px}
.bar{position:relative;height:3px;border-radius:3px;margin-top:10px;background:rgba(150,180,220,.1);overflow:hidden}
.bar i{display:block;height:100%;width:var(--w);border-radius:3px;transform-origin:left;animation:grow 1.2s cubic-bezier(.2,.7,.2,1) both;animation-delay:calc(var(--i)*80ms + 250ms);
  background:linear-gradient(90deg,var(--accent),transparent);box-shadow:0 0 12px var(--accent)}
@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@media(max-width:760px){
  .grid{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:14px}
  .card{flex:0 0 74%;scroll-snap-align:start}
}
@media(prefers-reduced-motion:reduce){*{animation-duration:.01ms!important;transition-duration:.01ms!important}}
</style></head><body>
<div class="grid">__CARDS__</div>
<script>
(function(){
  var reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.querySelectorAll('.n').forEach(function(el){
    var to=parseFloat(el.dataset.to),dec=parseInt(el.dataset.dec||'0',10),pre=el.dataset.prefix||'';
    function fmt(v){return pre+v.toLocaleString('en-US',{minimumFractionDigits:dec,maximumFractionDigits:dec});}
    if(isNaN(to)){return;}
    if(reduce){el.textContent=fmt(to);return;}
    var t0=null,dur=1200;
    function step(t){if(t0===null)t0=t;var p=Math.min(1,(t-t0)/dur),e=1-Math.pow(1-p,4);
      el.textContent=fmt(to*e);if(p<1){requestAnimationFrame(step);}else{el.textContent=fmt(to);}}
    requestAnimationFrame(step);
  });
  document.querySelectorAll('.card').forEach(function(c){
    c.addEventListener('pointermove',function(e){var r=c.getBoundingClientRect();
      c.style.setProperty('--mx',(e.clientX-r.left)+'px');c.style.setProperty('--my',(e.clientY-r.top)+'px');});
  });
})();
</script></body></html>"""


def kpi_strip(items, height=196, key_prefix="kpi"):
    """items: dict(label, value, decimals, suffix, note, icon, accent, fill, signed)."""
    cards = []
    for i, it in enumerate(items):
        value = it.get("value")
        accent = it.get("accent", PAL["cyan"])
        if value is None or (isinstance(value, float) and np.isnan(value)):
            number = '<span>—</span>'
        else:
            prefix = "+" if it.get("signed") and value > 0 else ""
            number = (
                f'<span class="n" data-to="{float(value):.6f}" data-dec="{int(it.get("decimals", 0))}" '
                f'data-prefix="{prefix}">0</span>'
            )
        suffix = f'<span class="suf">{esc(it["suffix"])}</span>' if it.get("suffix") and value is not None else ""
        fill = max(6, min(100, 100 * float(it.get("fill", 0.42))))
        cards.append(
            f'<div class="card" style="--accent:{accent};--i:{i}"><div class="glow"></div>'
            f'<div class="top"><span class="lbl">{esc(it["label"])}</span>'
            f'<span class="ico">{icon_svg(it.get("icon", "grid"), 17)}</span></div>'
            f'<div class="val">{number}{suffix}</div>'
            f'<div class="note">{esc(it.get("note", ""))}</div>'
            f'<div class="bar"><i style="--w:{fill:.0f}%"></i></div></div>'
        )
    markup = (KPI_TEMPLATE
              .replace("__N__", str(len(items)))
              .replace("__CH__", str(height - 34))
              .replace("__CARDS__", "".join(cards)))
    show_component(markup, height)


HERO_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8"><meta name="color-scheme" content="dark">
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600&family=Manrope:wght@700;800&display=swap');
*{box-sizing:border-box;margin:0}
html,body{height:100%;background:transparent;overflow:hidden;font-family:'DM Sans',sans-serif;color:#eaf2ff}
.stage{position:relative;height:100%;--rx:0;--ry:0;perspective:1300px}
canvas{position:absolute;inset:0;width:100%;height:100%}
.pitch{position:absolute;left:50%;top:50%;width:94%;max-width:660px;aspect-ratio:600/380;
  transform:translate(-50%,-50%) rotateX(calc(54deg + var(--ry)*-5deg)) rotateZ(calc(-13deg + var(--rx)*5deg));
  transition:transform .18s ease-out;transform-style:preserve-3d}
.pitch svg{width:100%;height:100%;overflow:visible;filter:drop-shadow(0 0 16px rgba(34,211,238,.4))}
.dash{stroke-dasharray:6 8;animation:flow 2.4s linear infinite}
@keyframes flow{to{stroke-dashoffset:-56}}
.chip{--d:10;position:absolute;display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:16px;
  background:linear-gradient(150deg,rgba(30,52,96,.78),rgba(9,18,38,.8));border:1px solid rgba(150,190,240,.22);
  backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
  box-shadow:0 16px 40px rgba(0,0,0,.4),inset 0 1px 0 rgba(255,255,255,.08);
  translate:calc(var(--rx)*var(--d)*1px) calc(var(--ry)*var(--d)*1px);
  animation:float 6s ease-in-out infinite;animation-delay:var(--dl,0s)}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-9px)}}
.chip .k{font:500 9.5px 'DM Mono',monospace;letter-spacing:.14em;text-transform:uppercase;color:#8fa3bf}
.chip .v{font:800 22px 'Manrope',sans-serif;letter-spacing:-.02em;color:#f4f9ff}
.ring{width:42px;height:42px;transform:rotate(-90deg)}
.ring circle{fill:none;stroke-width:4}
.ring .bg{stroke:rgba(150,180,220,.16)}
.ring .fg{stroke-linecap:round;stroke-dasharray:var(--c) 999;animation:fill 1.6s cubic-bezier(.2,.7,.2,1) both}
@keyframes fill{from{stroke-dasharray:0 999}}
.pulse{position:absolute;left:0;right:0;bottom:6px;height:64px;opacity:.9}
.pulse path{fill:none;stroke-width:2;stroke-linecap:round}
.pulse .tr{stroke:rgba(34,211,238,.14)}
.pulse .sc{stroke:url(#pg2);stroke-dasharray:200 800;animation:scan 3.2s linear infinite;filter:drop-shadow(0 0 6px #22d3ee)}
@keyframes scan{from{stroke-dashoffset:1000}to{stroke-dashoffset:0}}
@media(prefers-reduced-motion:reduce){*{animation-duration:.01ms!important;transition-duration:.01ms!important}}
</style></head><body>
<div class="stage" id="stage">
  <canvas id="fx"></canvas>
  <div class="pitch" id="pitch">
    <svg viewBox="0 0 600 380" id="svg">
      <defs>
        <linearGradient id="pg" x1="0" x2="1"><stop offset="0" stop-color="#22d3ee"/><stop offset="1" stop-color="#9b7bff"/></linearGradient>
        <radialGradient id="turf" cx=".5" cy=".5" r=".7"><stop offset="0" stop-color="rgba(34,211,238,.16)"/><stop offset="1" stop-color="rgba(8,18,40,.7)"/></radialGradient>
      </defs>
      <rect x="8" y="8" width="584" height="364" rx="12" fill="url(#turf)" stroke="url(#pg)" stroke-width="2"/>
      <g fill="none" stroke="url(#pg)" stroke-width="1.5" opacity=".8">
        <line x1="300" y1="8" x2="300" y2="372"/><circle cx="300" cy="190" r="50"/>
        <rect x="8" y="105" width="98" height="170"/><rect x="494" y="105" width="98" height="170"/>
        <rect x="8" y="150" width="36" height="80"/><rect x="556" y="150" width="36" height="80"/>
      </g>
      <g id="links" stroke="#22d3ee" stroke-width="1.3" opacity=".55" fill="none"></g>
      <g id="dots"></g>
    </svg>
  </div>
  __CHIPS__
  <svg class="pulse" viewBox="0 0 1000 64" preserveAspectRatio="none">
    <defs><linearGradient id="pg2" x1="0" x2="1"><stop offset="0" stop-color="#2ef2a0"/><stop offset="1" stop-color="#22d3ee"/></linearGradient></defs>
    <path class="tr" pathLength="1000" d="M0 34H180l14-8 12 16 16-34 18 56 14-30 10 0H480l14-8 12 16 16-34 18 56 14-30 10 0H760l14-8 12 16 16-34 18 56 14-30 10 0H1000"/>
    <path class="sc" pathLength="1000" d="M0 34H180l14-8 12 16 16-34 18 56 14-30 10 0H480l14-8 12 16 16-34 18 56 14-30 10 0H760l14-8 12 16 16-34 18 56 14-30 10 0H1000"/>
  </svg>
</div>
<script>
(function(){
  var reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var stage=document.getElementById('stage');
  var pos=[[42,190],[120,60],[112,140],[112,240],[120,320],[240,110],[228,190],[240,270],[370,70],[392,190],[370,310]];
  var edges=[[0,2],[0,3],[2,6],[3,6],[1,5],[4,7],[5,6],[6,7],[5,8],[6,9],[7,10],[8,9],[9,10]];
  var NS='http://www.w3.org/2000/svg',links=document.getElementById('links'),dots=document.getElementById('dots');
  edges.forEach(function(e){var l=document.createElementNS(NS,'line');
    l.setAttribute('x1',pos[e[0]][0]);l.setAttribute('y1',pos[e[0]][1]);l.setAttribute('x2',pos[e[1]][0]);l.setAttribute('y2',pos[e[1]][1]);
    l.setAttribute('class','dash');links.appendChild(l);});
  pos.forEach(function(p,i){
    var g=document.createElementNS(NS,'g');
    var ring=document.createElementNS(NS,'circle');ring.setAttribute('cx',p[0]);ring.setAttribute('cy',p[1]);ring.setAttribute('r',8);
    ring.setAttribute('fill','none');ring.setAttribute('stroke','#2ef2a0');ring.setAttribute('stroke-width','1.5');
    if(!reduce){
      var a1=document.createElementNS(NS,'animate');a1.setAttribute('attributeName','r');a1.setAttribute('values','8;22');a1.setAttribute('dur','2.6s');a1.setAttribute('begin',(i*0.23)+'s');a1.setAttribute('repeatCount','indefinite');
      var a2=document.createElementNS(NS,'animate');a2.setAttribute('attributeName','opacity');a2.setAttribute('values','.8;0');a2.setAttribute('dur','2.6s');a2.setAttribute('begin',(i*0.23)+'s');a2.setAttribute('repeatCount','indefinite');
      ring.appendChild(a1);ring.appendChild(a2);
    }
    var c=document.createElementNS(NS,'circle');c.setAttribute('cx',p[0]);c.setAttribute('cy',p[1]);c.setAttribute('r',7);
    c.setAttribute('fill','#07101f');c.setAttribute('stroke','#2ef2a0');c.setAttribute('stroke-width','2.2');
    g.appendChild(ring);g.appendChild(c);dots.appendChild(g);
  });
  stage.addEventListener('pointermove',function(e){
    var r=stage.getBoundingClientRect();
    stage.style.setProperty('--rx',(((e.clientX-r.left)/r.width)*2-1).toFixed(3));
    stage.style.setProperty('--ry',(((e.clientY-r.top)/r.height)*2-1).toFixed(3));
  });
  stage.addEventListener('pointerleave',function(){stage.style.setProperty('--rx',0);stage.style.setProperty('--ry',0);});
  /* count-up */
  document.querySelectorAll('.cu').forEach(function(el){
    var to=parseFloat(el.dataset.to);if(isNaN(to))return;
    var dec=parseInt(el.dataset.dec||'0',10);
    function f(v){return v.toLocaleString('en-US',{minimumFractionDigits:dec,maximumFractionDigits:dec});}
    if(reduce){el.textContent=f(to);return;}
    var t0=null;function step(t){if(t0===null)t0=t;var p=Math.min(1,(t-t0)/1400),e=1-Math.pow(1-p,4);el.textContent=f(to*e);if(p<1)requestAnimationFrame(step);else el.textContent=f(to);}
    requestAnimationFrame(step);
  });
  /* particle constellation */
  var cv=document.getElementById('fx'),cx=cv.getContext('2d'),W=0,H=0,pts=[],running=true;
  function size(){var r=cv.getBoundingClientRect(),d=Math.min(2,window.devicePixelRatio||1);
    W=r.width;H=r.height;cv.width=W*d;cv.height=H*d;cx.setTransform(d,0,0,d,0,0);
    var n=Math.max(18,Math.round(W*H/11000));var cols=['34,211,238','155,123,255','46,242,160'];
    pts=[];for(var i=0;i<n;i++){pts.push({x:Math.random()*W,y:Math.random()*H,vx:(Math.random()-.5)*.28,vy:(Math.random()-.5)*.28,r:Math.random()*1.5+.4,c:cols[i%3]});}}
  function draw(){
    cx.clearRect(0,0,W,H);
    for(var i=0;i<pts.length;i++){var p=pts[i];
      if(!reduce){p.x+=p.vx;p.y+=p.vy;if(p.x<0||p.x>W)p.vx*=-1;if(p.y<0||p.y>H)p.vy*=-1;}
      cx.beginPath();cx.fillStyle='rgba('+p.c+',.75)';cx.arc(p.x,p.y,p.r,0,6.283);cx.fill();
      for(var j=i+1;j<pts.length;j++){var q=pts[j],dx=p.x-q.x,dy=p.y-q.y,d=dx*dx+dy*dy;
        if(d<9000){cx.strokeStyle='rgba(120,180,255,'+(0.16*(1-d/9000)).toFixed(3)+')';cx.lineWidth=.7;cx.beginPath();cx.moveTo(p.x,p.y);cx.lineTo(q.x,q.y);cx.stroke();}}
    }
    if(running&&!reduce)requestAnimationFrame(draw);
  }
  size();draw();window.addEventListener('resize',function(){size();if(reduce)draw();});
  if('IntersectionObserver' in window){new IntersectionObserver(function(en){
    var v=en[0].isIntersecting;if(v&&!running&&!reduce){running=true;requestAnimationFrame(draw);}running=v;},{threshold:0}).observe(stage);}
})();
</script></body></html>"""


def hero_visual(stats, height=560):
    chips = ""
    if stats:
        def ring(v, color):
            c = 2 * 3.14159 * 17 * (max(0, min(100, v)) / 100)
            return (f'<svg class="ring" viewBox="0 0 42 42"><circle class="bg" cx="21" cy="21" r="17"/>'
                    f'<circle class="fg" cx="21" cy="21" r="17" stroke="{color}" style="--c:{c:.1f}"/></svg>')
        chips = (
            f'<div class="chip" style="left:2%;top:7%;--d:16;--dl:0s"><div><div class="k">Injury records</div>'
            f'<div class="v"><span class="cu" data-to="{stats["records"]}">0</span></div></div></div>'
            f'<div class="chip" style="right:1%;top:20%;--d:22;--dl:1.2s"><div><div class="k">Players tracked</div>'
            f'<div class="v"><span class="cu" data-to="{stats["players"]}">0</span></div></div></div>'
        )
        if stats.get("recovery_cov") is not None:
            chips += (
                f'<div class="chip" style="left:0%;bottom:26%;--d:26;--dl:2s">{ring(stats["recovery_cov"], "#2ef2a0")}'
                f'<div><div class="k">Recovery recorded</div><div class="v"><span class="cu" data-to="{stats["recovery_cov"]:.0f}">0</span>%</div></div></div>'
            )
        if stats.get("rating_cov") is not None:
            chips += (
                f'<div class="chip" style="right:3%;bottom:20%;--d:12;--dl:.6s">{ring(stats["rating_cov"], "#9b7bff")}'
                f'<div><div class="k">Rating change recorded</div><div class="v"><span class="cu" data-to="{stats["rating_cov"]:.0f}">0</span>%</div></div></div>'
            )
    show_component(HERO_TEMPLATE.replace("__CHIPS__", chips), height)


def splash_once():
    if st.session_state.get("_splash_done"):
        return
    st.session_state["_splash_done"] = True
    render(f"""
    <div class="splash" aria-hidden="true">
      <div><div class="logo">{brand_mark(86, "s")}</div>
      <h2>FOOTLENS</h2><p>INITIALISING PERFORMANCE INTELLIGENCE</p>
      <div class="bar"><i></i></div></div>
    </div>""")


def skeleton_block(n=5, height=150):
    cells = "".join(f'<div class="skel" style="height:{height}px"></div>' for _ in range(n))
    return (f'<div style="display:grid;grid-template-columns:repeat({n},1fr);gap:14px;margin:.6rem 0">{cells}</div>'
            f'<div class="mono" style="color:#22d3ee;font-size:.66rem;letter-spacing:.2em;margin-top:.4rem">'
            f'PREPARING YOUR WORKSPACE…</div>')


# ==========================================================
# SHARED SITE CHROME
# ==========================================================

def site_footer():
    render(f"""
    <div class="site-foot">
      <div><div style="display:flex;gap:.7rem;align-items:center">{brand_mark(36, "f")}
        <span class="brand-name">FOOTLENS</span></div>
        <p style="margin-top:.8rem;max-width:300px">Football injury intelligence for analysts who want to see what sits beneath the match sheet.</p></div>
      <div><h5>Workspaces</h5><ul><li>Command Centre</li><li>Injury Intelligence</li><li>Player Recovery Lab</li></ul></div>
      <div><h5>Studio</h5><ul><li>Club Comparison Studio</li><li>Data Explorer</li><li>Methodology</li></ul></div>
      <div><h5>Good to know</h5><ul><li>Descriptive analysis only</li><li>Session-only profile</li><li>Missing values are never filled</li></ul></div>
    </div>
    <div class="legal">FOOTLENS ANALYTICS · BEYOND THE GAME, BEHIND THE NUMBERS</div>""")


def landing_stats():
    """Real numbers for the hero, or None if the bundled dataset is not present."""
    try:
        d = load_dataset(None)
    except Exception:
        return None
    return {
        "records": int(len(d)),
        "players": int(d["Name"].nunique()) if "Name" in d.columns else 0,
        "clubs": int(d["Team Name"].nunique()) if "Team Name" in d.columns else 0,
        "seasons": sorted(d["Season"].dropna().astype(str).unique().tolist()) if "Season" in d.columns else [],
        "recovery_cov": completeness(d, "Recovery_Days"),
        "rating_cov": completeness(d, "Performance_Change"),
    }


# ==========================================================
# LANDING PAGE
# ==========================================================

def go_profile(target):
    st.session_state.nav_page = target
    st.session_state.page = "profile"


def render_landing():
    stats = landing_stats()
    left, right = st.columns([1.05, 1], gap="large")

    with left:
        status = (f"Dataset connected · {stats['records']:,} records" if stats else "Awaiting dataset")
        render(f"""
        <div style="min-height:2.2rem"></div>
        <div class="eyebrow" style="--a:#2ef2a0">FootLens · Performance intelligence</div>
        <h1 class="rise" style="font:700 clamp(2.7rem,6vw,5.4rem)/.96 'Space Grotesk';letter-spacing:-.05em;margin:1.1rem 0 1.2rem">
          BEYOND THE GAME.<br><span class="grad" style="--a:#22d3ee;--b:#2ef2a0">BEHIND THE NUMBERS.</span></h1>
        <p class="rise" style="--i:2;color:#a9bdd8;font-size:1.08rem;line-height:1.7;max-width:540px">
          Decode player availability. Understand injury patterns. Reveal the performance signals hidden beneath every match.</p>
        <div class="rise" style="--i:3;margin:1.1rem 0 1.4rem"><span class="chip"><i style="width:7px;height:7px;border-radius:50%;background:#2ef2a0;display:inline-block;animation:pulseDot 1.8s infinite"></i>{esc(status)}</span></div>
        """)
        b1, b2 = st.columns(2)
        with b1:
            st.button("Explore the platform", type="primary", key="cta_explore",
                      on_click=go_profile, args=("Command Centre",), **SK_BTN)
        with b2:
            st.button("Discover the analytics", key="cta_discover",
                      on_click=go_profile, args=("Injury Intelligence",), **SK_BTN)
        st.caption("Session-only analyst profile. Nothing is stored beyond this browser session.")
        render('<div class="scroll-hint"><div class="m"></div><span>SCROLL TO EXPLORE</span></div>')

    with right:
        hero_visual(stats, height=580)

    if stats:
        seasons = stats["seasons"]
        span = f"{seasons[0]} – {seasons[-1]}" if seasons else "multiple seasons"
        items = [
            f"<span><b>{stats['records']:,}</b> injury records</span>",
            f"<span><b>{stats['players']:,}</b> players</span>",
            f"<span><b>{stats['clubs']:,}</b> clubs</span>",
            f"<span><b>{len(seasons)}</b> seasons · {esc(span)}</span>",
            "<span>Recovery · ratings · team form</span>",
        ]
        rail = "".join(items) * 2
        render(f'<div class="ticker"><div class="rail">{rail}</div></div>')

    section_label("THE WORKSPACE", "Six rooms. One football intelligence system.",
                  "Each room answers a different question about availability, recovery and team form.")
    rooms = [
        ("grid", "Command Centre", "The live overview: volume, recovery, rating change and data quality in one board."),
        ("pulse", "Injury Intelligence", "Heatmaps, treemaps and distributions that show when, where and how injuries occur."),
        ("user", "Player Recovery Lab", "A dedicated profile per player with timeline, before-and-after ratings and recovery."),
        ("bars", "Club Comparison Studio", "Put clubs side by side on volume, recovery and results during absences."),
        ("table", "Data Explorer", "Search, filter, choose columns and export the exact records you are looking at."),
        ("book", "Methodology", "Plain-language definitions so every metric can be checked."),
    ]
    cols = st.columns(3)
    for i, (ic, title, copy) in enumerate(rooms):
        with cols[i % 3]:
            render(f"""
            <div class="panel feat reveal" style="margin-bottom:1rem">
              <div class="ico">{icon_svg(ic, 22)}</div>
              <div class="ft">{esc(title)}</div><div class="fc">{esc(copy)}</div></div>""")

    render("""
    <div class="callout reveal">FootLens describes the records it is given. It does not establish causation:
    opposition, tactics, venue and squad changes all shape results alongside any one player's absence.</div>""")
    site_footer()


# ==========================================================
# PROFILE PAGE
# ==========================================================

def render_profile():
    page_hero("Workspace access · Analyst profile", "Set up your", "analyst workspace.",
              "Choose a display name for this local session. It appears in the sidebar and nowhere else.",
              "#22d3ee", "#9b7bff", "player")
    left, right = st.columns([1, 1.1], gap="large")

    with left:
        render(f"""
        <div class="panel flat">
          <div class="ico" style="width:46px;height:46px;border-radius:14px;display:grid;place-items:center;color:#22d3ee;margin-bottom:.9rem;background:linear-gradient(145deg,#0f2040,#081428);border:1px solid rgba(34,211,238,.25)">{icon_svg("shield", 22)}</div>
          <div class="ft" style="font:700 1.1rem Manrope">What opens next</div>
          <div class="fc" style="color:#98acc6;font-size:.88rem;line-height:1.6;margin:.4rem 0 .8rem">
            A workspace with global filters, a command centre, player recovery profiles, club comparisons
            and downloadable records.</div>
          <span class="chip">Session-only profile</span><span class="chip c">No password</span>
        </div>""")

    with right:
        with st.form("profile_form"):
            st.markdown("### Analyst details")
            display_name = st.text_input("Display name", placeholder="e.g. Football Analyst")
            role = st.selectbox("Primary focus", [
                "Performance Analyst", "Sports Scientist", "Team Researcher",
                "Student / Project Evaluator", "Other"])
            accepted = st.checkbox("I understand this is a session-only demo profile.")
            submitted = st.form_submit_button("Open workspace", type="primary", **SK_FORM)

            if submitted:
                if not display_name.strip():
                    st.error("Enter a display name to continue.")
                elif not accepted:
                    st.error("Confirm the session-only notice to continue.")
                else:
                    st.session_state.profile = {"name": display_name.strip(), "role": role}
                    st.session_state.session_start = datetime.now()
                    st.session_state.page = "dashboard"
                    st.rerun()

    if st.button("Back to landing page", key="back_landing"):
        st.session_state.page = "landing"
        st.rerun()


# ==========================================================
# SMALL CHART/UI UTILITIES USED BY PAGES
# ==========================================================

def safe_multiselect(label, options, key, container=st, default=None, **kw):
    """Multiselect whose stored selection can never contain stale options."""
    options = list(options)
    want = list(options) if default is None else [d for d in default if d in options]
    if key in st.session_state:
        current = st.session_state[key]
        cleaned = [x for x in current if x in options]
        if len(cleaned) != len(current):
            st.session_state[key] = cleaned or want
        return container.multiselect(label, options, key=key, **kw)
    return container.multiselect(label, options, default=want, key=key, **kw)


def donut(labels, values, colors, center_top, center_sub, key, height=340):
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.7, sort=False, direction="clockwise",
        marker=dict(colors=colors, line=dict(color="#050912", width=2.5)),
        textinfo="none",
        hovertemplate="<b>%{label}</b><br>%{value:,} records · %{percent}<extra></extra>",
    ))
    style_fig(fig, height, legend=True)
    fig.update_layout(
        margin=dict(l=8, r=8, t=14, b=14),
        legend=dict(orientation="v", x=1.0, y=0.5, font=dict(size=11)),
        annotations=[dict(
            text=f"<b>{center_top}</b><br><span style='font-size:11px;color:#8fa3bf'>{center_sub}</span>",
            showarrow=False, font=dict(size=28, family="Manrope, sans-serif", color="#f4f9ff"),
        )],
    )
    show(fig, key)


def mode_or(series, fallback="Unavailable"):
    m = series.dropna().mode()
    return str(m.iloc[0]) if not m.empty else fallback


def tone_for(delta, eps=0.05):
    if delta is None or pd.isna(delta):
        return PAL["cyan"], "No rating data"
    if delta > eps:
        return PAL["emerald"], "Improved after return"
    if delta < -eps:
        return PAL["coral"], "Lower after return"
    return PAL["amber"], "Broadly unchanged"


def signed(v, d=2):
    return "—" if v is None or pd.isna(v) else f"{v:+.{d}f}"


# ==========================================================
# PAGE: COMMAND CENTRE
# ==========================================================

def page_command(f, df):
    page_hero(
        "Command Centre · Overview", "The availability", "intelligence board.",
        "A live read on injury volume, recovery, player ratings and club outcomes across your current selection.",
        PAL["cyan"], PAL["emerald"], "cc",
    )

    rec = safe_num(f, "Recovery_Days").dropna()
    perf = safe_num(f, "Performance_Change").dropna()
    n_players = int(f["Name"].nunique())
    n_clubs = int(f["Team Name"].nunique())

    kpi_strip([
        dict(label="Injury records", value=len(f), icon="pulse", accent=PAL["cyan"],
             note=f"{pct(len(f), len(df)):.0f}% of the {len(df):,} records loaded", fill=len(f) / max(len(df), 1)),
        dict(label="Players affected", value=n_players, icon="user", accent=PAL["emerald"],
             note=f"{len(f) / max(n_players, 1):.1f} injury records per player", fill=0.62),
        dict(label="Clubs represented", value=n_clubs, icon="shield", accent=PAL["violet"],
             note=f"of {int(df['Team Name'].nunique())} clubs in the dataset",
             fill=n_clubs / max(int(df['Team Name'].nunique()), 1)),
        dict(label="Avg. recovery", value=(float(rec.mean()) if len(rec) else None), decimals=0, suffix="days",
             icon="clock", accent=PAL["amber"],
             note=(f"Median {rec.median():.0f} days across {len(rec):,} cases with a recorded period" if len(rec) else "No recorded recovery periods"),
             fill=pct(len(rec), len(f)) / 100),
        dict(label="Avg. rating change", value=(float(perf.mean()) if len(perf) else None), decimals=2, signed=True,
             icon="trend", accent=PAL["coral"] if len(perf) and perf.mean() < 0 else PAL["emerald"],
             note=(f"{pct((perf > 0).sum(), len(perf)):.0f}% of {len(perf):,} rated cases improved after return" if len(perf) else "No before/after ratings"),
             fill=pct(len(perf), len(f)) / 100),
    ])

    # ---- featured trend + injury mix ----
    a, b = st.columns([1.6, 1], gap="large")
    peak_txt = None
    with a:
        section_label("Featured · Trend signal", "Injury volume over time",
                      "Records per month by injury date, with a 3-month rolling average. Undated records are left out of this chart.")
        if "Date of Injury" in f.columns and f["Date of Injury"].notna().any():
            trend = f.dropna(subset=["Date of Injury"]).copy()
            trend["Month"] = trend["Date of Injury"].dt.to_period("M").dt.to_timestamp()
            trend = trend.groupby("Month").size().reset_index(name="Records").sort_values("Month")
            full = pd.date_range(trend["Month"].min(), trend["Month"].max(), freq="MS")
            trend = trend.set_index("Month").reindex(full, fill_value=0).rename_axis("Month").reset_index()
            trend["Rolling"] = trend["Records"].rolling(3, min_periods=3).mean()
            fig = go.Figure()
            fig.add_trace(gradient_area(trend["Month"], trend["Records"], "34,211,238", "Records",
                                        "%{x|%b %Y}<br><b>%{y}</b> injury records<extra></extra>"))
            if trend["Rolling"].notna().any():
                fig.add_trace(go.Scatter(
                    x=trend["Month"], y=trend["Rolling"], name="3-month average", mode="lines",
                    line=dict(color=PAL["amber"], width=2, dash="dot"),
                    hovertemplate="%{x|%b %Y}<br>3-month avg <b>%{y:.1f}</b><extra></extra>"))
            style_fig(fig, 380, legend=True)
            fig.update_yaxes(title_text="Records")
            show(fig, "cc_trend")
            top = trend.sort_values("Records", ascending=False).iloc[0]
            peak_txt = (top["Month"].strftime("%B %Y"), int(top["Records"]), int(trend["Records"].sum()))
        else:
            st.info("Date information is unavailable for this selection.")

    with b:
        section_label("Injury mix", "Most frequent injury types",
                      "Case and spelling variants are merged (for example “Knee injury” and “knee injury”).")
        mix = f["Injury_Clean"].value_counts()
        top7 = mix.head(7)
        rest = int(mix.iloc[7:].sum())
        labels = top7.index.tolist() + (["All other types"] if rest else [])
        values = top7.tolist() + ([rest] if rest else [])
        seq = [PAL["cyan"], PAL["emerald"], PAL["violet"], PAL["amber"], "#6ea8ff", PAL["coral"], "#ff9f7a", "#4f6382"]
        donut(labels, values, seq[:len(labels)], f"{len(f):,}", "records", "cc_mix", 380)

    # ---- insight panels ----
    st.write("")
    i1, i2, i3 = st.columns(3, gap="large")
    cat_counts = f["Injury_Category"].value_counts()
    with i1:
        if peak_txt:
            insight("cyan", "pulse", "Peak month", peak_txt[0],
                    f"{peak_txt[1]} injury records, {pct(peak_txt[1], peak_txt[2]):.0f}% of all dated records in this selection.", 0)
        else:
            insight("cyan", "pulse", "Peak month", "Unavailable", "No injury dates in this selection.", 0)
    with i2:
        if not cat_counts.empty:
            insight("emerald", "shield", "Leading category", str(cat_counts.index[0]),
                    f"{pct(cat_counts.iloc[0], len(f)):.0f}% of records fall in this keyword-based category.", 1)
    with i3:
        if len(rec) >= 3:
            skew = ("A mean above the median means a few long layoffs pull the average up."
                    if rec.mean() > rec.median() else "Mean and median sit close together.")
            insight("amber", "clock", "Recovery skew", f"Median {rec.median():.0f} d · Mean {rec.mean():.0f} d", skew, 2)
        else:
            insight("amber", "clock", "Recovery skew", "Not enough data", "Fewer than three recovery periods in this selection.", 2)

    st.write("")
    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        section_label("Recovery", "Recovery distribution")
        if len(rec):
            cap = float(rec.quantile(0.95))
            shown = rec[rec <= cap]
            hidden = len(rec) - len(shown)
            fig = go.Figure(go.Histogram(
                x=shown, nbinsx=18,
                marker=dict(color="rgba(34,211,238,.55)", line=dict(color=PAL["cyan"], width=1)),
                hovertemplate="%{x} days<br><b>%{y}</b> cases<extra></extra>"))
            fig.add_vline(x=float(rec.median()), line_dash="dash", line_color=PAL["amber"],
                          annotation_text=f"median {rec.median():.0f} d", annotation_font_color=PAL["amber"])
            style_fig(fig, 320)
            fig.update_xaxes(title_text="Recovery days")
            show(fig, "cc_rec")
            if hidden:
                st.caption(f"Axis capped at the 95th percentile ({cap:.0f} days); {hidden} longer layoffs are not drawn.")
        else:
            st.info("No recovery-day values.")
    with c2:
        section_label("Player form", "Rating change profile")
        if len(perf):
            size = 0.25
            start = float(np.floor(perf.min() / size) * size)
            end = float(np.ceil(perf.max() / size) * size + size)
            fig = go.Figure()
            for part, color, name in [(perf[perf < 0], PAL["coral"], "Lower after return"),
                                      (perf[perf >= 0], PAL["emerald"], "Same or higher")]:
                fig.add_trace(go.Histogram(
                    x=part, name=name, xbins=dict(start=start, end=end, size=size),
                    marker=dict(color=color, opacity=0.75),
                    hovertemplate="%{x:.2f}<br><b>%{y}</b> cases<extra></extra>"))
            fig.add_vline(x=0, line_dash="dash", line_color=PAL["amber"])
            style_fig(fig, 320, legend=True)
            fig.update_layout(barmode="overlay")
            fig.update_xaxes(title_text="Post minus pre rating")
            show(fig, "cc_perf")
        else:
            st.info("No rating-change values.")
    with c3:
        section_label("Club signal", "Records by club")
        cc = f["Team Name"].value_counts().rename_axis("Club").reset_index(name="Records")
        render(f'<div class="panel flat" style="padding:.6rem 1.1rem">{leaderboard(cc, "Club", "Records")}</div>')

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    q1, q2 = st.columns([1.4, 1], gap="large")
    with q1:
        section_label("Quick read", "Automated descriptive insights")
        k1, k2, k3 = st.columns(3)
        vals = [
            ("Most common injury", mode_or(f["Injury_Clean"]), "Most frequently recorded injury in this selection."),
            ("Most represented club", mode_or(f["Team Name"]), "Club with the most injury records in this selection."),
            ("Rating data available", f"{len(perf):,}", "Cases with a usable pre/post rating change."),
        ]
        for col, (label, value, desc) in zip((k1, k2, k3), vals):
            with col:
                render(f"""<div class="panel" style="min-height:150px"><div class="sec-kicker" style="margin:0">{esc(label)}</div>
                <div style="font:700 1.15rem Manrope;margin:.5rem 0 .3rem;color:#f2f8ff">{esc(value)}</div>
                <div class="sec-desc" style="margin:0">{esc(desc)}</div></div>""")
    with q2:
        section_label("Data quality", "How complete is this selection?")
        rows = [("Injury date", "Date of Injury"), ("Recovery days", "Recovery_Days"),
                ("Pre-injury rating", "Avg_Pre_Injury_Rating"), ("Post-injury rating", "Avg_Post_Injury_Rating"),
                ("Rating change", "Performance_Change"), ("Goal difference in absence", "Avg_GD_During_Absence")]
        body = "".join(meter(lbl, completeness(f, col)) for lbl, col in rows if col in f.columns)
        render(f'<div class="panel flat">{body}</div>')


# ==========================================================
# PAGE: INJURY INTELLIGENCE
# ==========================================================

def page_injury(f, df):
    page_hero(
        "Analytics control room · 01", "Where, when and how", "injuries happen.",
        "Distributions, seasonality, positions, recovery and team outcomes. Charts describe the records; they do not prove cause.",
        PAL["violet"], PAL["cyan"], "inj",
    )

    with st.expander("Focus filters (apply to this page only)", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        cats = sorted(f["Injury_Category"].dropna().unique().tolist())
        grps = sorted(f["Position_Group"].dropna().unique().tolist())
        sel_cat = safe_multiselect("Injury category", cats, "ii_cat", c1)
        sel_grp = safe_multiselect("Position group", grps, "ii_grp", c2)
        min_cases = c3.slider("Min. cases per injury type", 1, 10, 2, key="ii_min",
                              help="Used by the team-impact chart.")
        log_rec = c4.toggle("Log scale for recovery days", value=True, key="ii_log",
                            help="Recovery is heavily skewed; log scale keeps long layoffs from flattening the rest.")

    v = f[f["Injury_Category"].isin(sel_cat) & f["Position_Group"].isin(sel_grp)].copy()
    if v.empty:
        st.warning("The focus filters leave no records. Widen the category or position selection.")
        return
    st.caption(f"{len(v):,} of {len(f):,} records after focus filters.")

    t1, t2, t3, t4, t5 = st.tabs(["Distribution", "Time & seasonality", "Positions & age",
                                  "Recovery duration", "Team impact"])
    yscale = "log" if log_rec else "linear"

    # ---------------- Distribution ----------------
    with t1:
        a, b = st.columns([1.5, 1], gap="large")
        with a:
            section_label("Injury distribution", "Treemap of injury types by category",
                          "Tile area is the number of records. The 36 largest injury types are drawn; the rest are grouped as “Other types”.")
            g = v.groupby(["Injury_Category", "Injury_Clean"], as_index=False).agg(Records=("Name", "size"))
            top = g.sort_values("Records", ascending=False).head(36)
            rest = g.drop(top.index).groupby("Injury_Category", as_index=False)["Records"].sum()
            rest["Injury_Clean"] = "Other types"
            tm = pd.concat([top, rest[rest["Records"] > 0]], ignore_index=True)
            fig = px.treemap(tm, path=[px.Constant("All injuries"), "Injury_Category", "Injury_Clean"],
                             values="Records", color="Injury_Category",
                             color_discrete_map={**CAT_COLORS, "(?)": "#0b1630"})
            fig.update_traces(
                root_color="rgba(0,0,0,0)", marker=dict(line=dict(width=2, color="#050912")),
                hovertemplate="<b>%{label}</b><br>%{value:,} records<br>%{percentRoot:.1%} of selection<extra></extra>",
                textfont=dict(family="DM Sans, sans-serif"))
            style_fig(fig, 470)
            fig.update_layout(margin=dict(l=6, r=6, t=10, b=6))
            show(fig, "ii_tree")
        with b:
            section_label("Injury-category comparison", "Share of records by category")
            cc = v["Injury_Category"].value_counts()
            donut(cc.index.tolist(), cc.tolist(), [CAT_COLORS.get(c, "#4f6382") for c in cc.index],
                  f"{len(v):,}", "records", "ii_catdonut", 470)
        share = pct(cc.iloc[0], len(v))
        insight("violet", "shield", "Reading this chart", f"{cc.index[0]} leads with {share:.0f}% of records",
                "Categories come from keyword rules applied to the injury description, so they group similar problems rather than reproduce a medical classification.")

    # ---------------- Time ----------------
    with t2:
        section_label("Injury frequency over time", "Monthly records by category",
                      "Stacked by injury category. Records without an injury date are not shown.")
        d = v.dropna(subset=["Date of Injury"]).copy()
        if not d.empty:
            d["Month"] = d["Date of Injury"].dt.to_period("M").dt.to_timestamp()
            mc = d.groupby(["Month", "Injury_Category"]).size().reset_index(name="Records")
            fig = px.bar(mc, x="Month", y="Records", color="Injury_Category", color_discrete_map=CAT_COLORS)
            fig.update_traces(hovertemplate="%{x|%b %Y}<br>%{fullData.name}: <b>%{y}</b><extra></extra>",
                              marker_line_width=0)
            style_fig(fig, 380, legend=True)
            fig.update_layout(barmode="stack", bargap=0.15)
            show(fig, "ii_monthly")
        else:
            st.info("No dated records in this selection.")

        h1, h2 = st.columns(2, gap="large")
        mdata = v.dropna(subset=["Month_Label"])
        with h1:
            section_label("Monthly injury heatmap", "Season by month",
                          "Months run in football-season order, August to July.")
            if not mdata.empty:
                heat = (mdata.groupby(["Season", "Month_Label"]).size().unstack(fill_value=0)
                        .reindex(columns=MONTHS_SEASON, fill_value=0))
                fig = px.imshow(heat, aspect="auto", color_continuous_scale=AURORA, text_auto=True,
                                labels=dict(x="Month", y="Season", color="Injuries"))
                fig.update_traces(hovertemplate="%{y} · %{x}<br><b>%{z}</b> injuries<extra></extra>")
                style_fig(fig, 360)
                fig.update_layout(coloraxis_showscale=False)
                fig.update_xaxes(side="top", tickangle=-35)
                show(fig, "ii_heat_season")
                flat = heat.stack()
                if flat.max() > 0:
                    (s_, m_), n_ = flat.idxmax(), int(flat.max())
                    st.caption(f"Busiest cell: {m_} {s_} with {n_} records.")
            else:
                st.info("Month information is unavailable.")
        with h2:
            section_label("Seasonality", "Monthly injury frequency by club")
            if not mdata.empty:
                heat = (mdata.groupby(["Team Name", "Month_Label"]).size().unstack(fill_value=0)
                        .reindex(columns=MONTHS_SEASON, fill_value=0))
                fig = px.imshow(heat, aspect="auto", color_continuous_scale=AURORA,
                                labels=dict(x="Month", y="Club", color="Injuries"))
                fig.update_traces(hovertemplate="%{y} · %{x}<br><b>%{z}</b> injuries<extra></extra>")
                style_fig(fig, 360)
                fig.update_xaxes(side="top", tickangle=-35)
                fig.update_layout(coloraxis_colorbar=dict(thickness=10, len=0.8, title=dict(text="")))
                show(fig, "ii_heat_club")
            else:
                st.info("Month information is unavailable.")

    # ---------------- Positions & age ----------------
    with t3:
        p1, p2 = st.columns(2, gap="large")
        with p1:
            section_label("Position-wise distribution", "Records by position group and position",
                          "Counts are not adjusted for how many players occupy each position.")
            ps = v.groupby(["Position_Group", "Position"], as_index=False).agg(Records=("Name", "size"))
            fig = px.sunburst(ps, path=["Position_Group", "Position"], values="Records", color="Position_Group",
                              color_discrete_map={**GROUP_COLORS, "(?)": "#0b1630"})
            fig.update_traces(marker=dict(line=dict(width=2, color="#050912")),
                              hovertemplate="<b>%{label}</b><br>%{value:,} records<extra></extra>")
            style_fig(fig, 430)
            fig.update_layout(margin=dict(l=6, r=6, t=10, b=6))
            show(fig, "ii_sun")
        with p2:
            section_label("Category mix", "What kind of injuries each position group records")
            pc = v.groupby(["Position_Group", "Injury_Category"]).size().reset_index(name="Records")
            fig = px.bar(pc, y="Position_Group", x="Records", color="Injury_Category", orientation="h",
                         color_discrete_map=CAT_COLORS)
            fig.update_traces(hovertemplate="%{y}<br>%{fullData.name}: <b>%{x:.0f}%</b><extra></extra>",
                              marker_line_width=0)
            style_fig(fig, 430, legend=True)
            fig.update_layout(barmode="stack", barnorm="percent")
            fig.update_xaxes(title_text="Share of group's records (%)")
            show(fig, "ii_posmix")

        g1, g2 = st.columns(2, gap="large")
        with g1:
            section_label("Age-group analysis", "Records by age group")
            ag = v.dropna(subset=["Age_Group"]).groupby("Age_Group").size().reindex(AGE_ORDER, fill_value=0).reset_index()
            ag.columns = ["Age group", "Records"]
            fig = go.Figure(go.Bar(
                x=ag["Age group"], y=ag["Records"],
                marker=dict(color=ag["Records"], colorscale=AURORA, line=dict(width=0)),
                hovertemplate="Age %{x}<br><b>%{y}</b> records<extra></extra>"))
            style_fig(fig, 340)
            fig.update_yaxes(title_text="Records")
            show(fig, "ii_age_bar")
        with g2:
            section_label("Age and recovery", "Recovery days by age group")
            ad = v.dropna(subset=["Age_Group", "Recovery_Days"])
            if len(ad) >= 5:
                fig = px.box(ad, x="Age_Group", y="Recovery_Days", category_orders={"Age_Group": AGE_ORDER},
                             color_discrete_sequence=[PAL["violet"]], points="outliers")
                fig.update_traces(marker=dict(size=4, opacity=0.6),
                                  hovertemplate="Age %{x}<br>%{y} days<extra></extra>")
                style_fig(fig, 340)
                fig.update_yaxes(type=yscale, title_text="Recovery days")
                fig.update_xaxes(title_text="")
                show(fig, "ii_age_box")
            else:
                st.info("Not enough recovery records to compare age groups.")

        section_label("Scatter", "Age against recovery",
                      "Each point is one injury record. Marker size follows the player's FIFA rating.")
        sc = v.dropna(subset=["Age", "Recovery_Days"])
        if not sc.empty:
            has_fifa = "FIFA rating" in sc.columns and sc["FIFA rating"].notna().any()
            hover = {"Name": True, "Injury_Clean": True, "Position_Group": False}
            if has_fifa:
                hover["FIFA rating"] = True
            fig = px.scatter(sc, x="Age", y="Recovery_Days", color="Position_Group",
                             size=("FIFA rating" if has_fifa else None), size_max=14, opacity=0.72,
                             color_discrete_map=GROUP_COLORS, hover_data=hover)
            style_fig(fig, 400, legend=True)
            fig.update_yaxes(type=yscale, title_text="Recovery days")
            show(fig, "ii_scatter")
        pg = v["Position_Group"].value_counts()
        insight("cyan", "user", "Most records", f"{pg.index[0]} · {pct(pg.iloc[0], len(v)):.0f}% of records",
                "A larger share partly reflects how many players play in that group, so read it as volume, not risk.")

    # ---------------- Duration ----------------
    with t4:
        r1, r2 = st.columns([1.5, 1], gap="large")
        rd = v.dropna(subset=["Recovery_Days"])
        with r1:
            section_label("Injury duration analysis", "Recovery distribution by category",
                          "Violin width shows where recovery periods cluster; the box marks the median and quartiles. Categories with fewer than 4 recovery records are skipped.")
            counts = rd["Injury_Category"].value_counts()
            keep = counts[counts >= 4].index
            vd = rd[rd["Injury_Category"].isin(keep)]
            if not vd.empty:
                fig = px.violin(vd, x="Injury_Category", y="Recovery_Days", color="Injury_Category",
                                color_discrete_map=CAT_COLORS, box=True, points=False)
                fig.update_traces(meanline_visible=True,
                                  hovertemplate="%{x}<br>%{y} days<extra></extra>")
                style_fig(fig, 430)
                fig.update_yaxes(type=yscale, title_text="Recovery days")
                fig.update_xaxes(title_text="", tickangle=-20)
                show(fig, "ii_violin")
            else:
                st.info("Not enough recovery records for a distribution chart.")
        with r2:
            section_label("Layoff length", "Records by recovery band")
            bd = rd.dropna(subset=["Recovery_Band"]).groupby("Recovery_Band").size().reindex(BAND_ORDER, fill_value=0)
            fig = go.Figure(go.Bar(
                x=bd.index, y=bd.values, marker=dict(color=bd.values, colorscale=VIOLET_SCALE, line=dict(width=0)),
                hovertemplate="%{x}<br><b>%{y}</b> records<extra></extra>"))
            style_fig(fig, 430)
            fig.update_yaxes(title_text="Records")
            show(fig, "ii_bands")

        section_label("Category comparison", "Recovery summary by injury category")
        if not rd.empty:
            tbl = rd.groupby("Injury_Category").agg(
                Records=("Recovery_Days", "size"), Median=("Recovery_Days", "median"),
                Mean=("Recovery_Days", "mean"), P90=("Recovery_Days", lambda s: s.quantile(0.9)),
                Longest=("Recovery_Days", "max")).reset_index().sort_values("Median", ascending=False)
            tbl.columns = ["Category", "Records with recovery", "Median days", "Mean days", "90th percentile days", "Longest (days)"]
            st.dataframe(tbl, hide_index=True, **SK_DF, column_config={
                "Median days": st.column_config.NumberColumn(format="%.0f"),
                "Mean days": st.column_config.NumberColumn(format="%.1f"),
                "90th percentile days": st.column_config.NumberColumn(format="%.0f"),
                "Longest (days)": st.column_config.NumberColumn(format="%.0f")})
            solid = tbl[tbl["Records with recovery"] >= 5]
            if not solid.empty:
                lead = solid.iloc[0]
                insight("amber", "clock", "Longest typical layoff", f"{lead['Category']} · median {lead['Median days']:.0f} days",
                        "Only categories with at least five recovery records are considered.")

    # ---------------- Team impact ----------------
    with t5:
        section_label("Team outcome", "Observed team performance change during absence",
                      "Positive values mean average goal difference was lower during the absence than before the injury.")
        imp = v.dropna(subset=["Team_Performance_Drop"])
        if not imp.empty:
            summ = imp.groupby("Injury_Clean", as_index=False).agg(
                Mean_Drop=("Team_Performance_Drop", "mean"), Cases=("Name", "size"))
            summ = summ[summ["Cases"] >= min_cases].sort_values("Mean_Drop", ascending=False).head(12)
            if not summ.empty:
                summ = summ.sort_values("Mean_Drop")
                fig = go.Figure(go.Bar(
                    x=summ["Mean_Drop"], y=summ["Injury_Clean"], orientation="h", customdata=summ["Cases"],
                    marker=dict(color=[PAL["coral"] if x > 0 else PAL["emerald"] for x in summ["Mean_Drop"]],
                                line=dict(width=0)),
                    hovertemplate="<b>%{y}</b><br>Mean change %{x:+.2f} goal difference<br>%{customdata} cases<extra></extra>"))
                fig.add_vline(x=0, line_dash="dash", line_color=PAL["amber"])
                style_fig(fig, 440)
                fig.update_xaxes(title_text="Goal difference before minus during absence")
                show(fig, "ii_drop")
            else:
                st.info(f"No injury type has at least {min_cases} complete records. Lower the minimum in Focus filters.")
        else:
            st.info("No complete pre-injury and absence goal-difference records are available.")

        s1, s2 = st.columns(2, gap="large")
        with s1:
            section_label("Before against during", "Goal difference per record",
                          "Points above the diagonal mean the team did better during the absence than before.")
            sd = v.dropna(subset=["Avg_GD_Before_Injury", "Avg_GD_During_Absence"])
            if not sd.empty:
                lo = float(min(sd["Avg_GD_Before_Injury"].min(), sd["Avg_GD_During_Absence"].min()))
                hi = float(max(sd["Avg_GD_Before_Injury"].max(), sd["Avg_GD_During_Absence"].max()))
                fig = px.scatter(sd, x="Avg_GD_Before_Injury", y="Avg_GD_During_Absence", color="Injury_Category",
                                 color_discrete_map=CAT_COLORS, opacity=0.75,
                                 hover_data={"Name": True, "Team Name": True, "Injury_Clean": True,
                                             "Injury_Category": False})
                fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", name="No change",
                                         line=dict(color=PAL["amber"], dash="dash", width=1.5), hoverinfo="skip"))
                style_fig(fig, 400, legend=True)
                fig.update_xaxes(title_text="Avg. goal difference before injury")
                fig.update_yaxes(title_text="Avg. goal difference during absence")
                show(fig, "ii_gd_scatter")
            else:
                st.info("No records with both goal-difference measures.")
        with s2:
            section_label("Results in absence", "Points per absence match by category",
                          "Total points divided by absence matches recorded. Categories with fewer than 4 records are skipped.")
            pp = v.dropna(subset=["Points_Per_Absence_Match"])
            cnt = pp["Injury_Category"].value_counts()
            pp = pp[pp["Injury_Category"].isin(cnt[cnt >= 4].index)]
            if not pp.empty:
                fig = px.box(pp, x="Injury_Category", y="Points_Per_Absence_Match", color="Injury_Category",
                             color_discrete_map=CAT_COLORS, points="all")
                fig.update_traces(marker=dict(size=3, opacity=0.5),
                                  hovertemplate="%{x}<br>%{y:.2f} points per match<extra></extra>")
                style_fig(fig, 400)
                fig.update_xaxes(title_text="", tickangle=-20)
                fig.update_yaxes(title_text="Points per match")
                show(fig, "ii_pts_box")
            else:
                st.info("Not enough absence-match records to compare.")
        dd = v["Team_Performance_Drop"].dropna()
        if len(dd):
            insight("coral", "trend", "Observed, not causal",
                    f"Goal difference fell in {pct((dd > 0).sum(), len(dd)):.0f}% of {len(dd):,} comparable cases",
                    "Opposition, venue, tactics and other squad changes also shape results, so treat this as context.")


# ==========================================================
# PAGE: PLAYER RECOVERY LAB
# ==========================================================

def page_player(f, df):
    page_hero(
        "Player lab · 02", "One player,", "every injury, in focus.",
        "Inspect injury history, recovery duration and recorded rating changes for a single player.",
        PAL["emerald"], PAL["cyan"], "player",
    )

    players = sorted(f["Name"].dropna().astype(str).unique().tolist())
    s1, s2 = st.columns([1, 1.4], gap="large")
    with s1:
        search = st.text_input("Search player", placeholder="Type a player name…", key="lab_search")
    if search.strip():
        players = [p for p in players if search.lower() in p.lower()]
    if not players:
        st.warning("No players match the current selection.")
        return
    with s2:
        player = st.selectbox("Select player", players)

    pdata = f[f["Name"].astype(str) == player].copy()
    pdata = pdata.sort_values("Date of Injury", na_position="first") if "Date of Injury" in pdata.columns else pdata
    latest = pdata.iloc[-1]

    perf = safe_num(pdata, "Performance_Change")
    pre = safe_num(pdata, "Avg_Pre_Injury_Rating")
    post = safe_num(pdata, "Avg_Post_Injury_Rating")
    rec = safe_num(pdata, "Recovery_Days")
    perf_mean = perf.dropna().mean() if perf.notna().any() else np.nan
    tone, tone_txt = tone_for(perf_mean)

    clubs = " · ".join(pdata["Team Name"].dropna().astype(str).unique())
    seasons_p = pdata["Season"].dropna().astype(str).unique().tolist()
    fifa = pd.to_numeric(pd.Series([latest.get("FIFA rating")]), errors="coerce").iloc[0]
    age = pd.to_numeric(pd.Series([latest.get("Age")]), errors="coerce").iloc[0]
    hue = hue_of(player)

    ring = ""
    if not pd.isna(fifa):
        circ = 2 * 3.14159 * 34
        ring = f"""<div style="text-align:center"><svg width="92" height="92" viewBox="0 0 92 92" style="transform:rotate(-90deg)">
            <circle cx="46" cy="46" r="34" fill="none" stroke="rgba(150,180,220,.15)" stroke-width="7"/>
            <circle cx="46" cy="46" r="34" fill="none" stroke="{tone}" stroke-width="7" stroke-linecap="round"
              stroke-dasharray="{circ * float(fifa) / 100:.1f} {circ:.1f}" style="filter:drop-shadow(0 0 6px {tone});animation:grow 1.4s ease both"/></svg>
            <div style="margin-top:-62px;margin-bottom:34px;font:800 1.5rem Manrope;color:#f4f9ff">{int(fifa)}</div>
            <div class="mono" style="font-size:.6rem;letter-spacing:.16em;color:#8fa3bf">FIFA RATING</div></div>"""

    chips = (f'<span class="chip c">{esc(clubs)}</span>'
             f'<span class="chip v">{esc(latest.get("Position", "—"))}</span>'
             + ("" if pd.isna(age) else f'<span class="chip">Age {int(age)} (latest record)</span>')
             + f'<span class="chip a">{esc(", ".join(seasons_p))}</span>')
    render(f"""
    <div class="profile" style="--h:hsl({hue},85%,60%)">
      <div>{avatar_svg(player, 116)}</div>
      <div><div class="eyebrow" style="--a:{tone}">Player profile</div>
        <div class="nm" style="margin-top:.5rem">{esc(player)}</div>
        <div class="meta">{chips}</div>
        <div style="margin-top:.9rem"><span class="status-glow" style="--t:{tone}"><i></i>{esc(tone_txt)}{'' if pd.isna(perf_mean) else f' · avg {perf_mean:+.2f}'}</span></div></div>
      <div>{ring}</div>
    </div>""")
    st.write("")

    absence_matches = safe_num(pdata, "Absence_Matches_Recorded")
    kpi_strip([
        dict(label="Injury cases", value=len(pdata), icon="pulse", accent=PAL["cyan"],
             note="Recorded injuries in the current filter", fill=min(1, len(pdata) / 8)),
        dict(label="Avg. recovery", value=(float(rec.mean()) if rec.notna().any() else None), decimals=0, suffix="days",
             icon="clock", accent=PAL["amber"], note=f"{int(rec.notna().sum())} case(s) with a recorded period", fill=0.5),
        dict(label="Rating before", value=(float(pre.mean()) if pre.notna().any() else None), decimals=2, icon="user",
             accent=PAL["violet"], note="Mean of pre-injury match ratings", fill=0.6),
        dict(label="Rating after", value=(float(post.mean()) if post.notna().any() else None), decimals=2, icon="user",
             accent=PAL["emerald"], note="Mean of post-return match ratings", fill=0.6),
        dict(label="Rating change", value=(None if pd.isna(perf_mean) else float(perf_mean)), decimals=2, signed=True,
             icon="trend", accent=tone, note="Average of per-case post minus pre", fill=0.55),
        dict(label="Absence matches", value=(float(absence_matches.sum()) if absence_matches.notna().any() else None),
             decimals=0, icon="shield", accent=PAL["coral"], note="Team matches recorded while absent", fill=0.5),
    ], height=196)

    # ---- timeline + charts ----
    st.write("")
    left, right = st.columns([1, 1.25], gap="large")
    with left:
        section_label("Injury timeline", "Every recorded absence")
        items = []
        for i, (_, r) in enumerate(pdata.iterrows()):
            d_inj = r.get("Date of Injury")
            d_ret = r.get("Date of return")
            when = (d_inj.strftime("%d %b %Y") if pd.notna(d_inj) else "Date not recorded")
            if pd.notna(d_ret):
                when += f" → {d_ret.strftime('%d %b %Y')}"
            pc = pd.to_numeric(pd.Series([r.get("Performance_Change")]), errors="coerce").iloc[0]
            tcol, _ = tone_for(pc)
            rd_ = pd.to_numeric(pd.Series([r.get("Recovery_Days")]), errors="coerce").iloc[0]
            pr = pd.to_numeric(pd.Series([r.get("Avg_Pre_Injury_Rating")]), errors="coerce").iloc[0]
            po = pd.to_numeric(pd.Series([r.get("Avg_Post_Injury_Rating")]), errors="coerce").iloc[0]
            pills = ""
            pills += f'<span class="chip a">{int(rd_)} days out</span>' if pd.notna(rd_) else '<span class="chip">Recovery not recorded</span>'
            if pd.notna(pr) and pd.notna(po):
                pills += f'<span class="chip c">{pr:.2f} → {po:.2f}</span>'
            if pd.notna(pc):
                pills += f'<span class="chip" style="color:{tcol};border-color:{tcol}55;background:{tcol}14">Δ {pc:+.2f}</span>'
            items.append(
                f'<div class="tl-item" style="--i:{i};--t:{tcol}"><div class="tl-card"><div class="d">{esc(when)}</div>'
                f'<div class="n">{esc(r.get("Injury_Clean", r.get("Injury", "Injury")))}</div>{pills}</div></div>')
        render(f'<div class="tl">{"".join(items)}</div>')

    labels = []
    for i, (_, r) in enumerate(pdata.iterrows()):
        d_inj = r.get("Date of Injury")
        labels.append(f"{d_inj:%b %Y} · {r.get('Injury_Clean', '')}" if pd.notna(d_inj) else f"Undated · {r.get('Injury_Clean', '')}")
    seen = {}
    uniq = []
    for lab in labels:
        seen[lab] = seen.get(lab, 0) + 1
        uniq.append(lab if seen[lab] == 1 else f"{lab} ({seen[lab]})")
    pdata["Case"] = uniq

    with right:
        section_label("Before versus after", "Rating at injury and after return",
                      "Each line joins the average pre-injury rating to the average post-return rating for one case.")
        both = pdata.dropna(subset=["Avg_Pre_Injury_Rating", "Avg_Post_Injury_Rating"])
        if not both.empty:
            fig = go.Figure()
            for _, r in both.iterrows():
                up = r["Avg_Post_Injury_Rating"] >= r["Avg_Pre_Injury_Rating"]
                fig.add_trace(go.Scatter(x=[r["Avg_Pre_Injury_Rating"], r["Avg_Post_Injury_Rating"]], y=[r["Case"]] * 2,
                                         mode="lines", showlegend=False, hoverinfo="skip",
                                         line=dict(color=PAL["emerald"] if up else PAL["coral"], width=3)))
            fig.add_trace(go.Scatter(x=both["Avg_Pre_Injury_Rating"], y=both["Case"], mode="markers", name="Before injury",
                                     marker=dict(size=13, color=PAL["violet"], line=dict(color="#050912", width=2)),
                                     hovertemplate="%{y}<br>Before: <b>%{x:.2f}</b><extra></extra>"))
            fig.add_trace(go.Scatter(x=both["Avg_Post_Injury_Rating"], y=both["Case"], mode="markers", name="After return",
                                     marker=dict(size=13, color=PAL["cyan"], line=dict(color="#050912", width=2)),
                                     hovertemplate="%{y}<br>After: <b>%{x:.2f}</b><extra></extra>"))
            style_fig(fig, max(300, 90 + 52 * len(both)), legend=True)
            fig.update_xaxes(title_text="Average match rating")
            fig.update_yaxes(autorange="reversed", automargin=True)
            show(fig, "pl_dumbbell")
        else:
            st.info("No case has both a pre-injury and post-return rating.")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        section_label("Recovery duration", "Days out per case")
        rc = pdata.dropna(subset=["Recovery_Days"])
        if not rc.empty:
            fig = go.Figure(go.Bar(
                x=rc["Recovery_Days"], y=rc["Case"], orientation="h",
                marker=dict(color=rc["Recovery_Days"], colorscale=AURORA, line=dict(width=0)),
                hovertemplate="%{y}<br><b>%{x:.0f}</b> days<extra></extra>"))
            style_fig(fig, max(280, 90 + 46 * len(rc)))
            fig.update_yaxes(autorange="reversed", automargin=True)
            fig.update_xaxes(title_text="Recovery days")
            show(fig, "pl_recovery")
        else:
            st.info("No recorded recovery periods for this player.")
    with c2:
        section_label("Performance change", "Rating change per case")
        pc_ = pdata.dropna(subset=["Performance_Change"])
        if not pc_.empty:
            fig = go.Figure(go.Bar(
                x=pc_["Performance_Change"], y=pc_["Case"], orientation="h",
                marker=dict(color=[PAL["emerald"] if x >= 0 else PAL["coral"] for x in pc_["Performance_Change"]], line=dict(width=0)),
                hovertemplate="%{y}<br><b>%{x:+.2f}</b> rating change<extra></extra>"))
            fig.add_vline(x=0, line_color=PAL["amber"], line_dash="dash")
            style_fig(fig, max(280, 90 + 46 * len(pc_)))
            fig.update_yaxes(autorange="reversed", automargin=True)
            fig.update_xaxes(title_text="Post minus pre rating")
            show(fig, "pl_perf")
        else:
            st.info("No rating change recorded for this player.")

    # ---- preserved match-rating timeline ----
    rating_cols = [c for c in pdata.columns if c.endswith("_Player_rating")]
    rows = []
    for _, row in pdata.iterrows():
        for phase, marker in [("Before injury", "_before_injury_"), ("After recovery", "_after_injury_")]:
            cols = [c for c in rating_cols if marker in c]
            values = pd.to_numeric(row[cols], errors="coerce").dropna() if cols else pd.Series(dtype=float)
            if not values.empty:
                rows.append({"Injury date": row.get("Date of Injury"), "Injury": row.get("Injury_Clean", "Unknown"),
                             "Phase": phase, "Average player rating": values.mean()})
    section_label("Match ratings", "Average rating before injury and after recovery")
    tl = pd.DataFrame(rows)
    if not tl.empty:
        tl["Injury date"] = pd.to_datetime(tl["Injury date"], errors="coerce")
        tl = tl.dropna(subset=["Injury date"]).sort_values("Injury date")
    if not tl.empty:
        fig = px.line(tl, x="Injury date", y="Average player rating", color="Phase", markers=True,
                      hover_data=["Injury"], color_discrete_sequence=[PAL["violet"], PAL["emerald"]])
        fig.update_traces(line=dict(width=2.6), marker=dict(size=9))
        style_fig(fig, 360, legend=True)
        show(fig, "pl_ratings")
    else:
        st.info("No usable before/after match-rating series found for this player.")

    st.markdown("#### Injury history")
    display_cols = [c for c in ["Date of Injury", "Date of return", "Injury", "Recovery_Days", "Avg_Pre_Injury_Rating",
                                "Avg_Post_Injury_Rating", "Performance_Change", "Wins_During_Absence",
                                "Points_During_Absence", "Avg_GD_During_Absence"] if c in pdata.columns]
    hist = pdata[display_cols].copy()
    if "Date of Injury" in hist.columns:
        hist = hist.sort_values("Date of Injury", na_position="last")
    st.dataframe(hist, hide_index=True, **SK_DF)


# ==========================================================
# PAGE: CLUB COMPARISON STUDIO
# ==========================================================

METRIC_DOCS = [
    ("Injury volume", "Injury_records", 0, "Number of injury records for the club in the current selection."),
    ("Unique players affected", "Players_affected", 0, "Distinct player names with at least one record."),
    ("Avg. recovery days", "Mean_recovery_days", 1, "Mean of Recovery_Days over records that have a recovery period."),
    ("Avg. rating change", "Mean_rating_change", 2, "Mean of post-return minus pre-injury rating. Positive means higher after return."),
    ("Avg. points during absence", "Mean_points_during_absence", 2, "Total points across the recorded absence matches (up to three), averaged per record."),
    ("Avg. goal difference during absence", "Mean_goal_difference_during_absence", 2, "Mean goal difference across recorded absence matches, averaged per record."),
]


def page_clubs(f, df):
    page_hero(
        "Comparison studio · 03", "Clubs,", "side by side.",
        "Compare recorded injury volume, recovery and absence-period outcomes. Each metric keeps its own unit.",
        PAL["cyan"], PAL["violet"], "club",
    )

    agg = {"Injury_records": ("Name", "size"), "Players_affected": ("Name", "nunique")}
    optional = {
        "Recovery_Days": "Mean_recovery_days", "Performance_Change": "Mean_rating_change",
        "Points_During_Absence": "Mean_points_during_absence", "Avg_GD_During_Absence": "Mean_goal_difference_during_absence",
        "Avg_Pre_Injury_Rating": "Mean_pre_rating", "Avg_Post_Injury_Rating": "Mean_post_rating",
    }
    for src, tgt in optional.items():
        if src in f.columns:
            agg[tgt] = (src, "mean")
    cs = f.groupby("Team Name").agg(**agg).reset_index()
    for c in cs.columns:
        if c != "Team Name":
            cs[c] = pd.to_numeric(cs[c], errors="coerce")

    all_clubs = cs["Team Name"].astype(str).tolist()
    top_default = cs.sort_values("Injury_records", ascending=False)["Team Name"].astype(str).head(2).tolist()
    chosen = safe_multiselect("Clubs to compare (up to 4)", all_clubs, "cmp_clubs", st, default=top_default,
                              max_selections=4)
    if not chosen:
        st.info("Choose at least one club to open the comparison.")
    sel = cs[cs["Team Name"].astype(str).isin(chosen)].copy()

    available = [(lbl, col, dec, doc) for lbl, col, dec, doc in METRIC_DOCS if col in cs.columns]

    if not sel.empty:
        cols = st.columns(len(sel), gap="large")
        for col, (_, r) in zip(cols, sel.iterrows()):
            rows = ""
            for lbl, mcol, dec, _doc in available:
                val = r[mcol]
                txt = "—" if pd.isna(val) else (f"{val:+.{dec}f}" if mcol in ("Mean_rating_change", "Mean_goal_difference_during_absence") else f"{val:,.{dec}f}")
                colr = "#eaf3ff"
                if not pd.isna(val) and mcol in ("Mean_rating_change", "Mean_goal_difference_during_absence"):
                    colr = PAL["emerald"] if val > 0 else (PAL["coral"] if val < 0 else "#eaf3ff")
                rows += (f'<div style="display:flex;justify-content:space-between;gap:1rem;padding:.5rem 0;border-bottom:1px solid rgba(150,180,220,.09)">'
                         f'<span style="color:#8fa3bf;font-size:.78rem">{esc(lbl)}</span>'
                         f'<b style="font:600 .86rem \'DM Mono\';color:{colr}">{txt}</b></div>')
            with col:
                render(f"""<div class="panel" style="--h:hsl({hue_of(r['Team Name'])},80%,60%)">
                  <div style="display:flex;align-items:center;gap:.9rem;margin-bottom:.7rem">{avatar_svg(r['Team Name'], 58)}
                  <div><div style="font:700 1.35rem 'Space Grotesk';color:#f4f9ff">{esc(r['Team Name'])}</div>
                  <div class="mono" style="font-size:.62rem;color:#8fa3bf;letter-spacing:.1em">{int(r['Injury_records'])} RECORDS</div></div></div>
                  {rows}</div>""")

        st.write("")
        g1, g2 = st.columns([1.1, 1], gap="large")
        with g1:
            section_label("Radar", "Relative profile across metrics",
                          "Each axis is scaled 0–100 between the lowest and highest club in the current selection, so different units can share a chart. Hover for the real values.")
            radar_cols = [(lbl, col, dec) for lbl, col, dec, _ in available]
            if len(radar_cols) >= 3:
                fig = go.Figure()
                palette = [PAL["cyan"], PAL["violet"], PAL["emerald"], PAL["amber"]]
                theta = [lbl for lbl, _, _ in radar_cols]
                for k, (_, r) in enumerate(sel.iterrows()):
                    rr, raw = [], []
                    for lbl, mcol, dec in radar_cols:
                        lo, hi = cs[mcol].min(), cs[mcol].max()
                        v = r[mcol]
                        if pd.isna(v):
                            rr.append(0); raw.append("n/a")
                        else:
                            rr.append(50.0 if hi == lo else 100 * (v - lo) / (hi - lo)); raw.append(f"{v:,.{dec}f}")
                    fig.add_trace(go.Scatterpolar(
                        r=rr + rr[:1], theta=theta + theta[:1], name=str(r["Team Name"]), fill="toself",
                        line=dict(color=palette[k % 4], width=2.4), opacity=0.85, customdata=raw + raw[:1],
                        hovertemplate="<b>" + str(r["Team Name"]) + "</b><br>%{theta}<br>Index %{r:.0f}/100<br>Actual: %{customdata}<extra></extra>"))
                style_fig(fig, 440, legend=True)
                fig.update_layout(polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    radialaxis=dict(range=[0, 100], gridcolor=GRID, linecolor=GRID, tickfont=dict(size=9, color="#6f86a6")),
                    angularaxis=dict(gridcolor=GRID, linecolor=GRID, tickfont=dict(size=11, color="#c9d8ee"))),
                    margin=dict(l=60, r=60, t=40, b=30))
                show(fig, "cl_radar")
            else:
                st.info("At least three metrics with data are needed for a radar chart.")
        with g2:
            section_label("Grouped bars", "Volume and players affected",
                          "Both measures are counts, so they share one axis.")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=sel["Team Name"], y=sel["Injury_records"], name="Injury records",
                                 marker=dict(color=PAL["cyan"], line=dict(width=0)),
                                 hovertemplate="%{x}<br><b>%{y}</b> injury records<extra></extra>"))
            fig.add_trace(go.Bar(x=sel["Team Name"], y=sel["Players_affected"], name="Players affected",
                                 marker=dict(color=PAL["violet"], line=dict(width=0)),
                                 hovertemplate="%{x}<br><b>%{y}</b> players<extra></extra>"))
            style_fig(fig, 440, legend=True)
            fig.update_layout(barmode="group", bargap=0.3)
            show(fig, "cl_grouped")

        if {"Mean_pre_rating", "Mean_post_rating"}.issubset(sel.columns):
            d = sel.dropna(subset=["Mean_pre_rating", "Mean_post_rating"])
            if not d.empty:
                section_label("Dumbbell", "Average rating before and after returning",
                              "Both ends are player match ratings, so they share one scale.")
                fig = go.Figure()
                for _, r in d.iterrows():
                    fig.add_trace(go.Scatter(x=[r["Mean_pre_rating"], r["Mean_post_rating"]], y=[r["Team Name"]] * 2,
                                             mode="lines", showlegend=False, hoverinfo="skip",
                                             line=dict(color="rgba(150,180,220,.45)", width=3)))
                fig.add_trace(go.Scatter(x=d["Mean_pre_rating"], y=d["Team Name"], mode="markers", name="Before injury",
                                         marker=dict(size=14, color=PAL["violet"], line=dict(color="#050912", width=2)),
                                         hovertemplate="%{y}<br>Before <b>%{x:.2f}</b><extra></extra>"))
                fig.add_trace(go.Scatter(x=d["Mean_post_rating"], y=d["Team Name"], mode="markers", name="After return",
                                         marker=dict(size=14, color=PAL["cyan"], line=dict(color="#050912", width=2)),
                                         hovertemplate="%{y}<br>After <b>%{x:.2f}</b><extra></extra>"))
                style_fig(fig, max(260, 120 + 60 * len(d)), legend=True)
                fig.update_xaxes(title_text="Average match rating")
                show(fig, "cl_dumbbell")

        section_label("Comparison table", "Selected clubs, metric by metric")
        table = pd.DataFrame({"Metric": [lbl for lbl, *_ in available]})
        for _, r in sel.iterrows():
            table[str(r["Team Name"])] = [
                "—" if pd.isna(r[col]) else (f"{r[col]:+.{dec}f}" if col in ("Mean_rating_change", "Mean_goal_difference_during_absence") else f"{r[col]:,.{dec}f}")
                for _, col, dec, _ in available]
        st.dataframe(table, hide_index=True, **SK_DF)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    section_label("Interactive ranking", "Rank every club on one metric")

    metric_options = {"Injury records": "Injury_records", "Players affected": "Players_affected"}
    display_names = {
        "Mean_recovery_days": "Average recovery days", "Mean_rating_change": "Average rating change",
        "Mean_points_during_absence": "Average points during absence",
        "Mean_goal_difference_during_absence": "Average goal difference during absence",
    }
    for col, label in display_names.items():
        if col in cs.columns:
            metric_options[label] = col
    r1, r2 = st.columns([2, 1])
    metric_label = r1.selectbox("Compare clubs by", list(metric_options))
    order = r2.radio("Order", ["Highest first", "Lowest first"], horizontal=True)
    metric_col = metric_options[metric_label]
    chart = cs.dropna(subset=[metric_col]).sort_values(metric_col, ascending=(order == "Highest first"))
    if not chart.empty:
        colors = [PAL["cyan"] if str(c) in chosen else "rgba(120,150,190,.45)" for c in chart["Team Name"]]
        fig = go.Figure(go.Bar(
            x=chart[metric_col], y=chart["Team Name"], orientation="h", marker=dict(color=colors, line=dict(width=0)),
            customdata=np.stack([chart["Injury_records"], chart["Players_affected"]], axis=-1),
            hovertemplate="<b>%{y}</b><br>" + metric_label + ": %{x:,.2f}<br>%{customdata[0]} records · %{customdata[1]} players<extra></extra>"))
        style_fig(fig, max(300, 90 + 48 * len(chart)))
        fig.update_xaxes(title_text=metric_label)
        show(fig, "cl_rank")
        st.caption("Clubs highlighted in cyan are the ones selected above.")
    else:
        st.info("No usable values for this metric.")

    st.markdown("#### Club statistics")
    stats = cs.rename(columns={"Team Name": "Club"})
    st.dataframe(stats, hide_index=True, **SK_DF)
    st.caption("Club averages are based on injury records in the selected dataset. They are descriptive and are not league-wide performance rankings.")

    with st.expander("What each metric means"):
        for lbl, _col, _dec, doc in available:
            st.markdown(f"**{lbl}** — {doc}")


# ==========================================================
# PAGE: DATA EXPLORER
# ==========================================================

def page_explorer(f, df):
    page_hero(
        "Data workbench · 04", "Explore the", "dataset.",
        "Search, choose columns, sort and export the records currently in view.",
        PAL["amber"], PAL["coral"], "data",
    )

    original_cols = [c for c in f.columns if c not in HELPER_COLS]
    core = [c for c in ["Name", "Team Name", "Position", "Age", "Season", "Injury", "Date of Injury",
                        "Date of return", "Recovery_Days"] if c in f.columns]
    sets = {
        "Core": core,
        "Recovery & ratings": core + [c for c in ["FIFA rating", "Avg_Pre_Injury_Rating", "Avg_Post_Injury_Rating",
                                                  "Performance_Change"] if c in f.columns],
        "Team results": core + [c for c in ["Absence_Matches_Recorded", "Wins_During_Absence", "Points_During_Absence",
                                            "Avg_GD_Before_Injury", "Avg_GD_During_Absence", "Team_Performance_Drop"] if c in f.columns],
        "All columns": original_cols,
    }

    def pick(name):
        st.session_state["explorer_cols"] = sets[name]

    st.session_state.setdefault("explorer_cols", sets["Core"])
    st.session_state["explorer_cols"] = [c for c in st.session_state["explorer_cols"] if c in f.columns] or sets["Core"]

    query = st.text_input("Quick search across player, club and injury",
                          placeholder="Search names, clubs or injury descriptions…", key="ex_query")
    view = f.copy()
    if query.strip():
        searchable = [c for c in ["Name", "Team Name", "Injury", "Injury_Clean", "Position", "Season"] if c in view.columns]
        mask = pd.Series(False, index=view.index)
        for c in searchable:
            mask |= view[c].astype(str).str.contains(query, case=False, na=False, regex=False)
        view = view[mask]

    st.markdown("**Column sets**")
    bcols = st.columns(len(sets))
    for col, name in zip(bcols, sets):
        col.button(name, key=f"colset_{name}", on_click=pick, args=(name,), **SK_BTN)

    shown = st.multiselect("Visible columns", [c for c in f.columns], key="explorer_cols")
    sc1, sc2 = st.columns([2, 1])
    sort_options = ["(none)"] + shown
    if st.session_state.get("ex_sort") not in sort_options:
        st.session_state.pop("ex_sort", None)
    sort_by = sc1.selectbox("Sort by", sort_options, key="ex_sort")
    sort_dir = sc2.radio("Direction", ["Ascending", "Descending"], horizontal=True, key="ex_dir")
    if sort_by != "(none)" and sort_by in view.columns:
        view = view.sort_values(sort_by, ascending=(sort_dir == "Ascending"), na_position="last")

    render(f'<span class="chip c">{len(view):,} records in this view</span><span class="chip">{len(shown)} columns visible</span>')
    if shown:
        st.dataframe(view[shown], hide_index=True, **SK_DF)
    else:
        st.warning("Choose at least one column to display.")

    export_all = view[[c for c in view.columns if c not in HELPER_COLS]]
    d1, d2, _ = st.columns([1, 1, 2])
    with d1:
        st.download_button("Download filtered CSV", export_all.to_csv(index=False).encode("utf-8"),
                           "footlens_filtered_injuries.csv", "text/csv", type="primary", key="dl_all", **SK_DL)
    with d2:
        if shown:
            st.download_button("Download visible columns", view[shown].to_csv(index=False).encode("utf-8"),
                               "footlens_visible_columns.csv", "text/csv", key="dl_visible", **SK_DL)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    section_label("Data quality", "How complete is this view?")
    total_cells = view.shape[0] * view.shape[1]
    missing_cells = int(view.isna().sum().sum())
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Rows", f"{len(view):,}")
    q2.metric("Columns", f"{len(view.columns):,}")
    q3.metric("Missing cells", f"{missing_cells:,}")
    q4.metric("Completeness", f"{100 * (1 - missing_cells / total_cells):.1f}%" if total_cells else "—")

    if len(view):
        miss = view.isna().sum().rename_axis("Column").reset_index(name="Missing")
        miss["Share"] = 100 * miss["Missing"] / len(view)
        miss = miss[miss["Missing"] > 0].sort_values("Missing", ascending=False)
        m1, m2 = st.columns([1.2, 1], gap="large")
        with m1:
            section_label("Missing values", "Columns with the most gaps")
            if not miss.empty:
                top = miss.head(15).sort_values("Missing")
                fig = go.Figure(go.Bar(
                    x=top["Share"], y=top["Column"], orientation="h", customdata=top["Missing"],
                    marker=dict(color=top["Share"], colorscale=[[0, "#3a2a12"], [1, PAL["amber"]]], line=dict(width=0)),
                    hovertemplate="<b>%{y}</b><br>%{x:.1f}% missing (%{customdata} rows)<extra></extra>"))
                style_fig(fig, 430)
                fig.update_xaxes(title_text="Rows missing (%)", range=[0, 100])
                fig.update_yaxes(automargin=True)
                show(fig, "ex_missing")
            else:
                st.success("No missing values in this view.")
        with m2:
            section_label("Missingness pattern", "Gaps across the first 120 rows",
                          "Each column is a field, each row a record; bright cells are missing.")
            if not miss.empty:
                cols_m = miss.head(18)["Column"].tolist()
                sample = view[cols_m].head(120).isna().astype(int)
                fig = go.Figure(go.Heatmap(
                    z=sample.values, x=cols_m, y=list(range(1, len(sample) + 1)), showscale=False,
                    colorscale=[[0, "#0b1630"], [1, PAL["amber"]]], xgap=1, ygap=1,
                    hovertemplate="%{x}<br>row %{y}: %{z}<extra></extra>"))
                style_fig(fig, 430)
                fig.update_yaxes(autorange="reversed", title_text="Row", showticklabels=False)
                fig.update_xaxes(showticklabels=False)
                show(fig, "ex_pattern")
            else:
                st.info("Nothing to plot.")

    section_label("Dataset metadata", "What was loaded")
    dates = f["Date of Injury"].dropna() if "Date of Injury" in f.columns else pd.Series(dtype="datetime64[ns]")
    span = f"{dates.min():%d %b %Y} → {dates.max():%d %b %Y}" if len(dates) else "No injury dates"
    dtype_counts = df[[c for c in df.columns if c not in HELPER_COLS]].dtypes.astype(str).value_counts()
    meta = [("Records loaded", f"{len(df):,}"), ("Fields (original + 2 derived)", f"{len(original_cols):,}"),
            ("Injury-date span", span), ("Seasons", ", ".join(sorted(df["Season"].dropna().astype(str).unique()))),
            ("Field types", " · ".join(f"{k}: {v}" for k, v in dtype_counts.items()))]
    render('<div class="panel flat">' + "".join(
        f'<div style="display:flex;justify-content:space-between;gap:1.5rem;padding:.55rem 0;border-bottom:1px solid rgba(150,180,220,.09)">'
        f'<span class="mono" style="font-size:.66rem;letter-spacing:.12em;color:#8fa3bf;text-transform:uppercase">{esc(k)}</span>'
        f'<span style="color:#eaf3ff;font-size:.86rem;text-align:right">{esc(v)}</span></div>' for k, v in meta) + "</div>")


# ==========================================================
# PAGE: METHODOLOGY
# ==========================================================

def page_method(f, df):
    page_hero(
        "Project notes · 05", "Methodology &", "interpretation.",
        "A transparent guide to every metric and derived field used in FootLens.",
        PAL["cyan"], PAL["violet"], "method",
    )
    cards = [
        ("Unit of analysis", "One row represents one recorded player-injury case. A player may appear more than once."),
        ("Performance change", "Uses the dataset's Performance_Change field, interpreted as average post-injury rating minus average pre-injury rating. Positive values indicate a higher post-injury rating."),
        ("Team performance drop", "Calculated as average goal difference across recorded pre-injury matches minus average goal difference during the player's recorded absence matches. A positive value means average goal difference was lower during absence."),
        ("Missing values and limitations", "Missing values are not replaced with fabricated values. Each chart uses records with the fields needed for that calculation. Results are descriptive associations and do not establish causation."),
        ("Injury names and categories", "Injury text is trimmed, lower-cased and re-capitalised so variants such as “Knee injury” and “knee injury” count together (two obvious typos are also corrected). Categories (muscle, ligament and tendon, bone, illness and so on) come from keyword rules applied to that text. They are a grouping aid, not a medical classification."),
        ("Position groups, age groups and bands", "Position groups combine listed positions (backs → Defender, midfield roles → Midfielder, wingers and centre forwards → Forward). Age groups are ≤21, 22–25, 26–29, 30–33 and 34+. Recovery bands run 1–7, 8–14, 15–28, 29–60, 61–120 and 120+ days."),
        ("Points per absence match", "Points_During_Absence divided by Absence_Matches_Recorded, only where at least one absence match was recorded. This keeps records with one, two or three recorded matches comparable."),
        ("Filters and undated records", "Global filters apply to every page. Records with no injury date stay in the data unless the injury-date range is narrowed; date-based charts simply omit them."),
    ]
    cols = st.columns(2, gap="large")
    for i, (title, copy) in enumerate(cards):
        with cols[i % 2]:
            render(f"""<div class="panel reveal" style="margin-bottom:1rem;--i:{i}"><div style="font:700 1.02rem Manrope;color:#f1f7ff">{esc(title)}</div>
            <div style="color:#98acc6;font-size:.86rem;line-height:1.6;margin-top:.4rem">{esc(copy)}</div></div>""")

    st.markdown("#### Current dataset profile")
    prof = {"Records": int(len(df)), "Unique players": int(df["Name"].nunique()), "Clubs": int(df["Team Name"].nunique()),
            "Seasons": int(df["Season"].nunique()), "Injury categories": int(df["Injury_Clean"].nunique())}
    for col, (label, value) in zip(st.columns(len(prof)), prof.items()):
        col.metric(label, f"{value:,}")
    with st.expander("Available dataset columns"):
        st.write(", ".join(map(str, [c for c in df.columns if c not in HELPER_COLS])))
        st.caption("Derived helper fields used by the interface: " + ", ".join(HELPER_COLS) + ".")


# ==========================================================
# SESSION FLOW
# ==========================================================

inject_css()

st.session_state.setdefault("page", "landing")
st.session_state.setdefault("profile", None)
splash_once()

if st.session_state.page == "landing":
    render_landing()
    st.stop()

if st.session_state.page == "profile":
    render_profile()
    st.stop()

# ---------------- SIDEBAR (identity, navigation, dataset) ----------------

analyst = st.session_state.profile or {"name": "Guest analyst", "role": "Analyst"}
st.session_state.setdefault("nav_page", NAV_ITEMS[0][0])

with st.sidebar:
    render(f"""<div class="brand">{brand_mark(44, "sb")}<div><div class="brand-name">FOOTLENS</div>
        <div class="brand-sub">PERFORMANCE INTELLIGENCE</div></div></div>
        <div class="analyst">{avatar_svg(analyst["name"], 42)}<div><b>{esc(analyst["name"])}</b><span>{esc(analyst["role"])}</span></div></div>
        <div class="side-label">Navigate</div>""")
    page = st.radio("Workspace", [n for n, _ in NAV_ITEMS], key="nav_page", label_visibility="collapsed")
    status_slot = st.empty()
    filters_slot = st.container()
    render('<div class="side-label">Dataset</div>')
    uploaded = st.file_uploader("Replace / upload dataset", type=["csv"])

skeleton_slot = st.empty()
if not st.session_state.get("_ds_seen"):
    skeleton_slot.markdown(H(skeleton_block()), unsafe_allow_html=True)
try:
    df = load_dataset(uploaded.getvalue() if uploaded is not None else None)
    st.session_state["_ds_seen"] = True
except FileNotFoundError:
    skeleton_slot.empty()
    st.error("Dataset not found. Place footlens_cleaned_injuries.csv beside app.py or upload it in the sidebar.")
    st.stop()
except Exception as exc:
    skeleton_slot.empty()
    st.error(f"Could not load the dataset: {exc}")
    st.stop()
skeleton_slot.empty()

required = ["Name", "Team Name", "Position", "Age", "Season", "Injury"]
missing = [c for c in required if c not in df.columns]
if missing:
    st.error("Missing required columns: " + ", ".join(missing))
    st.stop()

# ---------------- GLOBAL FILTERS ----------------

FILTER_KEYS = ["filter_Team Name", "filter_Season", "filter_Position", "filter_Injury", "age_filter", "date_filter"]


def reset_filters():
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)


def sign_out():
    st.session_state.page = "landing"
    st.session_state.profile = None


with filters_slot:
    ctl_slot = st.empty()
    ctl_flags = []

    def multi_filter(label, col, key):
        options = sorted(df[col].dropna().astype(str).unique().tolist())
        picked = safe_multiselect(label, options, key)
        ctl_flags.append(len(picked) < len(options))
        return picked

    clubs = multi_filter("Club", "Team Name", "filter_Team Name")
    seasons = multi_filter("Season", "Season", "filter_Season")
    positions = multi_filter("Position", "Position", "filter_Position")
    injuries = multi_filter("Injury", "Injury_Clean", "filter_Injury")

    age_values = pd.to_numeric(df["Age"], errors="coerce").dropna()
    age_range = None
    if not age_values.empty:
        amin, amax = int(age_values.min()), int(age_values.max())
        if amin < amax:
            age_range = st.slider("Age range", amin, amax, (amin, amax), key="age_filter")
            ctl_flags.append(tuple(age_range) != (amin, amax))
        else:
            age_range = (amin, amax)

    date_range = None
    date_full = None
    if "Date of Injury" in df.columns and df["Date of Injury"].notna().any():
        dts = df["Date of Injury"].dropna()
        dmin, dmax = dts.min().date(), dts.max().date()
        date_full = (dmin, dmax)
        selected_dates = st.date_input("Injury date range", value=(dmin, dmax), min_value=dmin, max_value=dmax,
                                       key="date_filter")
        if isinstance(selected_dates, (tuple, list)) and len(selected_dates) == 2:
            date_range = selected_dates
        ctl_flags.append(date_range is not None and (date_range[0] > dmin or date_range[1] < dmax))

    ctl_slot.markdown(H(filter_panel_header(ctl_flags)), unsafe_allow_html=True)

    st.button("Reset filters", key="reset_filters", on_click=reset_filters, **SK_BTN)
    st.button("Sign out / return to start", key="sign_out", on_click=sign_out, **SK_BTN)

# ---------------- APPLY FILTERS ----------------

filtered = df[
    df["Team Name"].astype(str).isin(clubs)
    & df["Season"].astype(str).isin(seasons)
    & df["Position"].astype(str).isin(positions)
    & df["Injury_Clean"].astype(str).isin(injuries)
].copy()

if age_range is not None:
    filtered = filtered[pd.to_numeric(filtered["Age"], errors="coerce").between(age_range[0], age_range[1])]

if date_range is not None and "Date of Injury" in filtered.columns:
    narrowed = date_full is not None and (date_range[0] > date_full[0] or date_range[1] < date_full[1])
    in_range = filtered["Date of Injury"].dt.date.between(date_range[0], date_range[1])
    if KEEP_UNDATED_RECORDS and not narrowed:
        in_range = in_range | filtered["Date of Injury"].isna()
    filtered = filtered[in_range]

# ---------------- SIDEBAR STATUS + HEADER ----------------

started = st.session_state.get("session_start")
since = f"Session since {started:%H:%M}" if started else "Session active"
source = "Uploaded file" if uploaded is not None else "footlens_cleaned_injuries.csv"
status_slot.markdown(H(f"""
    <div class="status"><div class="dot"></div><div><b>Dataset ready</b>
    <span>{len(filtered):,} of {len(df):,} records · {esc(since)}</span></div></div>
    <div class="mono" style="font-size:.58rem;color:#566c88;margin:.4rem .2rem 0;letter-spacing:.08em">SOURCE · {esc(source)}</div>"""),
    unsafe_allow_html=True)

narrowed_bits = []
if len(clubs) < df["Team Name"].nunique():
    narrowed_bits.append(f"{len(clubs)} club(s)")
if len(seasons) < df["Season"].nunique():
    narrowed_bits.append(f"{len(seasons)} season(s)")
if len(positions) < df["Position"].nunique():
    narrowed_bits.append(f"{len(positions)} position(s)")
if len(injuries) < df["Injury_Clean"].nunique():
    narrowed_bits.append(f"{len(injuries)} injury type(s)")
if age_range is not None and (age_range[0] > int(age_values.min()) or age_range[1] < int(age_values.max())):
    narrowed_bits.append(f"age {age_range[0]}–{age_range[1]}")
if date_range is not None and date_full is not None and (date_range[0] > date_full[0] or date_range[1] < date_full[1]):
    narrowed_bits.append("date range")
chips = "".join(f'<span class="chip v">{esc(b)}</span>' for b in narrowed_bits) or '<span class="chip">No filters narrowing the data</span>'
render(f"""<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.6rem;margin-bottom:1rem">
    <div><span class="chip c">Showing {len(filtered):,} of {len(df):,} records</span>{chips}</div>
    <div class="mono" style="font-size:.64rem;letter-spacing:.14em;color:#8fa3bf">ANALYST · <b style="color:#2ef2a0;font-weight:500">{esc(analyst["name"]).upper()}</b></div></div>""")

if filtered.empty:
    st.warning("No records match the selected filters. Widen a filter or use Reset filters in the sidebar.")
    st.stop()

# ---------------- ROUTER ----------------

PAGES = {
    "Command Centre": page_command,
    "Injury Intelligence": page_injury,
    "Player Recovery Lab": page_player,
    "Club Comparison Studio": page_clubs,
    "Data Explorer": page_explorer,
    "Methodology": page_method,
}
PAGES[page](filtered, df)
site_footer()