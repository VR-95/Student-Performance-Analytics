"""Shared validation and analysis engine for the Student Performance Analytics System.

Every page of the Streamlit app (app.py) and the command-line script (main.py)
calls the functions in this file, so results can never contradict each other.
"""
from __future__ import annotations

import csv
import html
import re
from datetime import datetime
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

# ----------------------------------------------------------------- configuration
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = BASE_DIR / "data" / "students.csv"

ID_COL, NAME_COL, DEPT_COL, ATT_COL = "Student_ID", "Name", "Department", "Attendance"
SUBJECTS = ["Python", "Statistics", "NumPy", "Pandas", "Data_Analysis"]  # explicit: never guessed
TEXT_COLUMNS = [ID_COL, NAME_COL, DEPT_COL]
NUMERIC_COLUMNS = SUBJECTS + [ATT_COL]
REQUIRED_COLUMNS = [ID_COL, NAME_COL, DEPT_COL] + SUBJECTS + [ATT_COL]

PASS_AVERAGE = 40        # project-defined rule: average must be >= 40
PASS_SUBJECT_MARK = 35   # project-defined rule: every subject must be >= 35
ATTENDANCE_THRESHOLD = 75
GRADE_BANDS = [(90, "A+"), (80, "A"), (70, "B"), (60, "C"), (50, "D")]  # lower bound -> grade
GRADE_ORDER = ["A+", "A", "B", "C", "D", "F"]


# ----------------------------------------------------------------- scalar rules
def assign_grade(average: float) -> str:
    """Return the grade for an average (the single grading function used everywhere)."""
    if average is None or pd.isna(average):
        raise ValueError("Cannot grade a missing average.")
    for lower_bound, grade in GRADE_BANDS:
        if average >= lower_bound:
            return grade
    return "F"


def is_passing(average: float, subject_marks) -> bool:
    """Pass only if average >= 40 AND every subject mark >= 35."""
    if average < PASS_AVERAGE:
        return False
    for mark in subject_marks:  # loop: any weak subject fails the student
        if mark < PASS_SUBJECT_MARK:
            return False
    return True


# ----------------------------------------------------------------- loading + validation
CAT_FILE = "File can be read"
CAT_COLUMNS = "Required columns present"
CAT_ROWS = "Contains student records"
CAT_MISSING = "No missing values"
CAT_NUMERIC = "Marks and attendance are numeric"
CAT_DUPLICATE = "Student IDs are unique"
CAT_MARKS = "Marks within 0-100"
CAT_ATTENDANCE = "Attendance within 0-100"
CHECK_ORDER = [CAT_FILE, CAT_COLUMNS, CAT_ROWS, CAT_MISSING, CAT_NUMERIC, CAT_DUPLICATE, CAT_MARKS, CAT_ATTENDANCE]
DERIVED_COLUMNS = ["Total_Marks", "Average_Marks", "Grade", "Result"]


@dataclass
class ValidationResult:
    """Outcome of loading a dataset: clean data (only if valid), problems, and notes."""
    source_name: str = ""
    data: pd.DataFrame | None = None
    issues: list = field(default_factory=list)      # list of (category, message)
    warnings: list = field(default_factory=list)    # things we fixed or ignored (never errors)
    raw_preview: pd.DataFrame | None = None
    raw_rows: int = 0
    raw_columns: int = 0

    @property
    def ok(self) -> bool:
        return not self.issues and self.data is not None

    @property
    def errors(self) -> list:
        return [message for _, message in self.issues]

    def checklist(self) -> list:
        """[(check name, passed)] in a fixed order, for display."""
        failed = {category for category, _ in self.issues}
        return [(name, name not in failed) for name in CHECK_ORDER]


def _canon(name) -> str:
    """Header comparison key: ignores case, spaces, underscores and hyphens."""
    return re.sub(r"[\s_\-]+", "", str(name).strip().lower())


def _rows(mask) -> str:
    """CSV row numbers (row 1 is the header) of True entries, shortened for display."""
    rows = (np.flatnonzero(np.asarray(mask, dtype=bool)) + 2).tolist()
    text = ", ".join(str(n) for n in rows[:10])
    return text + (f" (+{len(rows) - 10} more)" if len(rows) > 10 else "")


def _as_text(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("").str.strip().astype(object)


def _validate(raw, source_name: str = "") -> ValidationResult:
    """Validate a raw table. Collects ALL problems so the user can fix them in one pass."""
    res = ValidationResult(source_name=source_name)
    if raw is None or not isinstance(raw, pd.DataFrame) or raw.shape[1] == 0:
        res.issues.append((CAT_FILE, "The file contains no columns."))
        return res
    raw = raw.reset_index(drop=True)
    res.raw_rows, res.raw_columns = raw.shape
    res.raw_preview = raw.head(50)

    # --- columns: matched ignoring case/spaces, but each required column exactly once
    lookup = {_canon(c): c for c in REQUIRED_COLUMNS}
    found: dict = {}
    extras = []
    for original in raw.columns:
        target = lookup.get(_canon(original))
        if target is None:
            extras.append(str(original).strip())
        else:
            found.setdefault(target, []).append(original)
    repeated = [t for t, cols in found.items() if len(cols) > 1]
    if repeated:
        res.issues.append((CAT_COLUMNS, "Column(s) appear more than once: " + ", ".join(repeated) + "."))
        return res
    missing = [c for c in REQUIRED_COLUMNS if c not in found]
    if missing:
        res.issues.append((CAT_COLUMNS, "Missing required column(s): " + ", ".join(missing)
                           + ". Expected: " + ", ".join(REQUIRED_COLUMNS) + "."))
        return res
    renamed = [f"'{str(cols[0]).strip()}' read as {t}" for t, cols in found.items() if str(cols[0]).strip() != t]
    if renamed:
        res.warnings.append("Column names were matched ignoring capitals and spaces: " + "; ".join(renamed) + ".")
    derived = [c for c in extras if c in DERIVED_COLUMNS]
    if derived:
        res.warnings.append("Column(s) " + ", ".join(derived) + " were ignored; the app recalculates them.")
    others = [c for c in extras if c not in DERIVED_COLUMNS]
    if others:
        res.warnings.append("Extra column(s) ignored: " + ", ".join(others) + ".")
    if len(raw) == 0:
        res.issues.append((CAT_ROWS, "The dataset contains no student records."))
        return res

    df = pd.DataFrame({t: _as_text(raw[found[t][0]]) for t in REQUIRED_COLUMNS})

    # --- text columns
    for col in TEXT_COLUMNS:
        blank = (df[col] == "").to_numpy()
        if blank.any():
            res.issues.append((CAT_MISSING, f"'{col}' is empty in CSV row(s): {_rows(blank)}."))
    ids = df[ID_COL]
    repeated_ids = (ids != "") & ids.str.casefold().duplicated(keep=False)
    if repeated_ids.any():
        res.issues.append((CAT_DUPLICATE, "Duplicate Student_ID value(s): " + ", ".join(sorted(ids[repeated_ids].unique()))
                           + " (IDs are compared ignoring upper/lower case)."))

    # --- numeric columns (loop over every subject and attendance)
    numeric = {}
    for col in NUMERIC_COLUMNS:
        text = df[col]
        blank = (text == "").to_numpy()
        values = pd.to_numeric(text, errors="coerce").to_numpy(dtype=float)
        finite = np.isfinite(values)
        not_numeric = ~blank & ~finite
        out_of_range = finite & ((values < 0) | (values > 100))
        if blank.any():
            res.issues.append((CAT_MISSING, f"'{col}' has missing value(s) in CSV row(s): {_rows(blank)}. "
                                            "Missing values are never replaced with zero."))
        if not_numeric.any():
            examples = ", ".join(f"'{v}'" for v in text[not_numeric].unique()[:3])
            res.issues.append((CAT_NUMERIC, f"'{col}' has non-numeric value(s) {examples} in CSV row(s): {_rows(not_numeric)}."))
        if out_of_range.any():
            category = CAT_ATTENDANCE if col == ATT_COL else CAT_MARKS
            res.issues.append((category, f"'{col}' must be between 0 and 100; invalid in CSV row(s): {_rows(out_of_range)}."))
        numeric[col] = values
    if res.issues:
        return res

    clean = df.copy()
    for col in NUMERIC_COLUMNS:
        clean[col] = numeric[col]
    res.data = clean.reset_index(drop=True)
    return res


def load_dataset(source, source_name: str = "") -> ValidationResult:
    """Read and validate a CSV from a path, bytes or uploaded file. Never raises for bad input."""
    name = source_name

    def fail(message, category=CAT_FILE):
        return ValidationResult(source_name=name, issues=[(category, message)])

    try:
        if isinstance(source, (str, Path)):
            path = Path(source)
            name = name or path.name
            if not path.is_file():
                return fail(f"File not found: {path}")
            content = path.read_bytes()
        elif isinstance(source, (bytes, bytearray)):
            content = bytes(source)
        elif hasattr(source, "getvalue"):
            content = source.getvalue()
            name = name or getattr(source, "name", "")
        elif hasattr(source, "read"):
            content = source.read()
        else:
            return fail("Unsupported file source.")
        if isinstance(content, str):
            content = content.encode("utf-8")
        if not content.strip():
            return fail("The file is empty.")
        if b"\x00" in content:
            return fail("This does not look like a plain-text CSV file (it contains binary data).")

        warnings = []
        try:
            text = content.decode("utf-8-sig")            # also strips the Excel BOM
        except UnicodeDecodeError:
            try:
                text = content.decode("cp1252")           # Excel on Windows often saves this way
                warnings.append("The file was not UTF-8, so it was read as Windows-1252 text. "
                                "Check that accented names look right.")
            except UnicodeDecodeError:
                return fail("The file is not readable text. Save it as 'CSV (UTF-8)' and try again.")

        rows = [r for r in csv.reader(StringIO(text)) if r]
        header = rows[0] if rows else []
        if len(header) == 1 and any(sep in header[0] for sep in (";", "\t", "|")):
            return fail("The columns look separated by ';', tab or '|'. Save the file as a comma-separated CSV.")
        wrong = [(i + 1, len(r)) for i, r in enumerate(rows[1:], start=1) if len(r) != len(header)]
        if wrong:
            shown = "; ".join(f"row {n} has {k} fields" for n, k in wrong[:3])
            more = f" (and {len(wrong) - 3} more)" if len(wrong) > 3 else ""
            return fail(f"The file is not a well-formed CSV: the header has {len(header)} fields but {shown}{more}.")

        raw = pd.read_csv(StringIO(text), dtype=str, keep_default_na=False, index_col=False)
    except pd.errors.EmptyDataError:
        return fail("The file is empty or has no readable header row.")
    except pd.errors.ParserError as exc:
        return fail(f"The file is not a well-formed CSV: {exc}")
    except Exception as exc:  # an upload must never crash the app
        return fail(f"The file could not be read: {exc}")

    result = _validate(raw, name)
    result.warnings = warnings + result.warnings
    return result


def validate_dataframe(raw):
    """Compatibility wrapper: (clean_df or None, error messages)."""
    res = _validate(raw)
    return res.data, res.errors


def load_csv(source):
    """Compatibility wrapper: (clean_df or None, error messages)."""
    res = load_dataset(source)
    return res.data, res.errors


# ----------------------------------------------------------------- core analysis
def analyze(clean: pd.DataFrame) -> pd.DataFrame:
    """Add Total_Marks, Average_Marks, Grade and Result to a validated DataFrame."""
    out = clean.copy()
    marks = out[SUBJECTS].to_numpy(dtype=float)       # NumPy matrix: students x subjects
    total = np.round(marks.sum(axis=1), 6)           # removes floating-point noise before grading
    average = total / len(SUBJECTS)
    out["Total_Marks"] = total
    out["Average_Marks"] = average
    out["Grade"] = [assign_grade(a) for a in average]
    out["Result"] = ["Pass" if is_passing(a, row) else "Fail" for a, row in zip(average, marks)]
    return out


def failing_subjects(row) -> list[str]:
    return [s for s in SUBJECTS if row[s] < PASS_SUBJECT_MARK]


def extremes(df: pd.DataFrame, column: str, kind: str = "max") -> pd.DataFrame:
    """All rows tied for the highest ('max') or lowest ('min') value of a column."""
    if df.empty:
        return df.copy()
    target = df[column].max() if kind == "max" else df[column].min()
    return df[np.isclose(df[column].to_numpy(dtype=float), target)]


def top_students(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Top n students by average. Equal averages share a rank."""
    if df.empty:
        return df.copy()
    ranked = df.sort_values([ "Average_Marks", ID_COL], ascending=[False, True]).copy()
    ranked.insert(0, "Rank", ranked["Average_Marks"].rank(method="min", ascending=False).astype(int))
    return ranked[ranked["Rank"] <= n]               # students tied at the cut-off are all shown


def subject_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Per-subject statistics (attendance is never treated as a subject)."""
    rows = []
    for subject in SUBJECTS:
        marks = df[subject].to_numpy(dtype=float)
        rows.append({
            "Subject": subject,
            "Average": float(np.mean(marks)) if marks.size else np.nan,
            "Highest": float(np.max(marks)) if marks.size else np.nan,
            "Lowest": float(np.min(marks)) if marks.size else np.nan,
            "Median": float(np.median(marks)) if marks.size else np.nan,
            "Passing": int((marks >= PASS_SUBJECT_MARK).sum()),
            "Failing": int((marks < PASS_SUBJECT_MARK).sum()),
        })
    return pd.DataFrame(rows)


def best_and_lowest_subjects(stats: pd.DataFrame):
    """(best_subjects, lowest_subjects) as lists, so ties are all reported."""
    if stats.empty or stats["Average"].isna().all():
        return [], []
    top, bottom = stats["Average"].max(), stats["Average"].min()
    best = stats.loc[np.isclose(stats["Average"], top), "Subject"].tolist()
    low = stats.loc[np.isclose(stats["Average"], bottom), "Subject"].tolist()
    return best, low


def grade_distribution(df: pd.DataFrame) -> pd.DataFrame:
    counts = df["Grade"].value_counts().reindex(GRADE_ORDER, fill_value=0)
    pct = counts / len(df) * 100 if len(df) else counts * 0.0
    return pd.DataFrame({"Grade": GRADE_ORDER, "Students": counts.to_numpy(), "Percentage": pct.to_numpy()})


def department_stats(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for dept, group in df.groupby(DEPT_COL, sort=True):
        passed = int((group["Result"] == "Pass").sum())
        rows.append({
            "Department": dept, "Students": len(group),
            "Average_Marks": float(group["Average_Marks"].mean()),
            "Passed": passed, "Failed": len(group) - passed,
            "Pass_Percentage": passed / len(group) * 100,
            "Average_Attendance": float(group[ATT_COL].mean()),
        })
    return pd.DataFrame(rows, columns=["Department", "Students", "Average_Marks", "Passed", "Failed",
                                       "Pass_Percentage", "Average_Attendance"])


def best_departments(dept_df: pd.DataFrame) -> list[str]:
    """Department(s) with the highest average marks (all tied departments)."""
    if dept_df.empty:
        return []
    top = dept_df["Average_Marks"].max()
    return dept_df.loc[np.isclose(dept_df["Average_Marks"], top), "Department"].tolist()


def attendance_stats(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    low = df[df[ATT_COL] < ATTENDANCE_THRESHOLD]
    return {
        "average": float(df[ATT_COL].mean()), "highest": float(df[ATT_COL].max()),
        "lowest": float(df[ATT_COL].min()), "below_count": len(low),
        "meeting_count": len(df) - len(low), "below_students": low,
    }


def summary_metrics(df: pd.DataFrame) -> dict:
    """Headline numbers used by the dashboard, the reports and the CLI."""
    if df.empty:
        return {}
    passed = int((df["Result"] == "Pass").sum())
    n = len(df)
    best, low = best_and_lowest_subjects(subject_stats(df))
    return {
        "students": n, "subjects": len(SUBJECTS),
        "class_average": float(df["Average_Marks"].mean()),
        "highest_average": float(df["Average_Marks"].max()),
        "lowest_average": float(df["Average_Marks"].min()),
        "highest_total": float(df["Total_Marks"].max()),
        "lowest_total": float(df["Total_Marks"].min()),
        "pass_count": passed, "fail_count": n - passed,
        "pass_pct": passed / n * 100, "fail_pct": (n - passed) / n * 100,
        "avg_attendance": float(df[ATT_COL].mean()),
        "best_subjects": best, "lowest_subjects": low,
        "highest_students": extremes(df, "Average_Marks", "max")[NAME_COL].tolist(),
        "lowest_students": extremes(df, "Average_Marks", "min")[NAME_COL].tolist(),
    }


NEAR_FAIL_AVERAGE = 45   # a passing student below this average is "close to failing"
NEAR_FAIL_SUBJECT = 40   # ... or with any subject below this mark


def needs_attention(df: pd.DataFrame) -> pd.DataFrame:
    """Students who fail, are close to failing, or have low attendance, with the reasons."""
    rows = []
    for _, row in df.iterrows():
        reasons = []
        if row["Result"] == "Fail":
            reasons.append("Fails the pass rule")
        elif row["Average_Marks"] < NEAR_FAIL_AVERAGE or min(row[s] for s in SUBJECTS) < NEAR_FAIL_SUBJECT:
            reasons.append("Close to failing")
        if row[ATT_COL] < ATTENDANCE_THRESHOLD:
            reasons.append(f"Attendance below {ATTENDANCE_THRESHOLD}%")
        if reasons:
            rows.append({ID_COL: row[ID_COL], NAME_COL: row[NAME_COL], DEPT_COL: row[DEPT_COL],
                         "Average_Marks": row["Average_Marks"], ATT_COL: row[ATT_COL],
                         "Result": row["Result"], "Reasons": "; ".join(reasons)})
    cols = [ID_COL, NAME_COL, DEPT_COL, "Average_Marks", ATT_COL, "Result", "Reasons"]
    return pd.DataFrame(rows, columns=cols).sort_values("Average_Marks", kind="stable").reset_index(drop=True)


def reconciliation_check(df: pd.DataFrame) -> dict:
    """Confirms grade counts and pass/fail counts both add up to the number of students."""
    n = len(df)
    grades = int(grade_distribution(df)["Students"].sum())
    passed = int((df["Result"] == "Pass").sum())
    failed = int((df["Result"] == "Fail").sum())
    return {"students": n, "grade_total": grades, "pass_total": passed, "fail_total": failed,
            "ok": grades == n and passed + failed == n}


def filter_students(df, search="", departments=None, grades=None, results=None,
                    attendance_range=(0, 100), sort_by="Average_Marks", ascending=False):
    """Apply the Student Records filters. Returns a new DataFrame; the input is untouched."""
    out = df
    if search and search.strip():
        q = search.strip().lower()
        hit = out[ID_COL].str.lower().str.contains(q, regex=False) | out[NAME_COL].str.lower().str.contains(q, regex=False)
        out = out[hit]
    if departments:
        out = out[out[DEPT_COL].isin(departments)]
    if grades:
        out = out[out["Grade"].isin(grades)]
    if results:
        out = out[out["Result"].isin(results)]
    low, high = attendance_range
    out = out[(out[ATT_COL] >= low) & (out[ATT_COL] <= high)]
    return out.sort_values(sort_by, ascending=ascending, kind="stable").reset_index(drop=True)


def interpret_student(row, class_average: float) -> str:
    """Plain-language interpretation following the documented rules."""
    avg = row["Average_Marks"]
    diff = avg - class_average
    where = "above" if diff > 0 else "below" if diff < 0 else "equal to"
    text = f"{row[NAME_COL]} has an average of {avg:.2f} (grade {row['Grade']}), "
    text += f"{abs(diff):.2f} points {where} the class average of {class_average:.2f}." if diff else "equal to the class average."
    if row["Result"] == "Pass":
        text += " The student passes: average is at least 40 and every subject is at least 35."
    else:
        reasons = []
        if avg < PASS_AVERAGE:
            reasons.append(f"average is below {PASS_AVERAGE}")
        weak = failing_subjects(row)
        if weak:
            reasons.append(f"subject mark below {PASS_SUBJECT_MARK} in {', '.join(weak)}")
        text += " The student fails because " + " and ".join(reasons) + "."
    if row[ATT_COL] < ATTENDANCE_THRESHOLD:
        text += f" Attendance ({row[ATT_COL]:.0f}%) is below the {ATTENDANCE_THRESHOLD}% threshold (this does not change the academic result)."
    return text


# ----------------------------------------------------------------- exports
def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def build_summary_report(df: pd.DataFrame, source_name: str = "students.csv") -> str:
    """Markdown summary report built from the same functions as the dashboard."""
    m = summary_metrics(df)
    if not m:
        return "# Student Performance Summary\n\nNo data available."
    top = top_students(df, 5)
    att = attendance_stats(df)
    dept = department_stats(df)
    lines = [
        "# Student Performance Summary Report", "", f"Dataset: {source_name} ({m['students']} students, {m['subjects']} subjects)", "",
        "## Key metrics",
        f"- Class average: {m['class_average']:.2f}",
        f"- Highest student average: {m['highest_average']:.2f}",
        f"- Lowest student average: {m['lowest_average']:.2f}",
        f"- Highest / lowest total marks: {m['highest_total']:.0f} / {m['lowest_total']:.0f}",
        f"- Passed: {m['pass_count']} ({m['pass_pct']:.1f}%)  Failed: {m['fail_count']} ({m['fail_pct']:.1f}%)",
        f"- Best subject: {', '.join(m['best_subjects'])}  Lowest subject: {', '.join(m['lowest_subjects'])}",
        f"- Average attendance: {m['avg_attendance']:.1f}%  Students below {ATTENDANCE_THRESHOLD}%: {att['below_count']}", "",
        "## Top students",
    ]
    lines += [f"{r.Rank}. {r.Name} ({r.Student_ID}) - average {r.Average_Marks:.2f}, grade {r.Grade}" for r in top.itertuples()]
    lines += ["", "## Grade distribution"]
    lines += [f"- {r.Grade}: {r.Students} ({r.Percentage:.1f}%)" for r in grade_distribution(df).itertuples()]
    lines += ["", "## Departments (best: " + ", ".join(best_departments(dept)) + ")"]
    lines += [f"- {r.Department}: {r.Students} students, average {r.Average_Marks:.2f}, pass {r.Pass_Percentage:.1f}%" for r in dept.itertuples()]
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------- styled HTML report
_REPORT_CSS = """
*{box-sizing:border-box}body{margin:0;background:#F6F3EC;color:#1F2933;font:15px/1.5 "Segoe UI",system-ui,sans-serif}
.page{max-width:980px;margin:0 auto;padding:28px 20px 48px}
header{background:linear-gradient(120deg,#0B4F4A,#0F766E);color:#fff;border-radius:14px;padding:26px 30px}
header h1{margin:0 0 4px;font-size:26px}header p{margin:0;opacity:.85}
h2{color:#0B4F4A;border-bottom:3px solid #F2B84B;display:inline-block;padding-bottom:2px;margin:34px 0 12px;font-size:19px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:18px}
.kpi{background:#fff;border-radius:12px;padding:14px 16px;border-top:4px solid #0F766E;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.kpi.warn{border-top-color:#C2410C}.kpi b{display:block;font-size:24px;color:#0B4F4A}.kpi span{font-size:12px;color:#5B6770;text-transform:uppercase;letter-spacing:.04em}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}
th{background:#0F766E;color:#fff;text-align:left;padding:8px 10px;font-size:13px}td{padding:7px 10px;border-bottom:1px solid #E7E2D6;font-size:14px}
tr:nth-child(even) td{background:#FAF8F3}td.n,th.n{text-align:right}
.bar{display:flex;align-items:center;gap:10px;margin:5px 0}.bar i{width:110px;font-style:normal;font-size:13px}
.bar div{height:16px;border-radius:8px;background:#2A9D8F}.bar em{font-style:normal;font-size:13px;color:#5B6770}
.tag{padding:2px 9px;border-radius:10px;font-size:12px;font-weight:600}.pass{background:#D5F0EA;color:#0B4F4A}.fail{background:#FBE0D3;color:#9A3412}
footer{margin-top:34px;font-size:12px;color:#5B6770}
@media(max-width:700px){.kpis{grid-template-columns:repeat(2,1fr)}}
@media print{body{background:#fff}.page{padding:0}header,.kpi,th,.bar div,.tag{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
"""


def _html_table(headers, rows, numeric=()):
    head = "".join(f'<th class="{"n" if i in numeric else ""}">{html.escape(str(h))}</th>' for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(
        f'<td class="{"n" if i in numeric else ""}">{cell}</td>' for i, cell in enumerate(row)) + "</tr>" for row in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def _tag(result: str) -> str:
    return f'<span class="tag {"pass" if result == "Pass" else "fail"}">{html.escape(result)}</span>'


def _bars(labels, values, maximum, unit=""):
    return "".join(
        f'<div class="bar"><i>{html.escape(str(l))}</i><div style="width:{(v / maximum * 60 if maximum else 0):.1f}%"></div>'
        f"<em>{v:.1f}{unit}</em></div>" if isinstance(v, float) else
        f'<div class="bar"><i>{html.escape(str(l))}</i><div style="width:{(v / maximum * 60 if maximum else 0):.1f}%"></div><em>{v}</em></div>'
        for l, v in zip(labels, values))


def build_html_report(df: pd.DataFrame, source_name: str = "dataset", generated_at=None) -> str:
    """Self-contained, colour-styled, printable HTML summary report (same numbers as every page)."""
    esc = html.escape
    m = summary_metrics(df)
    if not m:
        return "<!doctype html><meta charset='utf-8'><title>Report</title><p>No data available.</p>"
    when = (generated_at or datetime.now()).strftime("%d %b %Y, %H:%M")
    att, dept, gd, subj = attendance_stats(df), department_stats(df), grade_distribution(df), subject_stats(df)
    kpis = [("Students", f"{m['students']}", False), ("Class average", f"{m['class_average']:.2f}", False),
            ("Pass rate", f"{m['pass_pct']:.1f}%", False), ("Failing students", f"{m['fail_count']}", m["fail_count"] > 0),
            ("Highest average", f"{m['highest_average']:.2f}", False), ("Lowest average", f"{m['lowest_average']:.2f}", False),
            ("Average attendance", f"{m['avg_attendance']:.1f}%", False),
            (f"Attendance below {ATTENDANCE_THRESHOLD:g}%", f"{att['below_count']}", att["below_count"] > 0)]
    tiles = "".join(f'<div class="kpi{" warn" if w else ""}"><span>{esc(k)}</span><b>{esc(v)}</b></div>' for k, v, w in kpis)
    top = top_students(df, 5)
    top_rows = [[r.Rank, esc(r.Student_ID), esc(r.Name), esc(r.Department), f"{r.Average_Marks:.2f}", esc(r.Grade), _tag(r.Result)]
                for r in top.itertuples()]
    dept_rows = [[esc(r.Department), r.Students, f"{r.Average_Marks:.2f}", r.Passed, r.Failed, f"{r.Pass_Percentage:.1f}%"]
                 for r in dept.itertuples()]
    attn = needs_attention(df)
    attn_rows = [[esc(r.Student_ID), esc(r.Name), f"{r.Average_Marks:.2f}", f"{r.Attendance:.0f}%", esc(r.Reasons)] for r in attn.itertuples()]
    attention_html = _html_table(["ID", "Name", "Average", "Attendance", "Reasons"], attn_rows, {2, 3}) if attn_rows \
        else "<p>No student fails, is close to failing, or has low attendance.</p>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Student Performance Report</title><style>{_REPORT_CSS}</style></head><body><div class="page">
<header><h1>Student Performance Report</h1><p>Dataset: {esc(source_name)} · {m['students']} students · {m['subjects']} subjects · generated {when}</p></header>
<div class="kpis">{tiles}</div>
<h2>Top students</h2>{_html_table(["Rank", "ID", "Name", "Department", "Average", "Grade", "Result"], top_rows, {0, 4})}
<h2>Grade distribution</h2>{_bars(gd["Grade"], gd["Students"].tolist(), max(gd["Students"].max(), 1))}
<h2>Subject averages</h2>{_bars(subj["Subject"], subj["Average"].tolist(), 100.0)}
<p>Best subject: <b>{esc(", ".join(m["best_subjects"]))}</b> · Lowest subject: <b>{esc(", ".join(m["lowest_subjects"]))}</b></p>
<h2>Departments</h2>{_html_table(["Department", "Students", "Average", "Passed", "Failed", "Pass %"], dept_rows, {1, 2, 3, 4, 5})}
<p>Best department: <b>{esc(", ".join(best_departments(dept)))}</b></p>
<h2>Students needing attention</h2>{attention_html}
<footer>Pass rule: average ≥ {PASS_AVERAGE:g} and every subject ≥ {PASS_SUBJECT_MARK:g}. Grades: A+ ≥ 90, A ≥ 80, B ≥ 70, C ≥ 60, D ≥ 50, else F.
Attendance never changes the academic result.</footer></div></body></html>
"""
