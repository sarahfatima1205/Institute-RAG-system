"""Download the official IIT Jodhpur documents into data/docs/.
Run this on YOUR machine (the sandbox this project was written in cannot reach iitj.ac.in).
Add more URLs from https://iitj.ac.in/Office-of-Academics/ (see README for the checklist)."""
import csv
import pathlib
import ssl
import urllib.request

DOCS = pathlib.Path(__file__).resolve().parents[1] / "data" / "docs"
# iitj.ac.in does not send its intermediate certificate (browsers fetch it themselves, Python does not),
# so we add it to the system CAs. Verification stays ON. Source: http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt
SSL_CTX = ssl.create_default_context()
SSL_CTX.load_verify_locations(pathlib.Path(__file__).with_name("sectigo_ov_r36_intermediate.pem"))
URLS = {
    "btech_regulations_2018.pdf": "https://iitj.ac.in/PageImages/Gallery/04-2025/BTech_Regulations_Latest_21July2018.pdf",
    "pg_regulations_2022_onwards.pdf": "https://iitj.ac.in/PageImages/Gallery/07-2025/Regulation_PG_2022-onwards_20022023.pdf",
    "regulations_2020_onwards.pdf": "https://iitj.ac.in/PageImages/Gallery/03-2025/bioreg-638769690932905139.pdf",
    "academic_calendar_2026_27.pdf": "https://iitj.ac.in/PageImages/Gallery/06-2026/Academic-Calendar-AY-2026-27-639178076336417495.pdf",
    "academic_regulations_page.html": "https://iitj.ac.in/Office-of-Academics/en/Academic-Regulations",
    "attendance_amendment_2024_25.pdf": "https://iitj.ac.in/PageImages/Gallery/03-2025/7.1_Circular_51Circular-No.-IITJOAACircular2024-2551682-dated-08-July-2024.pdf",
    "examination_amendment_2024_25.pdf": "https://iitj.ac.in/PageImages/Gallery/03-2025/7.2_Circular_52Circular-No.-IITJOAACircular2024-2552683-dated-08-July-2024.pdf",
    "rules_and_regulations_for_ms.pdf": "https://iitj.ac.in/PageImages/Gallery/03-2025/6_2024-04-17-661f605b54457-1713332315.pdf",
    "curricilum_btech_cse.pdf": "https://iitj.ac.in/PageImages/Gallery/07-2025/Curriculum-BTech-CSE.pdf",
    "cse_courses_details.pdf": "https://iitj.ac.in/PageImages/Gallery/07-2025/CSE-Courses-Details.pdf",
}

if __name__ == "__main__":
    DOCS.mkdir(parents=True, exist_ok=True)
    for name, url in URLS.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            (DOCS / name).write_bytes(urllib.request.urlopen(req, timeout=60, context=SSL_CTX).read())
            print("OK  ", name)
        except Exception as e:  # noqa: BLE001
            print("FAIL", name, e)
