"""Streamlit interface. All calculations come from functions.py - nothing is computed twice here."""
import html

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

import functions as fx

st.set_page_config(page_title="Student Performance Analytics System", page_icon="🎓", layout="wide")
st.markdown("""<style>
.block-container{padding-top:2rem;max-width:1300px}
[data-testid="stMain"] h1{color:#0B4F4A;border-left:8px solid #F2B84B;padding-left:14px}
.banner{background:#E3F2EF;border:1px solid #BFE3DD;border-left:6px solid #0F766E;color:#0B4F4A;border-radius:10px;padding:12px 16px;margin-bottom:12px}
h2,h3{color:#0B4F4A}
[data-testid="stMetric"]{background:#FFFFFF;border:1px solid #D6E6E2;border-top:4px solid #0F766E;border-radius:12px;
  padding:10px 16px;min-height:128px;box-shadow:0 1px 3px rgba(11,79,74,.10)}
[data-testid="stMetricValue"]{color:#0B4F4A}
</style>""", unsafe_allow_html=True)

NAVY, BLUE = "#0B4F4A", "#0F766E"
GRADE_COLORS = {"A+": "#0B4F4A", "A": "#127A6F", "B": "#2A9D8F", "C": "#76C7BB", "D": "#BFE3DD", "F": "#C2410C"}
PAGES = ["Dashboard", "Student Records", "Individual Student", "Subject Analysis", "Department Analysis",
         "Attendance Analysis", "Grade & Result Analysis", "Dataset Management", "Reports & Downloads"]
SORT_MAP = {"Average Marks": "Average_Marks", "Total Marks": "Total_Marks", "Name": fx.NAME_COL, "Attendance": fx.ATT_COL}
FILTER_DEFAULTS = {"f_search": "", "f_dept": [], "f_grade": [], "f_result": [],
                   "f_att": (0.0, 100.0), "f_sort": "Average Marks", "f_order": "Descending"}
DEFAULT_NAME = "students.csv (bundled default)"


# ------------------------------------------------------------------ state helpers
def reset_filters():
    for key, value in FILTER_DEFAULTS.items():
        st.session_state[key] = value


def use_dataset(result, name, is_default):
    st.session_state.update(clean_df=result.data, source_name=name, is_default=is_default,
                            load_warnings=list(result.warnings))
    reset_filters()                      # old filter values may not exist in the new data
    st.session_state.pop("student_select", None)


def init_state():
    if "clean_df" not in st.session_state:
        result = fx.load_dataset(fx.DEFAULT_DATASET)
        if not result.ok:
            st.error("The bundled dataset could not be loaded:")
            for e in result.errors:
                st.write("•", e)
            st.stop()
        use_dataset(result, DEFAULT_NAME, True)
    for key, value in FILTER_DEFAULTS.items():     # keeps filter widgets alive across pages
        st.session_state[key] = st.session_state.get(key, value)


def pretty(df):
    return df.rename(columns=lambda c: c.replace("_", " "))


def show_table(df, **kw):
    """Display a table; averages and percentages always show two decimals (98.00, not 98)."""
    shown = pretty(df).round(2)
    config = {}
    for col in shown.select_dtypes("float").columns:
        two = any(word in col for word in ("Average", "Percentage", "Median"))
        config[col] = st.column_config.NumberColumn(format="%.2f" if two else "%g")
    st.dataframe(shown, hide_index=True, width="stretch", column_config=config, **kw)


def chart(fig, height=360):
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=10, r=10, t=50, b=10), title_font_size=16)
    st.plotly_chart(fig, width="stretch")


def banner(text):
    st.markdown(f'<div class="banner">{text}</div>', unsafe_allow_html=True)


def header(title, text):
    st.title(title)
    st.caption(text)


# ------------------------------------------------------------------ pages
def card(col, label, value, who=None):
    """Metric card; `who` (optional) is shown in small grey text under the number."""
    if who:
        col.metric(label, value, delta=who, delta_color="off", delta_arrow="off")
    else:
        col.metric(label, value)


def page_dashboard(df):
    header("Dashboard", "Overview of the currently loaded dataset.")
    banner(f"<b>Dataset:</b> {html.escape(str(st.session_state['source_name']))} · <b>{len(df)} records</b>")
    m = fx.summary_metrics(df)
    names = lambda lst: ", ".join(lst[:2]) + (f" +{len(lst) - 2}" if len(lst) > 2 else "")
    c = st.columns(3)
    card(c[0], "Total Students", m["students"])
    card(c[1], "Total Subjects", m["subjects"])
    card(c[2], "Class Average", f"{m['class_average']:.2f}")
    c = st.columns(3)
    card(c[0], "Highest Student Average", f"{m['highest_average']:.2f}", names(m["highest_students"]))
    card(c[1], "Lowest Student Average", f"{m['lowest_average']:.2f}", names(m["lowest_students"]))
    card(c[2], "Average Attendance", f"{m['avg_attendance']:.1f}%")
    c = st.columns(3)
    card(c[0], "Passing Students", m["pass_count"])
    card(c[1], "Failing Students", m["fail_count"])
    card(c[2], "Overall Pass Percentage", f"{m['pass_pct']:.1f}%")

    stats = fx.subject_stats(df)
    c1, c2 = st.columns(2)
    with c1:
        chart(px.bar(stats, x="Subject", y="Average", title="Subject-wise Average Marks", text_auto=".1f",
                     color_discrete_sequence=[BLUE]).update_yaxes(range=[0, 100]))
    with c2:
        gd = fx.grade_distribution(df)
        chart(px.bar(gd, x="Grade", y="Students", title="Grade Distribution", text="Students", color="Grade",
                     color_discrete_map=GRADE_COLORS).update_layout(showlegend=False))
    st.caption(f"Best subject: {', '.join(m['best_subjects'])} · Lowest subject: {', '.join(m['lowest_subjects'])}")
    c3, c4 = st.columns(2)
    with c3:
        pf = pd.DataFrame({"Result": ["Pass", "Fail"], "Students": [m["pass_count"], m["fail_count"]]})
        chart(px.pie(pf, names="Result", values="Students", title="Pass / Fail Distribution", hole=0.45,
                     color="Result", color_discrete_map={"Pass": BLUE, "Fail": "#C2410C"}))
    with c4:
        dept = fx.department_stats(df)
        chart(px.bar(dept, x="Department", y="Average_Marks", title="Department-wise Average Marks", text_auto=".1f",
                     color_discrete_sequence=[NAVY]).update_yaxes(range=[0, 100], title="Average Marks"))
    st.subheader("Top-performing students")
    show_table(fx.top_students(df, 5)[["Rank", fx.ID_COL, fx.NAME_COL, fx.DEPT_COL, "Total_Marks", "Average_Marks", "Grade", "Result"]])
    st.caption("Ranked by average marks. Students with equal averages share a rank and are all shown.")
    st.subheader("Students needing attention")
    attention = fx.needs_attention(df)
    if attention.empty:
        st.success("No student fails, is close to failing, or has low attendance.")
    else:
        show_table(attention)
        st.caption(f"Close to failing = passing with an average below {fx.NEAR_FAIL_AVERAGE} or any subject below "
                   f"{fx.NEAR_FAIL_SUBJECT}. Low attendance is reported separately and never changes the academic result.")


def page_records(df):
    header("Student Records", "Search, filter and sort the analyzed student data.")
    c1, c2 = st.columns([2, 1])
    c1.text_input("Search by Student ID or name", key="f_search")
    c2.button("Reset filters", on_click=reset_filters)
    c1, c2, c3 = st.columns(3)
    c1.multiselect("Department (none selected = all)", sorted(df[fx.DEPT_COL].unique()), key="f_dept")
    c2.multiselect("Grade (none selected = all)", fx.GRADE_ORDER, key="f_grade")
    c3.multiselect("Result (none selected = all)", ["Pass", "Fail"], key="f_result")
    c1, c2, c3 = st.columns([2, 1, 1])
    c1.slider("Attendance range (%)", 0.0, 100.0, key="f_att")
    c2.selectbox("Sort by", list(SORT_MAP), key="f_sort")
    c3.selectbox("Order", ["Descending", "Ascending"], key="f_order")
    out = apply_filters(df)
    st.write(f"**Showing {len(out)} of {len(df)} students**")
    if out.empty:
        st.warning("No students match the current filters. Try resetting them.")
        return
    cols = [fx.ID_COL, fx.NAME_COL, fx.DEPT_COL] + fx.SUBJECTS + ["Total_Marks", "Average_Marks", "Grade", "Result", fx.ATT_COL]
    show_table(out[cols])


def apply_filters(df):
    s = st.session_state
    return fx.filter_students(df, s["f_search"], s["f_dept"], s["f_grade"], s["f_result"], s["f_att"],
                              SORT_MAP[s["f_sort"]], s["f_order"] == "Ascending")


def page_student(df):
    header("Individual Student Analysis", "Select a student to see their profile.")
    ids = df[fx.ID_COL].tolist()
    names = dict(zip(df[fx.ID_COL], df[fx.NAME_COL]))
    sid = st.selectbox("Student", ids, key="student_select", format_func=lambda i: f"{i} – {names[i]}")
    match = df[df[fx.ID_COL] == sid]
    if match.empty:
        st.warning("The selected student was not found in the current dataset.")
        return
    row = match.iloc[0]
    class_avg = float(df["Average_Marks"].mean())
    st.subheader(f"{row[fx.NAME_COL]} ({row[fx.ID_COL]})")
    st.caption(f"Department: {row[fx.DEPT_COL]}")
    cols = st.columns(5)
    cols[0].metric("Total Marks", f"{row['Total_Marks']:.0f}")
    cols[1].metric("Average Marks", f"{row['Average_Marks']:.2f}", f"{row['Average_Marks'] - class_avg:+.2f} vs class")
    cols[2].metric("Grade", row["Grade"])
    cols[3].metric("Result", row["Result"])
    cols[4].metric("Attendance", f"{row[fx.ATT_COL]:.0f}%")
    stats = fx.subject_stats(df)
    comp = pd.DataFrame({"Subject": fx.SUBJECTS * 2,
                         "Marks": [row[s] for s in fx.SUBJECTS] + stats["Average"].tolist(),
                         "Series": ["Student"] * len(fx.SUBJECTS) + ["Class average"] * len(fx.SUBJECTS)})
    fig = px.bar(comp, x="Subject", y="Marks", color="Series", barmode="group", title="Subject Marks vs Class Average",
                 color_discrete_map={"Student": NAVY, "Class average": "#9FD3CA"})
    chart(fig.update_yaxes(range=[0, 100]))
    st.subheader("Interpretation")
    st.write(fx.interpret_student(row, class_avg))


def page_subjects(df):
    header("Subject Analysis", "Statistics for each of the five subjects (attendance is not a subject).")
    stats = fx.subject_stats(df)
    best, low = fx.best_and_lowest_subjects(stats)
    c1, c2 = st.columns(2)
    c1.metric("Best-performing subject", ", ".join(best))
    c2.metric("Lowest-performing subject", ", ".join(low))
    chart(px.bar(stats, x="Subject", y="Average", title="Subject Averages", text_auto=".1f",
                 color_discrete_sequence=[BLUE]).update_yaxes(range=[0, 100]))
    show_table(stats)
    st.caption(f"A student passes a subject with at least {fx.PASS_SUBJECT_MARK} marks.")
    subject = st.selectbox("Show mark distribution for", fx.SUBJECTS)
    chart(px.histogram(df, x=subject, nbins=10, range_x=[0, 100], title=f"{subject} Mark Distribution",
                       color_discrete_sequence=[BLUE]).update_layout(yaxis_title="Students", bargap=0.05))


def page_departments(df):
    header("Department Analysis", "Performance by department.")
    dept = fx.department_stats(df)
    best = fx.best_departments(dept)
    st.metric("Best-performing department" + ("s (tie)" if len(best) > 1 else ""), ", ".join(best))
    c1, c2 = st.columns(2)
    with c1:
        chart(px.bar(dept, x="Department", y="Students", title="Students per Department", text="Students",
                     color_discrete_sequence=[NAVY]))
    with c2:
        chart(px.bar(dept, x="Department", y="Average_Marks", title="Average Marks by Department", text_auto=".1f",
                     color_discrete_sequence=[BLUE]).update_yaxes(range=[0, 100], title="Average Marks"))
    long = dept.melt(id_vars="Department", value_vars=["Passed", "Failed"], var_name="Result", value_name="Count")
    chart(px.bar(long, x="Department", y="Count", color="Result", barmode="group", title="Pass / Fail by Department",
                 color_discrete_map={"Passed": BLUE, "Failed": "#C2410C"}))
    show_table(dept)


def page_attendance(df):
    header("Attendance Analysis", f"Attendance threshold: {fx.ATTENDANCE_THRESHOLD}%.")
    a = fx.attendance_stats(df)
    cols = st.columns(5)
    cols[0].metric("Average", f"{a['average']:.1f}%")
    cols[1].metric("Highest", f"{a['highest']:.0f}%")
    cols[2].metric("Lowest", f"{a['lowest']:.0f}%")
    cols[3].metric(f"Below {fx.ATTENDANCE_THRESHOLD}%", a["below_count"])
    cols[4].metric(f"At least {fx.ATTENDANCE_THRESHOLD}%", a["meeting_count"])
    chart(px.histogram(df, x=fx.ATT_COL, nbins=10, range_x=[0, 100], title="Attendance Distribution",
                       color_discrete_sequence=[BLUE]).update_layout(yaxis_title="Students", xaxis_title="Attendance (%)"))
    st.subheader(f"Students below {fx.ATTENDANCE_THRESHOLD}% attendance")
    if a["below_count"]:
        show_table(a["below_students"][[fx.ID_COL, fx.NAME_COL, fx.DEPT_COL, fx.ATT_COL, "Average_Marks", "Result"]])
    else:
        st.success("Every student meets the attendance threshold.")
    st.subheader("Attendance vs average marks")
    chart(px.scatter(df, x=fx.ATT_COL, y="Average_Marks", hover_name=fx.NAME_COL, title="Attendance vs Average Marks",
                     color_discrete_sequence=[NAVY]))
    if len(df) >= 3 and df[fx.ATT_COL].std() > 0 and df["Average_Marks"].std() > 0:
        r = np.corrcoef(df[fx.ATT_COL], df["Average_Marks"])[0, 1]
        st.write(f"Correlation coefficient: **{r:.2f}**")
    st.caption("Correlation does not establish causation. Attendance does not change the academic pass/fail result.")


def page_grades(df):
    header("Grade & Result Analysis", "Grade bands, pass/fail results and the students in each category.")
    m = fx.summary_metrics(df)
    c1, c2 = st.columns(2)
    c1.metric("Passed", f"{m['pass_count']} ({m['pass_pct']:.1f}%)")
    c2.metric("Failed", f"{m['fail_count']} ({m['fail_pct']:.1f}%)")
    gd = fx.grade_distribution(df)
    chart(px.bar(gd, x="Grade", y="Students", text="Students", color="Grade", color_discrete_map=GRADE_COLORS,
                 title="Grade Distribution").update_layout(showlegend=False))
    show_table(gd)
    rec = fx.reconciliation_check(df)
    st.caption(f"✔ Grade counts ({rec['grade_total']}) and pass + fail counts ({rec['pass_total']} + {rec['fail_total']}) "
               f"reconcile with the {rec['students']} analyzed students." if rec["ok"] else "⚠ Counts do not reconcile.")
    st.caption("Grade F with result Pass is possible: an average of 40–49.99 passes but is graded F under the project rules.")
    grade = st.selectbox("Students with grade", fx.GRADE_ORDER)
    members = df[df["Grade"] == grade]
    if members.empty:
        st.info(f"No students have grade {grade}.")
    else:
        show_table(members.sort_values("Average_Marks", ascending=False)[
            [fx.ID_COL, fx.NAME_COL, fx.DEPT_COL, "Average_Marks", "Grade", "Result"]])
    c1, c2 = st.columns(2)
    cols = [fx.ID_COL, fx.NAME_COL, "Average_Marks", "Total_Marks"]
    c1.subheader("Highest performer(s)")
    with c1:
        show_table(fx.extremes(df, "Average_Marks", "max")[cols])
    c2.subheader("Lowest performer(s)")
    with c2:
        show_table(fx.extremes(df, "Average_Marks", "min")[cols])


def show_checklist(result):
    for name, passed in result.checklist():
        st.write(("✅ " if passed else "❌ ") + name)


TEMPLATE_CSV = (",".join(fx.REQUIRED_COLUMNS) + "\nS001,Example Student,Computer Science,80,75,82,78,85,92\n").encode("utf-8")


def page_dataset():
    header("Dataset Management", "Load, validate and inspect data. The bundled file is never overwritten.")
    ss = st.session_state
    kind = "bundled default dataset" if ss["is_default"] else "uploaded file"
    banner(f"<b>Active dataset:</b> {html.escape(str(ss['source_name']))} · {len(ss['clean_df'])} records · {kind}")
    if st.button("Return to bundled dataset", disabled=ss["is_default"]):
        result = fx.load_dataset(fx.DEFAULT_DATASET)
        if not result.ok:
            st.error("; ".join(result.errors))
        else:
            use_dataset(result, DEFAULT_NAME, True)
            st.rerun()
    for note in ss.get("load_warnings", []):
        st.warning(note)
    st.markdown(f"**Required columns:** `{'`, `'.join(fx.REQUIRED_COLUMNS)}`")
    st.download_button("Download a blank CSV template", TEMPLATE_CSV, file_name="students_template.csv", mime="text/csv")
    up = st.file_uploader("Upload a CSV file", type=["csv"])
    if up is not None:
        result = fx.load_dataset(up, up.name)
        st.subheader("Validation checks")
        show_checklist(result)
        if result.ok:
            st.success(f"'{up.name}' passed validation: {len(result.data)} records.")
            for note in result.warnings:
                st.warning(note)
            if st.button("Use this dataset for analysis"):
                use_dataset(result, up.name, False)
                st.rerun()
        else:
            st.error(f"'{up.name}' is not valid and will not be used. Please fix {len(result.issues)} problem(s):")
            for e in result.errors:
                st.write("•", e)
        if result.raw_preview is not None:
            st.caption(f"Uploaded file preview: {result.raw_rows} rows, {result.raw_columns} columns.")
            st.dataframe(result.raw_preview, hide_index=True, width="stretch")
    st.subheader("Active dataset checks")
    clean = ss["clean_df"]
    checks = pd.DataFrame({
        "Check": ["Records", "Columns", "Missing values", "Duplicate Student IDs", "Marks outside 0–100", "Attendance outside 0–100"],
        "Result": [len(clean), clean.shape[1], int(clean.isna().sum().sum()), int(clean[fx.ID_COL].duplicated().sum()),
                   int(((clean[fx.SUBJECTS] < 0) | (clean[fx.SUBJECTS] > 100)).sum().sum()),
                   int(((clean[fx.ATT_COL] < 0) | (clean[fx.ATT_COL] > 100)).sum())]})
    st.dataframe(checks, hide_index=True, width="stretch")
    st.subheader("Preview")
    st.dataframe(pretty(clean), hide_index=True, width="stretch")


def page_reports(df):
    header("Reports & Downloads", "Downloads reflect the active dataset; source files are never modified.")
    name = "default" if st.session_state["is_default"] else st.session_state["source_name"].rsplit(".", 1)[0]
    filtered = apply_filters(df)
    items = [
        ("Complete analyzed dataset (CSV)", fx.to_csv_bytes(df), f"{name}_analyzed_students.csv", "text/csv"),
        (f"Filtered student dataset (CSV) – {len(filtered)} records", fx.to_csv_bytes(filtered), f"{name}_filtered_students.csv", "text/csv"),
        ("Subject-wise analysis (CSV)", fx.to_csv_bytes(fx.subject_stats(df)), f"{name}_subject_analysis.csv", "text/csv"),
        ("Department-wise analysis (CSV)", fx.to_csv_bytes(fx.department_stats(df)), f"{name}_department_analysis.csv", "text/csv"),
        ("Summary report – styled HTML (opens in a browser, printable)",
         fx.build_html_report(df, st.session_state["source_name"]).encode("utf-8"), f"{name}_summary_report.html", "text/html"),
        ("Summary report – Markdown", fx.build_summary_report(df, st.session_state["source_name"]).encode("utf-8"),
         f"{name}_summary_report.md", "text/markdown"),
    ]
    for i, (label, data, fname, mime) in enumerate(items):
        st.download_button(f"Download: {label}", data, file_name=fname, mime=mime, key=f"dl_{i}")
    st.caption("The filtered dataset uses the filters currently set on the Student Records page.")


# ------------------------------------------------------------------ main
def main():
    init_state()
    st.sidebar.title("🎓 Student Performance Analytics")
    st.sidebar.caption("Built with Python, NumPy and Pandas")
    page = st.sidebar.radio("Navigate", PAGES, key="page")
    st.sidebar.divider()
    st.sidebar.caption(f"Dataset: {st.session_state['source_name']}")
    if page == "Dataset Management":
        return page_dataset()
    df = fx.analyze(st.session_state["clean_df"])
    if df.empty:
        st.warning("No valid records are loaded. Go to Dataset Management.")
        return
    {"Dashboard": page_dashboard, "Student Records": page_records, "Individual Student": page_student,
     "Subject Analysis": page_subjects, "Department Analysis": page_departments,
     "Attendance Analysis": page_attendance, "Grade & Result Analysis": page_grades,
     "Reports & Downloads": page_reports}[page](df)


main()
