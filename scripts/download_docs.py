"""Download the official IIT Jodhpur documents into data/docs/.
Run this on YOUR machine (the sandbox this project was written in cannot reach iitj.ac.in).
Add more URLs from https://iitj.ac.in/Office-of-Academics/ (see README for the checklist)."""
import csv
import pathlib
import urllib.request

DOCS = pathlib.Path(__file__).resolve().parents[1] / "data" / "docs"
URLS = {
    "btech_regulations_2018.pdf": "https://iitj.ac.in/PageImages/Gallery/04-2025/BTech_Regulations_Latest_21July2018.pdf",
    "pg_regulations_2022_onwards.pdf": "https://iitj.ac.in/PageImages/Gallery/07-2025/Regulation_PG_2022-onwards_20022023.pdf",
    "regulations_2020_onwards.pdf": "https://iitj.ac.in/PageImages/Gallery/03-2025/bioreg-638769690932905139.pdf",
    "academic_calendar_2026_27.pdf": "https://iitj.ac.in/PageImages/Gallery/06-2026/Academic-Calendar-AY-2026-27-639178076336417495.pdf",
    "academic_regulations_page.html": "https://iitj.ac.in/Office-of-Academics/en/Academic-Regulations",
    # TODO(team): open the Academic-Regulations page, right-click the links "Amendment in the Attendance Policy"
    # and "Amendment in the Examination Policy" (AY 2024-25) and add their PDF URLs here.
}

if __name__ == "__main__":
    DOCS.mkdir(parents=True, exist_ok=True)
    for name, url in URLS.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            (DOCS / name).write_bytes(urllib.request.urlopen(req, timeout=60).read())
            print("OK  ", name)
        except Exception as e:  # noqa: BLE001
            print("FAIL", name, e)
