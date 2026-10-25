# Compliance Report

Status key: **PASS** implemented and verified · **PENDING STUDENT ACTION** needs an external action by the student · **NOT VERIFIED** could not be tested in the build environment.

Environment: Linux, Python 3.12, Streamlit 1.66.1, NumPy 2.5.4, pandas 3.1.0, Plotly 7.1.0 (installed from `requirements.txt` into a fresh virtual environment).
Methods: **T** = pytest (82 tests, all passing) · **B** = `tools/capture_and_verify.py`, 22 checks in real headless Chromium against the live server, all passing · **E** = edge-case battery of 23 hand-made CSV files run through the loader · **I** = inspection.

## Core assignment
| Requirement | Where | Method | Status |
|---|---|---|---|
| Python, NumPy, Pandas used meaningfully | `functions.py` (`analyze`, `subject_stats`, `attendance_stats`, `_validate`) | I, T | PASS |
| Variables and data types | `main.py` (int, float, str, bool) | I | PASS |
| Loops, functions, conditions | `functions.py`, `main.py` | I, T | PASS |
| ≥ 20 fictional records; ID, Name, Department, 5 subjects, Attendance | `data/students.csv` (26) | T | PASS |
| Total, average, grade, pass/fail | `analyze`, `assign_grade`, `is_passing` | T (hand-calculated set) | PASS |
| Highest/lowest, class average, subject analysis, top students | `summary_metrics`, `subject_stats`, `top_students` | T, B | PASS |

## GUI
| Requirement | Method | Status |
|---|---|---|
| Dashboard: 9 metrics, 4 charts, top table, dataset name + count | T, B (screenshot) | PASS |
| Student Records: search, 4 filters, sort, count, reset | T, B | PASS |
| Individual Student: profile, class comparison, interpretation | T, B | PASS |
| Subject, Department, Attendance, Grade & Result pages | T, B | PASS |
| Dataset page: upload, checklist, warnings, preview, return to bundled data | T, B | PASS |
| Invalid upload rejected and not used; valid upload drives dashboard; reset works | B | PASS |
| All six downloads (4 CSV, HTML report, Markdown report) contain current data and respect filters | B (all downloaded and opened) | PASS |
| Empty / invalid / one-record states handled | T | PASS |
| No hardcoded or contradictory values | I, T (dashboard values equal engine values) | PASS |

## Quality
| Requirement | Method | Status |
|---|---|---|
| Calculation logic centralised | I | PASS |
| Validation of all listed problems | T, E | PASS |
| Grade / pass-fail boundaries, ties, empty data, fewer than five students | T | PASS |
| Dependencies install in a fresh virtual environment and the suite passes | T | PASS |
| Tested only on the newest allowed library versions | – | NOT VERIFIED (older versions) |
| Windows PowerShell commands | – | NOT VERIFIED (Linux equivalents verified) |

## Submission
| Item | Status |
|---|---|
| Dataset, app, requirements, README, formal documentation, tests, screenshots included | PASS |
| `.gitignore` excludes venvs, caches, generated outputs | PASS |
| Student details and *Challenges & Learning* written in `Project_Documentation.md` | PENDING STUDENT ACTION |
| GitHub repository created, pushed, URL verified | PENDING STUDENT ACTION |
| EWB Google Form submitted | PENDING STUDENT ACTION |

## Defects found and fixed during the audit
1. **Silent column shift:** a CSV in which *every* row had one extra field was accepted and values landed in the wrong columns (Student_ID lost, Attendance = 1). Now rejected; regression test added.
2. Melt column-name clash crashed the Department page (found by page-render tests).
3. Charts were captured as loading placeholders; the capture script now waits for rendering.
4. Metric cards had uneven heights; averages displayed as `98` instead of `98.00`; duplicated words in the dataset banner.
5. Duplicate IDs differing only in capitals (S1 / s1) were accepted; Windows-1252 files and lower-case headers were rejected unnecessarily; derived columns in an upload were dropped without telling the user.

## Notes
- Grade F with result Pass is a direct consequence of the stated rules (S011, S026).
- Screenshot 11 uses a three-student test file.
