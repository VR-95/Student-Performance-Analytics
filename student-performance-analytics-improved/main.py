"""Command-line version of the analysis (the GUI is app.py).

    python main.py                  analyse the bundled dataset
    python main.py --file my.csv    analyse another CSV
    python main.py --export         also write reports into the outputs/ folder
"""
import argparse

import functions as fx


def main(argv=None, out_dir=None) -> int:
    parser = argparse.ArgumentParser(description="Student Performance Analytics (command line)")
    parser.add_argument("--file", default=str(fx.DEFAULT_DATASET), help="CSV file to analyse")
    parser.add_argument("--export", action="store_true", help="write CSV/Markdown reports to outputs/")
    args = parser.parse_args(argv)

    result = fx.load_dataset(args.file)
    if not result.ok:
        print("The dataset is not valid:")
        for message in result.errors:                      # loop over problems
            print("  -", message)
        return 1
    for note in result.warnings:
        print("Note:", note)
    df = fx.analyze(result.data)
    m = fx.summary_metrics(df)

    students = m["students"]                               # int
    class_average = m["class_average"]                     # float
    source = result.source_name                            # str
    all_pass = m["fail_count"] == 0                        # bool
    print(f"Dataset: {source} ({students} students, {m['subjects']} subjects)")
    print(f"Class average: {class_average:.2f}")
    print(f"Highest average: {m['highest_average']:.2f} ({', '.join(m['highest_students'])})")
    print(f"Lowest average:  {m['lowest_average']:.2f} ({', '.join(m['lowest_students'])})")
    print(f"Pass: {m['pass_count']} ({m['pass_pct']:.1f}%)   Fail: {m['fail_count']} ({m['fail_pct']:.1f}%)")
    if all_pass:                                           # conditional
        print("Every student passed.")
    print("Best subject:", ", ".join(m["best_subjects"]), "| Lowest subject:", ", ".join(m["lowest_subjects"]))

    print("\nSubject statistics")
    for r in fx.subject_stats(df).itertuples():
        print(f"  {r.Subject:<14} avg {r.Average:6.2f}  high {r.Highest:5.1f}  low {r.Lowest:5.1f}  median {r.Median:6.2f}")
    print("\nTop 5 students")
    for r in fx.top_students(df, 5).itertuples():
        print(f"  {r.Rank}. {r.Name} ({r.Student_ID})  average {r.Average_Marks:.2f}  grade {r.Grade}")
    print("\nGrade distribution")
    for r in fx.grade_distribution(df).itertuples():
        print(f"  {r.Grade:<3} {r.Students:>3}  {'#' * r.Students}")

    if args.export:
        folder = fx.Path(out_dir) if out_dir else fx.BASE_DIR / "outputs"
        folder.mkdir(exist_ok=True)
        (folder / "analyzed_students.csv").write_bytes(fx.to_csv_bytes(df))
        (folder / "subject_analysis.csv").write_bytes(fx.to_csv_bytes(fx.subject_stats(df)))
        (folder / "department_analysis.csv").write_bytes(fx.to_csv_bytes(fx.department_stats(df)))
        (folder / "summary_report.html").write_text(fx.build_html_report(df, source), encoding="utf-8")
        (folder / "summary_report.md").write_text(fx.build_summary_report(df, source), encoding="utf-8")
        print(f"\nReports written to {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
