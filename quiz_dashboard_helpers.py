"""
quiz_dashboard_helpers.py
=========================
Back-end logic for quiz_instructor_dashboard.ipynb.
Instructors never need to edit this file.
"""
import json, os, glob, csv, io, re
from datetime import datetime

ATTEMPTS_DIR  = "/home/jovyan/shared-public/quiz_attempts"
SUBMISSIONS   = "/home/jovyan/shared-public/submissions.json"

# ── data loading ──────────────────────────────────────────────────────────────

def list_quiz_ids():
    """Return sorted list of unique quiz IDs found in attempt files."""
    files = glob.glob(os.path.join(ATTEMPTS_DIR, "*.json"))
    ids = set()
    for f in files:
        base = os.path.basename(f)
        # match user_QuizXX.json  (not _state.json)
        m = re.match(r".+?_(.+?)(?:_state)?\.json$", base)
        if m:
            ids.add(m.group(1))
    return sorted(ids)


def load_quiz_attempts(quiz_id):
    """
    Load all attempt records for a given quiz_id.
    Returns list of dicts with keys:
        user, name, opened_at, score, total, pct_str, has_score
    """
    pattern = os.path.join(ATTEMPTS_DIR, f"*_{quiz_id}.json")
    open_files = glob.glob(pattern)
    results = []

    for path in open_files:
        base = os.path.basename(path)
        # user is everything before the last _QuizXX
        user = base[: base.rfind(f"_{quiz_id}")]
        try:
            with open(path) as f:
                rec = json.load(f)
        except Exception:
            continue

        # Try to get score from state file
        state_path = os.path.join(ATTEMPTS_DIR, f"{user}_{quiz_id}_state.json")
        score, total, has_score = None, None, False
        if os.path.exists(state_path):
            try:
                with open(state_path) as f:
                    state = json.load(f)
                score     = state.get("score")
                total     = state.get("total")
                has_score = (score is not None and total is not None)
            except Exception:
                pass

        # Also check submissions.json for submitted score
        submitted_score = _find_submission_score(user, quiz_id)
        if submitted_score is not None:
            score, total, has_score = submitted_score["correct"], submitted_score["total"], True

        pct_str = f"{score/total*100:.0f}%" if has_score and total else "—"

        results.append({
            "user":       user,
            "name":       rec.get("name", ""),
            "opened_at":  rec.get("timestamp", ""),
            "score":      score,
            "total":      total,
            "pct_str":    pct_str,
            "has_score":  has_score,
        })

    results.sort(key=lambda r: r["user"])
    return results


def _find_submission_score(user, quiz_id):
    """Check submissions.json for a submitted score for this user+quiz."""
    if not os.path.exists(SUBMISSIONS):
        return None
    try:
        with open(SUBMISSIONS) as f:
            subs = json.load(f)
        # Most recent submission wins
        matches = [s for s in subs
                   if s.get("user") == user and s.get("lab") == quiz_id]
        if matches:
            return sorted(matches, key=lambda s: s.get("timestamp",""))[-1]
    except Exception:
        pass
    return None


def load_canvas_roster(csv_text):
    """
    Parse a Canvas gradebook CSV export.
    Returns (list_of_student_dicts, list_of_column_names).
    Student dict keys include: Student, ID, SIS_Login_ID, Section, + assignment cols.
    Canvas puts 4 junk rows at the top — we find the real header row automatically.
    """
    lines = csv_text.splitlines()
    # Find the header row — contains "Student" and "SIS Login ID"
    header_idx = None
    for i, line in enumerate(lines):
        if "Student" in line and "SIS Login ID" in line:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("Could not find Canvas gradebook header row. "
                         "Expected columns: Student, SIS Login ID")

    reader = csv.DictReader(lines[header_idx:])
    students = []
    for row in reader:
        # Skip the two Canvas meta-rows ("    Points Possible", "Student, Test")
        name = row.get("Student", "").strip()
        if not name or name.startswith("    ") or name == "Student, Test":
            continue
        # Normalise key: remove spaces
        sis = row.get("SIS Login ID", "").strip().lower()
        if not sis:
            continue
        students.append({
            "Student":      name,
            "ID":           row.get("ID", "").strip(),
            "SIS_Login_ID": sis,
            "Section":      row.get("Section", "").strip(),
            "_raw":         dict(row),
        })
    cols = list(reader.fieldnames) if reader.fieldnames else []
    return students, cols


def match_scores_to_roster(students, attempts, quiz_id, points_possible=10):
    """
    Left-join roster → attempts on SIS_Login_ID == user.
    Returns list of result dicts for CSV export.
    """
    attempt_map = {a["user"].lower(): a for a in attempts}
    rows = []
    for s in students:
        sis   = s["SIS_Login_ID"]
        match = attempt_map.get(sis)
        if match and match["has_score"]:
            raw_score = match["score"]
            # Scale to points_possible
            pts = round(raw_score / match["total"] * points_possible, 1) if match["total"] else 0
        else:
            pts = ""   # blank = not submitted in Canvas
        rows.append({
            "Student":      s["Student"],
            "ID":           s["ID"],
            "SIS Login ID": s["SIS_Login_ID"],
            "Section":      s["Section"],
            quiz_id:        pts,
        })
    return rows


def export_canvas_csv(rows, quiz_id):
    """Serialise matched rows to a Canvas-compatible CSV string."""
    if not rows:
        return ""
    fieldnames = ["Student", "ID", "SIS Login ID", "Section", quiz_id]
    buf = io.StringIO()
    w   = csv.DictWriter(buf, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def not_attempted(students, attempts):
    """Return students from the roster who have no attempt record."""
    attempted_users = {a["user"].lower() for a in attempts}
    return [s for s in students if s["SIS_Login_ID"] not in attempted_users]
