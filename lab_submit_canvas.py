"""
lab_submit_canvas.py
====================
Drop-in replacement for lab_submit.py that adds Canvas API grade passback
as a fourth write target, plus a submit_quiz() function for quiz-only notebooks.

ORIGINAL targets are preserved exactly:
  1. Google Sheets  — via service account  (silent if not configured)
  2. Shared JSON    — /home/jovyan/shared-public/submissions.json
  3. Home fallback  — ~/submissions_local.json

NEW target (4th, tried after the others):
  4. Canvas Grades API — PUT score to the Canvas gradebook

TESTING / SWITCHOVER STRATEGY
──────────────────────────────
Set CANVAS_TEST_MODE = True  → Canvas call is logged but never sent.
                               All other targets still write normally.
Set CANVAS_TEST_MODE = False → Live Canvas write on submit.

To switch a lab from the old submit to the Canvas version:
  1. Copy this file into the lab directory as lab_submit_canvas.py
  2. Update the notebook import line:
       from lab_submit_canvas import submit_lab, submit_quiz
  3. Leave lab_submit.py untouched in the parent directory.

CANVAS SETUP
────────────
Store a JSON config file at CANVAS_CONFIG_PATH:

  {
    "api_url":   "https://temple.instructure.com",
    "api_token": "YOUR_INSTRUCTOR_TOKEN",
    "course_id": 12345
  }

Then map each LAB_ID to a Canvas assignment ID in CANVAS_ASSIGNMENT_IDS below.
Leave a lab out of the map to skip Canvas write for that lab (silent).

QUIZ NOTEBOOK USAGE
────────────────────
Quiz notebooks have no gofer checks — the score comes from jupyterquiz responses.
Call submit_quiz() instead of submit_lab():

    from lab_submit_canvas import submit_quiz
    submit_quiz(name, user, quiz_score, quiz_total, quiz_id="Quiz01")

quiz_score and quiz_total are integers you pass in after reading them from
the jupyterquiz widget state or your own tracking variable.
"""

import json, os, re, glob, time, fcntl
import ipywidgets as widgets
from IPython.display import display, clear_output

# ── per-lab configuration ──────────────────────────────────────────────────────

LAB_ID = "Lab03"      # ← change this for each lab copy

# ── original write targets (unchanged from lab_submit.py) ─────────────────────

FALLBACK_JSON = os.path.expanduser("~/submissions_local.json")
SHEET_ID      = "1JTlIyJCAGE7obspq04ERJkQHOku_d8jZn1sxmIedWJU"
SHARED_JSON   = "/home/jovyan/shared-public/submissions.json"   # student data — shared-public confirmed writable

# ⚠️ CREDS_PATH holds a Google service-account KEY, not student data. shared-public
# being writable-by-students does not necessarily mean it's also world-*readable* —
# but that has NOT been confirmed. Do not leave a live credential file here until
# someone has verified students cannot read this directory's contents. If in doubt,
# use a path outside any shared/student-writable directory entirely (e.g. an
# instructor-only home directory or a Hub secrets mechanism), and set this to that
# path instead.
CREDS_PATH    = "/home/jovyan/shared-readwrite/nordic-knowledge-6598a7fdb7c8.json"  # UNVERIFIED — see warning above

# ── Canvas configuration ───────────────────────────────────────────────────────

# Path to JSON file containing api_url, api_token, course_id.
# ⚠️ Same warning as CREDS_PATH above: this holds a live Canvas API TOKEN.
# "shared-readwrite" was the old (broken/unwritable) path — but simply swapping it
# for shared-public is NOT safe for a credential file unless shared-public is also
# confirmed to block student read access. Verify before deploying; consider an
# instructor-only location instead if shared-public is broadly readable.
CANVAS_CONFIG_PATH = "/home/jovyan/shared-readwrite/canvas_config.json"  # UNVERIFIED — see warning above

# Map LAB_ID / quiz_id strings → Canvas assignment ID (integer).
# Find assignment IDs in the Canvas URL when editing an assignment:
#   .../courses/12345/assignments/>>67890<<
# Leave a lab out of this dict to skip Canvas write for it (no error).
CANVAS_ASSIGNMENT_IDS = {
    "Lab01": None,   # ← fill in once assignments are created in Canvas
    "Lab02": None,
    "Lab03": None,
    "Lab04": None,
    "Lab05": None,
    "Quiz01": None,
    "Quiz02": None,
    "Quiz03": None,
    "CA_Quiz1_CodingPolicies": None,
    "CA_Quiz2_StatsTeaching": None,
}

# ── TEST MODE ─────────────────────────────────────────────────────────────────
# True  → Canvas API call is printed but NOT sent. Safe for testing.
# False → Live write to Canvas gradebook on every submit click.
CANVAS_TEST_MODE = True

# ── Canvas helpers ─────────────────────────────────────────────────────────────

def _load_canvas_config():
    """
    Load Canvas API credentials from the shared config file.
    Returns (config_dict, "") on success or (None, error_message) on failure.
    Silent if the config file simply doesn't exist.
    """
    if not os.path.exists(CANVAS_CONFIG_PATH):
        return None, f"Canvas config not found: {CANVAS_CONFIG_PATH}"
    try:
        with open(CANVAS_CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        required = {"api_url", "api_token", "course_id"}
        missing  = required - set(cfg)
        if missing:
            return None, f"Canvas config missing keys: {missing}"
        return cfg, ""
    except Exception as e:
        return None, f"Canvas config read error: {e}"


def _post_grade_to_canvas(user, score_pct, assignment_id, cfg, test_mode):
    """
    PUT a score (0–100) for `user` to the Canvas Grades API.

    Canvas accepts a score as a raw number; we pass the percentage directly
    and set the assignment's points_possible to 100 in Canvas so it maps 1:1.

    Returns (True, info_message) or (False, error_message).
    """
    try:
        import urllib.request, urllib.error
    except ImportError:
        return False, "urllib not available (should never happen)"

    url = (f"{cfg['api_url'].rstrip('/')}/api/v1/courses/{cfg['course_id']}"
           f"/assignments/{assignment_id}/submissions/{user}")

    payload = json.dumps({
        "submission": {"posted_grade": f"{score_pct:.1f}%"}
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {cfg['api_token']}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }

    if test_mode:
        msg = (f"[TEST MODE — not sent]\n"
               f"  PUT {url}\n"
               f"  Body: posted_grade={score_pct:.1f}%")
        return True, msg

    req = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            body   = resp.read().decode("utf-8", errors="replace")[:200]
            if status in (200, 201):
                return True, f"Canvas grade written ({status})"
            else:
                return False, f"Canvas API returned status {status}: {body}"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        return False, f"Canvas HTTP {e.code}: {body}"
    except urllib.error.URLError as e:
        return False, f"Canvas URL error: {e.reason}"
    except Exception as e:
        return False, f"Canvas error: {e}"


def _submit_to_canvas(user, score_pct, item_id):
    """
    Orchestrate Canvas grade write.
    Returns (destination_label, warning_message_or_None).
    """
    assignment_id = CANVAS_ASSIGNMENT_IDS.get(item_id)
    if not assignment_id:
        return None, None   # not configured for this lab — skip silently

    cfg, cfg_err = _load_canvas_config()
    if cfg is None:
        return None, f"Canvas config error: {cfg_err}"

    ok, msg = _post_grade_to_canvas(user, score_pct, assignment_id, cfg,
                                     CANVAS_TEST_MODE)
    if ok:
        label = f"Canvas {'[TEST]' if CANVAS_TEST_MODE else 'Gradebook'}"
        return label, msg if CANVAS_TEST_MODE else None
    else:
        return None, f"Canvas write failed: {msg}"


# ── original helpers (copied verbatim from lab_submit.py) ─────────────────────

def _find_notebook():
    nbs = glob.glob("*.ipynb")
    return max(nbs, key=os.path.getmtime) if nbs else None


def _extract_open_ended(nb_path):
    answers = {}
    debug   = []
    try:
        import nbformat as nbf
        ntbk  = nbf.read(nb_path, nbf.NO_CONVERT)
        cells = ntbk.cells
        debug.append(f"nbformat read OK — {len(cells)} cells")
    except Exception as e:
        debug.append(f"nbformat failed ({e}), falling back to json.load")
        try:
            with open(nb_path, encoding="utf-8") as f:
                raw = json.load(f)
            class _Cell:
                def __init__(self, d):
                    self.cell_type = d.get("cell_type", "")
                    src = d.get("source", [])
                    self.source = src if isinstance(src, str) else "".join(src)
            cells = [_Cell(c) for c in raw.get("cells", [])]
            debug.append(f"json.load fallback OK — {len(cells)} cells")
        except Exception as e2:
            debug.append(f"json.load also failed: {e2}")
            return answers, debug

    for i, cell in enumerate(cells):
        if cell.cell_type != "code":
            continue
        src = cell.source if isinstance(cell.source, str) else "".join(cell.source)
        m = re.search(r'check\s*\(\s*["\']tests/q([^"\']+_open_ended)\.py["\']', src)
        if not m:
            continue
        q_id = m.group(1)
        debug.append(f"Found check cell for q{q_id} at cell index {i}")
        found = False
        for j in range(i - 1, max(i - 7, -1), -1):
            c = cells[j]
            if c.cell_type == "markdown":
                text = c.source if isinstance(c.source, str) else "".join(c.source)
                answers[q_id] = text.strip()
                debug.append(f"  → captured cell {j}: {text.strip()[:80]!r}")
                found = True
                break
        if not found:
            debug.append(f"  → no markdown cell found within 6 cells above")
    return answers, debug


def _atomic_append_json(path, record):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    lock_path = path + ".lock"
    with open(lock_path, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    data = [data]
            else:
                data = []
            data.append(record)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, path)
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _flatten_record(record):
    flat = {k: v for k, v in record.items() if k != "answers"}
    for i, (q_id, text) in enumerate(record.get("answers", {}).items(), start=1):
        flat[f"open{i}_label"] = q_id
        flat[f"open{i}"]       = text
    return flat


def _append_to_sheet(record, sheet_id, creds_path):
    try:
        import gspread
    except ImportError:
        return False, "gspread not installed"
    if not os.path.exists(creds_path):
        return False, f"Credentials file not found: {creds_path}"
    try:
        try:
            gc = gspread.service_account(filename=creds_path)
        except AttributeError:
            from google.oauth2.service_account import Credentials
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds  = Credentials.from_service_account_file(creds_path, scopes=scopes)
            gc     = gspread.authorize(creds)
        ws   = gc.open_by_key(sheet_id).sheet1
        flat = _flatten_record(record)
        existing_headers = ws.row_values(1)
        if not existing_headers:
            ws.append_row(list(flat.keys()), value_input_option="RAW")
            ws.append_row(list(flat.values()), value_input_option="USER_ENTERED")
        else:
            new_cols = [k for k in flat if k not in existing_headers]
            if new_cols:
                updated_headers = existing_headers + new_cols
                ws.update(range_name="A1", values=[updated_headers])
            else:
                updated_headers = existing_headers
            row = [flat.get(col, "") for col in updated_headers]
            ws.append_row(row, value_input_option="USER_ENTERED")
        return True, ""
    except Exception as e:
        return False, str(e)


# ── shared submission core ─────────────────────────────────────────────────────

def _build_and_fire_button(label, button_style, on_click_fn, score_line):
    """Render score summary + button; wire up on_click_fn."""
    print(score_line)
    btn = widgets.Button(
        description=label,
        button_style=button_style,
        icon="check",
        layout=widgets.Layout(width="200px", height="40px"),
        style={"font_weight": "bold"},
    )
    out = widgets.Output()
    btn.on_click(lambda b: on_click_fn(b, out))
    display(widgets.VBox([btn, out]))


def _write_all_targets(record, item_id, perc_correct, out_widget):
    """
    Write record to all configured targets; print results inside out_widget.
    Returns list of destination labels.
    """
    destinations = []

    # 1. Google Sheets
    if SHEET_ID:
        ok, sheet_err = _append_to_sheet(record, SHEET_ID, CREDS_PATH)
        if ok:
            destinations.append("Google Sheets")
        else:
            print(f"  ⚠️  Google Sheets write failed: {sheet_err}")

    # 2 & 3. Shared JSON with home fallback
    try:
        _atomic_append_json(SHARED_JSON, record)
        destinations.append(SHARED_JSON)
    except (PermissionError, OSError):
        _atomic_append_json(FALLBACK_JSON, record)
        destinations.append(FALLBACK_JSON)

    # 4. Canvas Grades API
    canvas_dest, canvas_note = _submit_to_canvas(
        record["user"], perc_correct, item_id)
    if canvas_dest:
        destinations.append(canvas_dest)
        if canvas_note:           # test-mode message
            print(f"  🧪 {canvas_note}")
    elif canvas_note:             # warning / error
        print(f"  ⚠️  {canvas_note}")

    return destinations


# ── public API: submit_lab ────────────────────────────────────────────────────

def submit_lab(name, user, correct, questions, lab_id=LAB_ID):
    """
    Drop-in replacement for lab_submit.submit_lab().
    Identical call signature — just change the import line in the notebook.

        from lab_submit_canvas import submit_lab
        submit_lab(name, user, correct, questions)
    """
    perc_correct = correct / len(questions) * 100
    msg = "nice work!" if perc_correct >= 80 else "look over your work again, seek help, some errors!!!"

    print(f"----\n{name} {msg}\n----\nusername: {user}")
    score_line = f"Score: {perc_correct:.1f}%  ({correct}/{len(questions)})"

    canvas_status = (
        "🧪 Canvas TEST MODE — grade will be logged but not sent"
        if CANVAS_TEST_MODE else
        "📡 Canvas grade passback LIVE"
    )
    print(score_line)
    print(canvas_status)

    btn = widgets.Button(
        description="Submit Lab",
        button_style="success",
        icon="check",
        layout=widgets.Layout(width="200px", height="40px"),
        style={"font_weight": "bold"},
    )
    out = widgets.Output()

    def _on_click(b):
        b.disabled = True
        with out:
            clear_output(wait=True)
            try:
                from IPython.display import Javascript
                display(Javascript("""
                    (function() {
                        try { IPython.notebook.save_checkpoint(); } catch(e) {}
                        try { window.jupyterapp.commands.execute('docmanager:save'); } catch(e) {}
                    })();
                """))
                print("💾  Saving notebook…")
                time.sleep(2)
                clear_output(wait=True)

                nb_path   = _find_notebook()
                localtime = time.asctime(time.localtime(time.time()))

                if nb_path:
                    answers, debug = _extract_open_ended(nb_path)
                else:
                    answers, debug = {}, ["No .ipynb found in current directory"]

                record = {
                    "lab":       lab_id,
                    "name":      name,
                    "user":      user,
                    "timestamp": localtime,
                    "score_pct": round(perc_correct, 1),
                    "correct":   correct,
                    "total":     len(questions),
                    "notebook":  nb_path or "unknown",
                    "answers":   answers,
                }

                destinations = _write_all_targets(record, lab_id, perc_correct, out)

                b.description  = "Submitted ✓"
                b.button_style = "info"

                print(f"✅  Submitted {lab_id} for {name}")
                print(f"    Time     : {localtime}")
                print(f"    Score    : {perc_correct:.1f}%  ({correct}/{len(questions)})")
                print(f"    Answers  : {len(answers)} open-ended response(s) captured")
                print(f"    Saved    : {', '.join(destinations)}")

                if not answers:
                    print("\n  ⚠️  No open-ended answers captured.")
                    print("     Uncomment the debug lines in lab_submit_canvas.py")
                    print("     to diagnose, then resubmit.")

            except Exception as e:
                b.disabled     = False
                b.button_style = "danger"
                print(f"❌  Submission failed: {e}")

    btn.on_click(_on_click)
    display(widgets.VBox([btn, out]))


# ── public API: submit_quiz ───────────────────────────────────────────────────

def submit_quiz(name, user, quiz_score, quiz_total, quiz_id="Quiz01"):
    """
    Submit function for quiz-only notebooks (no gofer checks).
    The score is passed in directly — read it from your quiz tracking variable.

    Typical quiz notebook final cell:
    ──────────────────────────────────
        from lab_submit_canvas import submit_quiz

        # quiz_score and quiz_total come from your score-tracking cell:
        #   quiz_score = 7   # student got 7 right
        #   quiz_total = 10  # out of 10
        submit_quiz(name, user, quiz_score, quiz_total, quiz_id="Quiz03")
    ──────────────────────────────────

    The record written to all targets looks identical to a lab submission
    except:
      - "lab" field is set to quiz_id
      - "answers" is empty (quizzes have no open-ended responses)
      - button label says "Submit Quiz" instead of "Submit Lab"
    """
    if quiz_total == 0:
        print("❌  quiz_total is 0 — cannot compute score.")
        return

    perc_correct = quiz_score / quiz_total * 100
    msg = "great score!" if perc_correct >= 80 else "review the material and try the quiz again!"

    print(f"----\n{name} — {msg}\n----\nusername: {user}")
    print(f"Quiz score: {perc_correct:.1f}%  ({quiz_score}/{quiz_total})")

    canvas_status = (
        "🧪 Canvas TEST MODE — grade will be logged but not sent"
        if CANVAS_TEST_MODE else
        "📡 Canvas grade passback LIVE"
    )
    print(canvas_status)

    btn = widgets.Button(
        description="Submit Quiz",
        button_style="warning",      # orange — visually distinct from lab button
        icon="check",
        layout=widgets.Layout(width="200px", height="40px"),
        style={"font_weight": "bold"},
    )
    out = widgets.Output()

    def _on_click(b):
        b.disabled = True
        with out:
            clear_output(wait=True)
            try:
                from IPython.display import Javascript
                display(Javascript("""
                    (function() {
                        try { IPython.notebook.save_checkpoint(); } catch(e) {}
                        try { window.jupyterapp.commands.execute('docmanager:save'); } catch(e) {}
                    })();
                """))
                print("💾  Saving notebook…")
                time.sleep(2)
                clear_output(wait=True)

                nb_path   = _find_notebook()
                localtime = time.asctime(time.localtime(time.time()))

                record = {
                    "lab":       quiz_id,
                    "name":      name,
                    "user":      user,
                    "timestamp": localtime,
                    "score_pct": round(perc_correct, 1),
                    "correct":   quiz_score,
                    "total":     quiz_total,
                    "notebook":  nb_path or "unknown",
                    "answers":   {},          # quizzes have no open-ended responses
                }

                destinations = _write_all_targets(record, quiz_id, perc_correct, out)

                b.description  = "Submitted ✓"
                b.button_style = "info"

                print(f"✅  Submitted {quiz_id} for {name}")
                print(f"    Time     : {localtime}")
                print(f"    Score    : {perc_correct:.1f}%  ({quiz_score}/{quiz_total})")
                print(f"    Saved    : {', '.join(destinations)}")

            except Exception as e:
                b.disabled     = False
                b.button_style = "danger"
                print(f"❌  Submission failed: {e}")

    btn.on_click(_on_click)
    display(widgets.VBox([btn, out]))
