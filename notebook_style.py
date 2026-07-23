"""
notebook_style.py
-----------------
Drop this file in your course repo (alongside your notebooks, or inside EDS_mod/).
Students never need to see or edit it — just call apply_style() at the top of any notebook.

Usage in a notebook cell:
    from notebook_style import apply_style
    apply_style()
"""

from IPython.display import HTML, display

# ---------------------------------------------------------------------------
# Default theme
# ---------------------------------------------------------------------------
_DEFAULT = dict(
    body_color   = "#1a3a5c",   # deep navy  — body text
    h1_color     = "#c0392b",   # red        — main title
    h2_color     = "#1a6e2e",   # forest green — section headings
    h3_color     = "#7d3c98",   # purple     — sub-headings
    body_size    = 18,          # px — markdown prose
    code_size    = 16,          # px — code cells
    question_bg  = "#eaf4fb",
    question_border = "#2980b9",
)

# ---------------------------------------------------------------------------
# Optional named themes (pass theme="name" to apply_style)
# ---------------------------------------------------------------------------
_THEMES = {
    "default": _DEFAULT,
    "dark_academia": dict(
        body_color="#d4c5a9", h1_color="#c9a84c", h2_color="#8fbc8f",
        h3_color="#cd853f", body_size=18, code_size=16,
        question_bg="#2c2c2c", question_border="#c9a84c",
    ),
    "ocean": dict(
        body_color="#003153", h1_color="#0077b6", h2_color="#00b4d8",
        h3_color="#48cae4", body_size=18, code_size=16,
        question_bg="#caf0f8", question_border="#0077b6",
    ),
    "high_contrast": dict(
        body_color="#000000", h1_color="#cc0000", h2_color="#006600",
        h3_color="#000099", body_size=20, code_size=18,
        question_bg="#ffffe0", question_border="#cc0000",
    ),
}


def apply_style(theme: str = "default", **overrides):
    """
    Inject custom CSS into the running Jupyter notebook.

    Parameters
    ----------
    theme : str
        One of "default", "dark_academia", "ocean", "high_contrast".
    **overrides : keyword arguments
        Any key from the theme dict can be overridden, e.g.
            apply_style(h1_color="#ff6600", body_size=20)
    """
    if theme not in _THEMES:
        raise ValueError(f"Unknown theme '{theme}'. Choose from: {list(_THEMES)}")

    cfg = {**_THEMES[theme], **overrides}   # merge theme + any per-call overrides

    css = f"""
<style>
  /* ── Body / prose text ─────────────────────────────────────── */
  body,
  .jp-RenderedHTMLCommon,
  .cell-output {{
    font-size: {cfg['body_size']}px !important;
  }}
  .jp-RenderedHTMLCommon p,
  .jp-RenderedHTMLCommon li {{
    font-size: {cfg['body_size']}px;
    color: {cfg['body_color']};
  }}

  /* ── Headings ───────────────────────────────────────────────── */
  .jp-RenderedHTMLCommon h1 {{
    font-size: 2.2em;
    color: {cfg['h1_color']};
  }}
  .jp-RenderedHTMLCommon h2 {{
    font-size: 1.8em;
    color: {cfg['h2_color']};
  }}
  .jp-RenderedHTMLCommon h3 {{
    font-size: 1.4em;
    color: {cfg['h3_color']};
  }}

  /* ── Code cells ─────────────────────────────────────────────── */
  .CodeMirror,
  .jp-CodeMirrorEditor .cm-editor {{
    font-size: {cfg['code_size']}px !important;
  }}

  /* ── Question callout box ───────────────────────────────────── */
  .question-box {{
    background: {cfg['question_bg']};
    border-left: 6px solid {cfg['question_border']};
    padding: 12px 16px;
    border-radius: 4px;
    margin: 10px 0;
    font-size: {cfg['body_size']}px;
  }}
</style>
"""
    display(HTML(css))
    print(f"✅ Notebook styled with theme='{theme}'.")


def list_themes():
    """Print available theme names."""
    print("Available themes:", list(_THEMES))
