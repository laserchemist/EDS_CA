# EDS_CA

Course Assistant / STEM Leadership Fellow materials for Elements of Data Science (SCTC 1013).

Everything lives flat at the repo root (no subfolders) — this matches what nbgitpuller needs to
resolve paths cleanly, and is simpler to keep in sync with the Hub.

## Contents

- `index.html` — the CA/Fellow manual (policies, coding review, data wrangling, statistics,
  strategies for success, teaching foundations, cheat sheet, video library, test-yourself).
  Served as the site's home page via GitHub Pages. **This is the file GitHub Pages actually
  serves** — if `EDS_CA_Manual.html` still exists alongside it, that's a leftover duplicate, not
  the live copy; edit `index.html`, or delete the duplicate to avoid the two drifting apart.
- `stemds_quiz.py` — the quiz widget/lockout engine. Must be importable from wherever the quiz
  notebooks run — since everything's flat at repo root, that's automatic once the repo is pulled.
- `questions_quiz1_coding_policies.json` — 50-question bank for Quiz 1 (Policies, Coding Review,
  Data Wrangling).
- `questions_quiz2_stats_teaching.json` — 50-question bank for Quiz 2 (Statistics, Strategies
  for Success, Teaching Foundations).
- `Quiz1_Coding_Wrangling_Policies.ipynb` / `Quiz2_Statistics_Teaching.ipynb` — the two quiz
  notebooks. Each draws 30 of 50 questions at random and allows **3 attempts at the whole
  quiz** (a fresh 30-question subset each attempt, not the same set repeated).
- `lab05_init.py` — shared init module the quiz notebooks import (`from lab05_init import *`).

## Viewing the manual

Live site: `https://laserchemist.github.io/EDS_CA/`

## nbgitpuller links (in the manual's "Test Yourself" section)

Because everything is flat at repo root, notebook links target `EDS_CA/<filename>.ipynb`
directly — **not** a subfolder. E.g.:

```
https://temple.2i2c.cloud/hub/user-redirect/git-pull?repo=https%3A%2F%2Fgithub.com%2Flaserchemist%2FEDS_CA&urlpath=lab%2Ftree%2FEDS_CA%2FQuiz1_Coding_Wrangling_Policies.ipynb&branch=main
```

If you ever reorganize files into subfolders, every nbgitpuller `urlpath=` in `index.html`'s
"Test Yourself" section needs the matching subfolder inserted, or the links will 404 with
"Could not find path" even though the pull itself succeeded.

## Important: shared-public, not shared-readwrite

`stemds_quiz.py`'s `ATTEMPTS_DIR` is set to `/home/jovyan/shared-public/quiz_attempts` — this
matches the Hub's actual writable shared directory. Earlier directory names
(`shared-readwrite` and similar) were **not** reliably writable for students on this Hub. If the
Hub's shared writable path ever changes again, update `ATTEMPTS_DIR` at the top of
`stemds_quiz.py` accordingly — it's the only place this path is defined.

## How the multi-attempt quiz logic works

`stemds_quiz.py` distinguishes two different "attempts" concepts — see the module's docstring
for full detail:

- `max_attempts` (per **question**, inside one sitting — e.g. a second guess allowed)
- `max_quiz_attempts` (times the **whole quiz** may be opened/retaken — e.g. 3)

Re-running the quiz cell mid-attempt (e.g. after a kernel restart) always resumes the same
in-progress attempt with the same question subset — it does not consume a new attempt. A new
attempt, with a freshly-drawn 30-question subset, only starts once the previous attempt has been
fully completed and the student reopens the quiz. After all quiz attempts are used, `open_quiz()`
shows a locked message with the student's attempt history; an instructor can reset a student (or
everyone) with `stemds_quiz.reset_attempt()`.

## Superseded files

`CA_Onboarding_Quiz.ipynb` and `questions_ca_onboarding.json` are the original single-quiz
version, replaced by the two-quiz split above. Safe to delete once you've confirmed the new
quizzes work — keeping them around doesn't break anything, they're just no longer linked from
the manual.

## Local preview of the manual

```bash
python3 -m http.server 8000
# then open http://localhost:8000 in a browser
```

## Updating the manual or quizzes

Edit the relevant file(s), commit, and push to `main` — GitHub Pages rebuilds the site
automatically within a minute or two. Quiz notebooks and question banks take effect on the Hub
next time a student pulls the repo (see the nbgitpuller links in the manual's "Test Yourself"
section).
