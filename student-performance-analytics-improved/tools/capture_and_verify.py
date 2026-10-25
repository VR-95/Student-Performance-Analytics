"""Optional helper: drives the real app in headless Chromium, verifies the main flows and saves screenshots.

Needs:  pip install playwright   and   python -m playwright install chromium
Run:    python tools/capture_and_verify.py
"""
import io
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "screenshots"
PORT = 8765
URL = f"http://localhost:{PORT}"
PAGES = [("Dashboard", "01_dashboard"), ("Student Records", "02_student_records"),
         ("Individual Student", "03_individual_student"), ("Subject Analysis", "04_subject_analysis"),
         ("Department Analysis", "05_department_analysis"), ("Attendance Analysis", "06_attendance_analysis"),
         ("Grade & Result Analysis", "07_grade_result_analysis"), ("Dataset Management", "08_dataset_management"),
         ("Reports & Downloads", "09_reports_downloads")]
HEADER = "Student_ID,Name,Department,Python,Statistics,NumPy,Pandas,Data_Analysis,Attendance"
results = []


def check(name, condition):
    results.append((name, bool(condition)))
    print(("PASS  " if condition else "FAIL  ") + name)


def main():
    SHOTS.mkdir(exist_ok=True)
    server = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true",
                               "--server.port", str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                urllib.request.urlopen(URL + "/_stcore/health", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        tmp = Path(tempfile.mkdtemp())
        bad, good = tmp / "invalid_marks.csv", tmp / "three_students.csv"
        bad.write_text(f"{HEADER}\nS1,Ann,CS,150,80,80,80,80,90\nS1,Bob,CS,abc,80,80,80,80,90\n")
        good.write_text(f"{HEADER}\nU1,Uma,Physics,90,90,90,90,90,95\nU2,Vik,Physics,50,50,50,50,50,80\nU3,Wen,Chemistry,30,30,30,30,30,60\n")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1400, "height": 1900}, accept_downloads=True)
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(URL)
            page.get_by_role("heading", name="Dashboard").wait_for(timeout=30000)

            def settle():
                """Wait until charts/tables have finished loading."""
                time.sleep(1)
                page.wait_for_function("document.querySelectorAll('[data-testid=\"stSkeleton\"]').length === 0", timeout=20000)
                time.sleep(1.5)

            def go(name):
                page.locator('[data-testid="stSidebar"]').get_by_text(name, exact=True).click()
                page.get_by_role("heading", name=name.replace("&", "&"), exact=False).first.wait_for(timeout=15000)
                settle()

            for name, shot in PAGES:
                go(name)
                check(f"page renders: {name}", page.locator('[data-testid="stException"]').count() == 0)
                if name == "Individual Student":
                    page.get_by_text("Interpretation").wait_for()
                page.screenshot(path=str(SHOTS / f"{shot}.png"))
                if name == "Dashboard":
                    check("dashboard shows 26 students", page.get_by_text("26", exact=True).first.is_visible())

            # filters
            go("Student Records")
            page.get_by_label("Search by Student ID or name").fill("Sara")
            page.keyboard.press("Enter")
            page.get_by_text("Showing 1 of 26 students").wait_for(timeout=10000)
            check("search filter shows 1 of 26", True)
            page.screenshot(path=str(SHOTS / "02b_search_filter.png"))

            # downloads honour the filter
            go("Reports & Downloads")
            files = {}
            for label in ["Complete analyzed", "Filtered student", "Subject-wise", "Department-wise", "styled HTML", "Summary report – Markdown"]:
                with page.expect_download() as d:
                    page.get_by_role("button", name=re.compile(label)).click()
                path = tmp / d.value.suggested_filename
                d.value.save_as(path)
                files[label] = path
            full = pd.read_csv(files["Complete analyzed"])
            filt = pd.read_csv(files["Filtered student"])
            check("download: complete CSV has 26 rows + derived columns",
                  len(full) == 26 and {"Total_Marks", "Average_Marks", "Grade", "Result"} <= set(full.columns))
            check("download: filtered CSV has the 1 searched student", len(filt) == 1 and filt.loc[0, "Name"] == "Sara Khan")
            check("download: subject CSV has 5 subjects", len(pd.read_csv(files["Subject-wise"])) == 5)
            check("download: department CSV has 4 departments", len(pd.read_csv(files["Department-wise"])) == 4)
            check("download: Markdown summary mentions students", "26 students" in files["Summary report – Markdown"].read_text())
            page_html = files["styled HTML"].read_text(encoding="utf-8")
            check("download: HTML report is a styled page with the data", "<style>" in page_html and "Sara Khan" in page_html and "26 students" in page_html)

            # invalid upload
            go("Dataset Management")
            page.locator('input[type="file"]').set_input_files(str(bad))
            page.get_by_text("is not valid and will not be used").wait_for(timeout=15000)
            check("invalid upload rejected with explanation", page.get_by_text("between 0 and 100").first.is_visible())
            time.sleep(1)
            settle()
            page.screenshot(path=str(SHOTS / "10_invalid_upload_rejected.png"))
            go("Dashboard")
            check("rejected file not used (still 26 students)", page.get_by_text("students.csv (bundled default)").first.is_visible())

            # valid upload, then use it
            go("Dataset Management")
            page.locator('input[type="file"]').set_input_files(str(good))
            page.get_by_text("passed validation").wait_for(timeout=15000)
            page.get_by_role("button", name="Use this dataset for analysis").click()
            time.sleep(2)
            go("Dashboard")
            page.get_by_text("three_students.csv").first.wait_for(timeout=10000)
            check("uploaded dataset drives the dashboard (3 records)", page.get_by_text("3 records").first.is_visible())
            settle()
            page.screenshot(path=str(SHOTS / "11_uploaded_dataset_dashboard.png"))

            # reset
            go("Dataset Management")
            page.get_by_role("button", name="Return to bundled dataset").click()
            time.sleep(2)
            go("Dashboard")
            check("reset restores bundled dataset (26 records)", page.get_by_text("26 records").first.is_visible())
            check("no JavaScript errors", not errors)
            browser.close()
    finally:
        server.terminate()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} browser checks passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
