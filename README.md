# mybk-planner: HCMUT course planner, GPA & myBK portal CLI

[![PyPI version](https://img.shields.io/pypi/v/mybk-planner)](https://pypi.org/project/mybk-planner/)
[![Python](https://img.shields.io/pypi/pyversions/mybk-planner)](https://pypi.org/project/mybk-planner/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/danhnth/mybk-planner/actions/workflows/ci.yml/badge.svg)](https://github.com/danhnth/mybk-planner/actions)
[![Downloads](https://img.shields.io/pypi/dm/mybk-planner)](https://pypi.org/project/mybk-planner/)

**mybk-planner** is a read-only command-line tool for HCMUT (Đại học Bách Khoa TP.HCM) students. It turns the myBK portal into a course planner: GPA tracker, transcript reader, CTĐT curriculum progress, timetable, exam schedule, and a next-semester course recommendation engine with tuition estimates. All from your terminal, in Vietnamese and English output.

Read-only by design. It **finds** the classes and **recommends** a plan; registration stays in the official portal.

[Tiếng Việt → README.vi.md](README.vi.md)

## Table of Contents

- [What can it do?](#what-can-it-do)
- [Why another myBK tool?](#why-another-mybk-tool)
- [How do I install it?](#how-do-i-install-it)
- [How do I configure it?](#how-do-i-configure-it)
- [Quick start](#quick-start)
- [Commands](#commands)
- [The course planner](#the-course-planner-plan)
- [Interactive REPL](#interactive-repl)
- [JSON output for scripting](#json-output-for-scripting)
- [API quirks & parser notes](#api-quirks--parser-notes)
- [Security & scope](#security--scope)
- [Tests & development](#tests--development)
- [FAQ](#faq)
- [License](#license)

## What can it do?

- **GPA & transcript**: cumulative GPA on the 10-point and 4-point scales, per-semester GPA history, letter-grade distribution, courses you can still improve (D grades), and retakes that are no longer "failed" once you pass them.
- **CTĐT curriculum progress**: per-khối (knowledge block) credit progress against the official program requirements, with the correct multi-constraint khối math (BB core + elective pool + seminar are summed, not collapsed).
- **Timetable & exam schedule**: fetch your thời khóa biểu and lịch thi for any semester.
- **Course planner**: `plan` combines curriculum + grades (+ the live open-class feed) and suggests a next-semester course list. It prioritises retakes, fills each khối's gap up to its own remaining credits, and stays inside your per-semester credit budget.
- **Tuition estimates**: the plan prints an estimated semester fee from the official 2026-27 fee notice: the flat "trọn gói" fee for your program, vượt định mức credits billed per credit above the 18-TC/HK quota, and the Bảng 1.2 discount tiers when you register fewer credits.
- **Registration read-only surface**: current đợt (registration round) info, open classes, your own tickets and defer-exam (hoãn thi) rows. Write endpoints are deliberately **not** wrapped.

## Why another myBK tool?

Existing HCMUT community tools (`mybk-mobile`, `BKSchedule`, `BKSCrawler`, score-checker scripts) are mostly stale, archived, or browser plugins. mybk-planner is:

- **Live-verified against the current myBK `/app` API** (2026), including the `?null` anti-cache suffix, the UTF-8 BOM quirk, and the `{code,msg,data}` envelope.
- **Read-only and safe**: no `tao-phieu-dang-ky` / `huy-phieu-dang-ky` wrappers, ever. Your registration workflow is untouched.
- **Both CLI and library**: pretty tables in the terminal, raw JSON with `--json`, and importable pure functions (`analysis`, `fees`) for your own scripts.
- **Privacy-conscious**: credentials come from a git-ignored `.env` file, never committed; the tool is designed for your own account only.

## How do I install it?

Requires **Python 3.10+**. Install from PyPI:

```bash
pip install mybk-planner
```

Or from source:

```bash
git clone https://github.com/danhnth/mybk-planner.git
cd mybk-planner
pip install -e ".[dev]"      # includes pytest + ruff for development
```

Either way you get the `mybk-planner` console command (or run `python -m mybk_planner.cli`).

## How do I configure it?

Copy the template and fill in your own credentials:

```bash
cp .env.example .env
# edit .env with your HCMUT myBK login
```

| Variable | Required | Description |
|---|---|---|
| `MYBK_USERNAME` | yes | BKNetId: the part of your `@hcmut.edu.vn` email before the `@` |
| `MYBK_PASSWORD` | yes | your CAS password (quote it if it contains `#` or spaces) |
| `MYBK_MSSV` | no | student ID override; auto-detected from your profile when omitted |

Credentials resolve in this order: **CLI flag → OS environment variable → `.env` file**. The legacy `MYBK_TEST_USERNAME`/`MYBK_TEST_PASSWORD`/`MYBK_TEST_MSSV` names still work as fallbacks.

## Quick start

```bash
mybk-planner info            # who am I (profile)
mybk-planner gpa             # cumulative GPA, 10-scale + 4-scale
mybk-planner ctdt            # curriculum progress per knowledge block
mybk-planner plan            # suggested next-semester course plan + tuition estimate
mybk-planner                 # drop into the interactive REPL
```

Every command prints a rich table by default; add `--json` for raw scriptable output:

```bash
mybk-planner plan --max-tc 18 --semester 20253 --json
```

## Commands

| Command | What it fetches |
|---|---|
| `auth` | CAS login + JWT sanity check |
| `info` | student profile (MSSV, class, faculty) |
| `grades` | full transcript + pass/fail/mean summary |
| `gpa` | cumulative GPA (4-scale and 10-scale) + credits |
| `ctdt` | CTĐT curriculum progress per khối |
| `schedule --semester-year 20252` | timetable for a semester (`YYYYk` code) |
| `exams --namhoc 2025 --hocky 2` | exam schedule (GK/CK rows) |
| `reg-dots` | current registration đợt(s) |
| `reg-open-classes --hockytkb 20253` | open/withdrawable classes for a semester |
| `reg-tickets` | your pending + finished registration tickets |
| `reg-defer --hocky 20253 --dot HOANTHI_CK.20253.1` | hoãn-thi (defer exam) đợt + rows |
| `reg-profile` | your registrant profile |
| `plan [--max-tc 18.0] [--semester 20253]` | suggested next-semester plan + analysis + tuition |
| `dashboard [--max-tc 18.0] [--semester 20253]` | info + GPA + plan in one screen, one login |

## The course planner (`plan`)

`plan` reads the CTĐT curriculum and your grades, then:

1. Puts retakes first (courses you took but haven't passed yet).
2. Fills each unmet khối up to its own remaining-credit gap, largest gap first, so one block can't hog the whole budget while Tốt nghiệp stays empty.
3. Spills any leftover budget into met-khối courses by priority.
4. Prints a full analysis panel: GPA trajectory, completion %, khối compliance, grade health, graduation timeline, and a tuition estimate.

Key facts it gets right:

- Pass authority is the grade list, not CTĐT's `diemdat`. A retake pass (e.g. F then D+) correctly clears the course from "failed".
- Khối gaps are sums of distinct requirement rows. The feed repeats each group's requirement on every course row, and a khối can hold several additive groups (e.g. Chuyên ngành = BB core + elective pool + seminar). Naive first-row reads under-count the program.
- The timeline uses incremental credits between semesters: `ceil(remaining / max_tc)` semesters at your budget.
- Tuition (from the 2026-27 fee notice): flat "trọn gói" fee for your program, credits above the 18-TC/HK định mức billed at the per-credit price, and the ≤12/≤9/≤6 TC discount tiers (15/30/45%) shown when your plan qualifies.

## Interactive REPL

Run with no subcommand for a menu-driven session (one CAS login, then `1` to `8` plus `find`, `help`):

```
1 info · 2 grades · 3 gpa · 4 ctdt · 5 plan · 6 schedule · 7 exams · 8 dashboard
```

## JSON output for scripting

Pass `--json` anywhere for a single JSON document on stdout (login confirmation goes to stderr), so you can pipe into `jq` or your own analysis:

```bash
mybk-planner plan --json | jq '.plan.completion'
```

## API quirks & parser notes

Things the myBK API doesn't tell you, documented for contributors:

- **Envelope**: `{"code": "200"|"400", "data": …, "msg": …}`. `code` is a *string*; `400` still carries business rows.
- **`?null` suffix** is appended to the first query param on GET calls (anti-cache quirk of `/app/js/main.js`).
- **UTF-8 BOM** (`\ufeff`) is stripped from responses.
- **`id_hoc_ky` encoding**: `(YYYY % 100) * 10 + HK`. HK2 of 25-26 ⇒ `252`.
- **CAS**: myBK sits behind CAS 3.5.1 (`sso.hcmut.edu.vn/cas` for `/app`). A 403 during login usually means rate-limited, so wait, don't spam.

## Security & scope

- **Your own account only.** The `schedule`/`exams` tools accept an `mssv` argument. Feed them your own.
- **Read-only.** Registration and defer-exam write endpoints (`tao-phieu-dang-ky`, `huy-phieu-dang-ky`, `cap-nhat-…`) are discovered in the API bundles but deliberately **not** wrapped.
- **Credentials never committed.** `.env`, tokens and cookies are git-ignored.
- Not affiliated with HCMUT; this is an unofficial community tool.

## Tests & development

The pure logic (analysis, fees, env) has an offline pytest suite: no network, no account needed:

```bash
pip install -e ".[dev]"
python -m pytest tests -q
ruff check mybk_planner tests
```

CI runs pytest + ruff + a wheel build on Python 3.10/3.11/3.12.

## FAQ

### Is this an official HCMUT tool?

No. It is an unofficial, community-maintained read-only client for the myBK portal.

### Will my account be safe?

The tool only reads data using your own credentials, never modifies anything, and is designed for your own account only. Be mindful of myBK's rate limits.

### Can I use it for someone else's data?

No. Feed it only your own MSSV. The underlying endpoints are not for cross-account use.

### Why does my plan total differ from a raw sum of CTĐT credits?

Because a khối's gap is the sum of its *distinct* requirement rows, and the feed repeats requirement values on every course row. Raw sums over every listed elective option over-count.

### Do I still register in myBK?

Yes. This tool finds classes and suggests a plan; you always register through the official myBK portal.

## License

[MIT](LICENSE) © 2026 Nguyễn Thành Danh
