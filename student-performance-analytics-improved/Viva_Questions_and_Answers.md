# Viva Questions and Answers

1. **What does the project do?** Reads student marks from a CSV, validates them, calculates total, average, grade and pass/fail per student, and shows class, subject, department and attendance analysis in a Streamlit dashboard.
2. **Where is NumPy used?** In `analyze()` the five subject columns become a NumPy matrix (`to_numpy`); `marks.sum(axis=1)` gives all totals. NumPy also provides `np.mean/median/max/min` for subject statistics, `np.corrcoef` for correlation, `np.isclose` for tie detection, `np.isfinite` and boolean masks in validation.
3. **Where is Pandas used?** `read_csv`, DataFrames, boolean filtering, sorting, `groupby` for departments, `value_counts` for grades, `to_csv` for downloads.
4. **How is the grade decided?** `assign_grade(average)` checks 90, 80, 70, 60, 50 in order and returns A+, A, B, C or D; anything lower is F.
5. **What are the pass rules?** Average ≥ 40 **and** every subject ≥ 35. They are project-defined, not given by the assignment.
6. **Why can a student have grade F and still pass?** F means average below 50; passing needs only 40. S011 (average 40) and S026 (41) show this.
7. **Why does S009 fail with an average of 45.6?** Python mark is 33, below the subject minimum of 35.
8. **Which student is exactly on the A+ boundary?** S014 (every mark 90, average 90.0 → A+).
9. **Where are loops, conditions and functions used?** Loops: `analyze`, `subject_stats`, `is_passing`, validation per column. Conditions: `assign_grade`, `is_passing`, validation. Functions: everything reusable lives in `functions.py`.
10. **Why keep calculations out of `app.py`?** So every page, the command line and the tests use identical results and the logic can be tested without the GUI.
11. **How are blank marks handled?** Rejected with the CSV row numbers; never replaced by zero, because that would silently lower a student's grade.
12. **What bug can happen when every CSV row has one extra field?** pandas treats the first column as the index and shifts all values. The loader counts fields per row and rejects such files; there is a regression test.
13. **What does the validation checklist show?** Eight checks (file readable, columns present, has records, no missing values, numeric values, unique IDs, marks in range, attendance in range) with ✅/❌.
14. **How are ties handled?** Equal averages share a rank and all tied students at the cut-off are shown; `extremes`, `best_departments` and `best_and_lowest_subjects` return every tied item. `np.isclose` avoids floating-point mismatches.
15. **Why round totals to 6 decimals?** To remove floating-point noise (e.g. 449.99999999) that could push a student into the wrong grade band.
16. **Does attendance affect the result?** No; it is only reported. Low attendance appears as an extra reason in *Students needing attention*.
17. **Does correlation prove attendance causes marks?** No. The scatter page says correlation does not establish causation.
18. **How is an uploaded file kept from damaging the bundled data?** It is validated in memory, used only after you click the button, never written to disk, and "Return to bundled dataset" restores the original.
19. **How did you test the GUI?** Streamlit `AppTest` for every page and interaction, plus a real-browser script that uploads files and downloads all reports.
20. **What would you improve next?** Excel (.xlsx) upload, configurable subject list, per-term comparisons.
