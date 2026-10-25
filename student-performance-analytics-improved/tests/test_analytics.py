import io

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import functions as fx

APP = str(fx.BASE_DIR / "app.py")


def make_df(rows):
    """rows: list of (id, name, dept, [5 marks], attendance)."""
    return pd.DataFrame([[i, n, d, *m, a] for i, n, d, m, a in rows], columns=fx.REQUIRED_COLUMNS)


@pytest.fixture
def small():
    """Hand-calculated dataset (see expected values in the tests below)."""
    return fx.analyze(make_df([
        ("A1", "Ann", "CS", [100, 90, 80, 70, 60], 90),   # total 400 avg 80   -> A  Pass
        ("B2", "Bob", "CS", [50, 50, 50, 50, 50], 70),    # total 250 avg 50   -> D  Pass
        ("C3", "Cy", "DS", [30, 40, 40, 40, 50], 80),     # total 200 avg 40   -> F  Fail (30 < 35)
        ("D4", "Di", "DS", [20, 20, 20, 20, 20], 60),     # total 100 avg 20   -> F  Fail
    ]))


def csv_bytes(text):
    return io.BytesIO(text.encode())


# ---------------------------------------------------------------- calculations
def test_total_and_average(small):
    assert small["Total_Marks"].tolist() == [400, 250, 200, 100]
    assert small["Average_Marks"].tolist() == [80, 50, 40, 20]
    assert fx.ATT_COL not in fx.SUBJECTS and fx.ID_COL not in fx.SUBJECTS


def test_grades_and_results(small):
    assert small["Grade"].tolist() == ["A", "D", "F", "F"]
    assert small["Result"].tolist() == ["Pass", "Pass", "Fail", "Fail"]


def test_summary_metrics(small):
    m = fx.summary_metrics(small)
    assert m["class_average"] == pytest.approx(47.5)
    assert (m["highest_average"], m["lowest_average"]) == (80, 20)
    assert (m["highest_total"], m["lowest_total"]) == (400, 100)
    assert (m["pass_count"], m["fail_count"]) == (2, 2)
    assert m["pass_pct"] == 50 and m["fail_pct"] == 50
    assert m["avg_attendance"] == pytest.approx(75)


def test_subject_stats(small):
    s = fx.subject_stats(small).set_index("Subject")
    assert s.loc["Python", "Average"] == pytest.approx(50)       # (100+50+30+20)/4
    assert s.loc["Python", ["Highest", "Lowest", "Median"]].tolist() == [100, 20, 40]
    assert s.loc["Python", ["Passing", "Failing"]].tolist() == [2, 2]
    best, low = fx.best_and_lowest_subjects(fx.subject_stats(small))
    # hand-calculated averages: Python 50, Statistics 50, NumPy 47.5, Pandas 45, Data_Analysis 45 (ties on both ends)
    assert best == ["Python", "Statistics"] and low == ["Pandas", "Data_Analysis"]
    assert s.loc["NumPy", "Average"] == pytest.approx(47.5)
    assert set(s.index) == set(fx.SUBJECTS)


def test_best_subject_exact():
    stats = pd.DataFrame({"Subject": ["X", "Y", "Z"], "Average": [70.0, 70.0, 50.0]})
    assert fx.best_and_lowest_subjects(stats) == (["X", "Y"], ["Z"])


def test_top_students_and_ties(small):
    top = fx.top_students(small, 2)
    assert top["Student_ID"].tolist() == ["A1", "B2"] and top["Rank"].tolist() == [1, 2]
    assert len(fx.top_students(small, 5)) == 4                   # fewer than five students
    tied = fx.analyze(make_df([("T1", "A", "CS", [80] * 5, 90), ("T2", "B", "CS", [80] * 5, 90), ("T3", "C", "CS", [10] * 5, 90)]))
    assert fx.top_students(tied, 5)["Rank"].tolist() == [1, 1, 3]
    assert len(fx.extremes(tied, "Average_Marks", "max")) == 2


def test_grade_distribution_reconciles(small):
    gd = fx.grade_distribution(small)
    assert gd["Students"].sum() == len(small) and gd["Percentage"].sum() == pytest.approx(100)
    assert gd.set_index("Grade").loc["F", "Students"] == 2


def test_department_stats_and_ties(small):
    d = fx.department_stats(small).set_index("Department")
    assert d.loc["CS", "Average_Marks"] == 65 and d.loc["DS", "Average_Marks"] == 30
    assert d.loc["CS", "Pass_Percentage"] == 100 and d.loc["DS", "Failed"] == 2
    assert fx.best_departments(d.reset_index()) == ["CS"]
    both = pd.DataFrame({"Department": ["P", "Q"], "Average_Marks": [60.0, 60.0]})
    assert fx.best_departments(both) == ["P", "Q"]


def test_attendance_stats(small):
    a = fx.attendance_stats(small)
    assert (a["highest"], a["lowest"]) == (90, 60)
    assert a["below_count"] == 2 and a["meeting_count"] == 2
    assert fx.attendance_stats(small.iloc[0:0]) == {}


# ---------------------------------------------------------------- boundaries
@pytest.mark.parametrize("avg,grade", [(0, "F"), (49.99, "F"), (50, "D"), (59.99, "D"), (60, "C"), (69.99, "C"),
                                       (70, "B"), (79.99, "B"), (80, "A"), (89.99, "A"), (90, "A+"), (100, "A+")])
def test_grade_boundaries(avg, grade):
    assert fx.assign_grade(avg) == grade


@pytest.mark.parametrize("mark,grade", [(49.99, "F"), (59.99, "D"), (69.99, "C"), (79.99, "B"), (89.99, "A"), (90, "A+")])
def test_grade_boundaries_through_analyze(mark, grade):
    out = fx.analyze(make_df([("X", "N", "D", [mark] * 5, 80)]))
    assert out.loc[0, "Grade"] == grade


def test_pass_fail_boundaries():
    assert fx.is_passing(40, [35] * 5)                  # average exactly 40, subjects exactly 35
    assert not fx.is_passing(39.99, [40] * 5)
    assert not fx.is_passing(80, [100, 100, 100, 100, 34])   # high average, one subject < 35
    assert not fx.is_passing(45, [34, 50, 50, 45, 46])       # average ok, subject too low
    assert fx.is_passing(50, [35, 35, 35, 75, 70])
    assert fx.analyze(make_df([("X", "N", "D", [40] * 5, 80)])).loc[0, "Result"] == "Pass"


def test_bundled_dataset_valid_and_varied():
    clean, errors = fx.load_csv(fx.DEFAULT_DATASET)
    assert errors == [] and len(clean) >= 20
    df = fx.analyze(clean)
    assert set(df["Result"]) == {"Pass", "Fail"} and (df[fx.ATT_COL] < 75).any() and df[fx.DEPT_COL].nunique() >= 3
    assert {"A+", "A", "B", "C", "D", "F"} <= set(df["Grade"])
    assert df["Total_Marks"].to_numpy() == pytest.approx(clean[fx.SUBJECTS].to_numpy().sum(axis=1))


# ---------------------------------------------------------------- validation
HEADER = ",".join(fx.REQUIRED_COLUMNS)
GOOD = "S1,Ann,CS,80,80,80,80,80,90"


def test_valid_csv_and_single_record():
    clean, errors = fx.load_csv(csv_bytes(f"{HEADER}\n{GOOD}\n"))
    assert errors == [] and len(clean) == 1
    df = fx.analyze(clean)
    m = fx.summary_metrics(df)
    assert m["students"] == 1 and m["pass_pct"] == 100
    assert fx.department_stats(df)["Students"].tolist() == [1]


@pytest.mark.parametrize("text,fragment", [
    ("", "empty"),
    (f"{HEADER}\n", "no student records"),
    ("Student_ID,Name\nS1,Ann\n", "Missing required column"),
    (f"{HEADER}\n{GOOD}\n{GOOD}\n", "Duplicate Student_ID"),
    (f"{HEADER}\nS1,Ann,CS,101,80,80,80,80,90\n", "between 0 and 100"),
    (f"{HEADER}\nS1,Ann,CS,-1,80,80,80,80,90\n", "between 0 and 100"),
    (f"{HEADER}\nS1,Ann,CS,80,80,80,80,80,150\n", "Attendance"),
    (f"{HEADER}\nS1,Ann,CS,,80,80,80,80,90\n", "missing value"),
    (f"{HEADER}\nS1,Ann,CS,abc,80,80,80,80,90\n", "non-numeric"),
    (f"{HEADER}\n,Ann,CS,80,80,80,80,80,90\n", "Student_ID' is empty"),
    (f"{HEADER}\nS1,,CS,80,80,80,80,80,90\n", "Name' is empty"),
])
def test_invalid_csv_is_rejected(text, fragment):
    clean, errors = fx.load_csv(csv_bytes(text))
    assert clean is None and errors
    assert any(fragment.lower() in e.lower() for e in errors), errors


def test_all_problems_reported_together():
    text = f"{HEADER}\nS1,Ann,CS,abc,80,80,80,80,150\nS1,Bob,CS,80,-5,80,80,80,90\n"
    _, errors = fx.load_csv(csv_bytes(text))
    assert len(errors) >= 4


def test_missing_and_malformed_files(tmp_path):
    assert "not found" in fx.load_csv(tmp_path / "nope.csv")[1][0].lower()
    assert fx.load_csv(io.BytesIO(b"\xff\xfe\x00\x81"))[0] is None
    assert fx.load_csv(csv_bytes('a,b\n"unclosed,1\n'))[0] is None
    assert fx.validate_dataframe(None)[0] is None


def test_invalid_input_never_zero_filled():
    clean, errors = fx.load_csv(csv_bytes(f"{HEADER}\nS1,Ann,CS,,80,80,80,80,90\n"))
    assert clean is None and errors


def test_empty_dataframe_helpers():
    empty = fx.analyze(fx.load_csv(csv_bytes(f"{HEADER}\n{GOOD}\n"))[0]).iloc[0:0]
    assert fx.summary_metrics(empty) == {} and fx.top_students(empty).empty
    assert fx.grade_distribution(empty)["Students"].sum() == 0
    assert fx.department_stats(empty).empty and fx.best_departments(fx.department_stats(empty)) == []


# ---------------------------------------------------------------- filtering & exports
def test_filters_do_not_mutate_source():
    df = fx.analyze(fx.load_csv(fx.DEFAULT_DATASET)[0])
    before = df.copy()
    out = fx.filter_students(df, search="aar", departments=["Computer Science"], sort_by="Name", ascending=True)
    assert out["Name"].tolist() == ["Aarav Sharma"] and df.equals(before)
    assert len(fx.filter_students(df, search="S01")) == 10        # S010-S019 (case-insensitive ID search)
    assert set(fx.filter_students(df, results=["Fail"])["Result"]) == {"Fail"}
    assert (fx.filter_students(df, attendance_range=(0, 74.9))[fx.ATT_COL] < 75).all()
    assert fx.filter_students(df, search="zzz").empty
    assert fx.filter_students(df, sort_by="Average_Marks")["Average_Marks"].is_monotonic_decreasing


def test_report_and_csv_content():
    df = fx.analyze(fx.load_csv(fx.DEFAULT_DATASET)[0])
    back = pd.read_csv(io.BytesIO(fx.to_csv_bytes(df)))
    assert len(back) == len(df) and {"Total_Marks", "Average_Marks", "Grade", "Result", "Student_ID"} <= set(back.columns)
    report = fx.build_summary_report(df, "x.csv")
    assert "26 students" in report and "Sara Khan" in report


def test_interpretation_text():
    df = fx.analyze(make_df([("X", "Sam", "D", [30, 90, 90, 90, 90], 50), ("Y", "Tim", "D", [60] * 5, 90)]))
    text = fx.interpret_student(df.iloc[0], df["Average_Marks"].mean())
    assert "fails" in text and "Python" in text and "Attendance" in text


# ---------------------------------------------------------------- GUI (Streamlit AppTest)
def run_app(page=None):
    at = AppTest.from_file(APP, default_timeout=60).run()
    if page:
        at.sidebar.radio(key="page").set_value(page).run()
    return at


def test_gui_loads_dashboard_with_correct_metrics():
    at = run_app()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    expected = fx.summary_metrics(fx.analyze(fx.load_csv(fx.DEFAULT_DATASET)[0]))
    assert metrics["Total Students"] == str(expected["students"])
    assert metrics["Class Average"] == f"{expected['class_average']:.2f}"
    assert metrics["Passing Students"] == str(expected["pass_count"])
    assert metrics["Failing Students"] == str(expected["fail_count"])


@pytest.mark.parametrize("page", ["Dashboard", "Student Records", "Individual Student", "Subject Analysis",
                                  "Department Analysis", "Attendance Analysis", "Grade & Result Analysis",
                                  "Dataset Management", "Reports & Downloads"])
def test_every_page_renders(page):
    at = run_app(page)
    assert not at.exception, [e.value for e in at.exception]


def test_gui_search_filter_and_reset():
    at = run_app("Student Records")
    assert len(at.dataframe[0].value) == 26
    at.text_input(key="f_search").set_value("Sara").run()
    assert len(at.dataframe[0].value) == 1
    assert any("Showing 1 of 26" in m.value for m in at.markdown)
    at.button[0].click().run()                      # Reset filters
    assert len(at.dataframe[0].value) == 26
    at.multiselect(key="f_result").set_value(["Fail"]).run()
    assert len(at.dataframe[0].value) == 3


def test_gui_filters_persist_across_pages_into_report():
    at = run_app("Student Records")
    at.multiselect(key="f_result").set_value(["Fail"]).run()
    at.sidebar.radio(key="page").set_value("Reports & Downloads").run()
    assert not at.exception
    assert any("3 records" in b.proto.label for b in at.get("download_button"))


def test_gui_student_selection_updates_profile():
    at = run_app("Individual Student")
    at.selectbox(key="student_select").set_value("S010").run()
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Grade"] == "A+" and metrics["Average Marks"] == "98.00" and metrics["Total Marks"] == "490"
    at.selectbox(key="student_select").set_value("S012").run()
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Result"] == "Fail" and metrics["Total Marks"] == "165"


def test_gui_dataset_page_shows_checks_and_default():
    at = run_app("Dataset Management")
    assert any("bundled default" in m.value for m in at.markdown)
    assert at.button[0].disabled                    # already on the bundled dataset


def test_gui_uses_invalid_session_data_gracefully():
    """Upload widgets cannot be driven by AppTest; invalid uploads are covered by the validation tests above."""
    clean, errors = fx.load_csv(csv_bytes(f"{HEADER}\nS1,Ann,CS,999,80,80,80,80,90\n"))
    assert clean is None and errors


# ================================================================ v2 regression tests
import main as cli


def ds(text, name="t.csv"):
    return fx.load_dataset(text.encode() if isinstance(text, str) else text, name)


def test_extra_field_in_every_row_is_rejected_not_shifted():
    """Regression: pandas used to treat column 1 as an index and shift every value."""
    res = ds(f"{HEADER}\n{GOOD},1\nS2,Bob,CS,70,70,70,70,70,80,1\n")
    assert not res.ok and res.data is None
    assert "9 fields" in res.errors[0] and "10 fields" in res.errors[0]


def test_short_row_rejected():
    assert not ds(f"{HEADER}\nS1,Ann,CS,80,80,80,80,80\n").ok


def test_bom_and_crlf_accepted():
    assert ds("\ufeff" + f"{HEADER}\r\n{GOOD}\r\n").ok


def test_windows_1252_file_read_with_warning():
    res = ds(f"{HEADER}\nS1,Jos\xe9,CS,80,80,80,80,80,90\n".encode("cp1252"))
    assert res.ok and res.data.loc[0, "Name"] == "José"
    assert any("Windows-1252" in w for w in res.warnings)


def test_binary_and_semicolon_files_get_helpful_messages():
    assert "binary" in ds(b"\x00\x01\xff").errors[0]
    res = ds(HEADER.replace(",", ";") + "\n" + GOOD.replace(",", ";") + "\n")
    assert not res.ok and "separated by" in res.errors[0]


def test_headers_matched_ignoring_case_and_spaces_with_warning():
    res = ds(HEADER.lower().replace("_", " ") + f"\n{GOOD}\n")
    assert res.ok and list(res.data.columns) == fx.REQUIRED_COLUMNS
    assert any("ignoring capitals" in w for w in res.warnings)


def test_repeated_required_column_rejected():
    res = ds(HEADER + f",python\n{GOOD},70\n")
    assert not res.ok and "more than once" in res.errors[0]


def test_duplicate_ids_ignore_case():
    res = ds(f"{HEADER}\n{GOOD}\ns1,Bob,CS,70,70,70,70,70,80\n")
    assert not res.ok and any("Duplicate" in e for e in res.errors)


def test_derived_and_extra_columns_ignored_with_warnings():
    res = ds(f"{HEADER},Total_Marks,Remarks\n{GOOD},1,hi\n")
    assert res.ok and "Total_Marks" not in res.data.columns
    assert len(res.warnings) == 2


def test_checklist_marks_only_failed_checks():
    res = ds(f"{HEADER}\nS1,Ann,CS,150,80,80,80,80,90\n")
    status = dict(res.checklist())
    assert status[fx.CAT_MARKS] is False and status[fx.CAT_MISSING] is True and status[fx.CAT_FILE] is True
    assert all(dict(ds(f"{HEADER}\n{GOOD}\n").checklist()).values())


def test_float_noise_cannot_change_grade():
    out = fx.analyze(make_df([("X", "N", "D", [90.1, 89.9, 90, 90, 90], 80)]))
    assert out.loc[0, "Grade"] == "A+" and out.loc[0, "Total_Marks"] == 450


def test_top_students_keeps_ties_at_cutoff():
    rows = [(f"T{i}", f"N{i}", "CS", [m] * 5, 90) for i, m in enumerate([90, 80, 70, 60, 50, 50, 40])]
    top = fx.top_students(fx.analyze(make_df(rows)), 5)
    assert len(top) == 6 and top["Rank"].tolist() == [1, 2, 3, 4, 5, 5]


def test_needs_attention_reasons():
    df = fx.analyze(make_df([
        ("A", "Fails", "CS", [20] * 5, 90),                       # fails
        ("B", "Close", "CS", [60, 60, 60, 60, 38], 90),            # passes, subject < 40
        ("C", "LowAtt", "CS", [80] * 5, 60),                       # attendance only
        ("D", "Fine", "CS", [80] * 5, 90),                         # nothing
    ]))
    att = fx.needs_attention(df).set_index("Name")
    assert set(att.index) == {"Fails", "Close", "LowAtt"}
    assert att.loc["Fails", "Reasons"] == "Fails the pass rule"
    assert att.loc["Close", "Reasons"] == "Close to failing"
    assert att.loc["LowAtt", "Result"] == "Pass"                   # attendance never changes the result


def test_reconciliation_and_summary_names(small):
    assert fx.reconciliation_check(small)["ok"]
    m = fx.summary_metrics(small)
    assert m["highest_students"] == ["Ann"] and m["lowest_students"] == ["Di"]


def test_cli_runs_and_exports(tmp_path, capsys):
    assert cli.main([], out_dir=tmp_path) == 0
    assert "Class average: 66.85" in capsys.readouterr().out
    assert cli.main(["--export"], out_dir=tmp_path) == 0
    assert {p.name for p in tmp_path.iterdir()} == {"analyzed_students.csv", "subject_analysis.csv",
                                                    "department_analysis.csv", "summary_report.md", "summary_report.html"}
    assert len(pd.read_csv(tmp_path / "analyzed_students.csv")) == 26


def test_cli_rejects_invalid_file(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text(f"{HEADER}\nS1,Ann,CS,999,80,80,80,80,90\n")
    assert cli.main(["--file", str(bad)]) == 1
    assert "between 0 and 100" in capsys.readouterr().out


def test_gui_dashboard_cards_names_and_attention_table():
    at = run_app()
    cards = {m.label: m for m in at.metric}
    assert cards["Highest Student Average"].value == "98.00" and "Sara Khan" in cards["Highest Student Average"].delta
    assert cards["Lowest Student Average"].value == "30.00" and "Manish Das" in cards["Lowest Student Average"].delta
    assert any(s.value == "Students needing attention" for s in at.subheader)
    df = fx.analyze(fx.load_csv(fx.DEFAULT_DATASET)[0])
    assert len(at.dataframe[-1].value) == len(fx.needs_attention(df))


def test_html_report_matches_engine_and_escapes_text():
    df = fx.analyze(fx.load_csv(fx.DEFAULT_DATASET)[0])
    page = fx.build_html_report(df, "my<file>.csv")
    assert page.startswith("<!doctype html>") and "26 students" in page
    assert "Sara Khan" in page and "66.85" in page and "my&lt;file&gt;.csv" in page and "my<file>" not in page
    assert page.count("<table>") == 3 and "Computer Science" in page          # top, departments, attention
    evil = fx.analyze(make_df([("X", "<script>alert(1)</script>", "D", [80] * 5, 90)]))
    assert "<script>" not in fx.build_html_report(evil)
    assert "No data available" in fx.build_html_report(df.iloc[0:0])


def test_gui_reports_page_offers_html_and_markdown_summary():
    at = run_app("Reports & Downloads")
    labels = [b.proto.label for b in at.get("download_button")]
    assert len(labels) == 6 and any("styled HTML" in l for l in labels) and any("Markdown" in l for l in labels)
