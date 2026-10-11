from pathlib import Path
import fitz
path = Path(__file__).resolve().parents[1] / "sample_analytics_report.pdf"
doc = fitz.open()
for title, lines in [
    ("Q2 Retail Analytics", ["Revenue 2025: 1,200,000", "Revenue 2026: 1,440,000", "Orders in Q2: 12,000"]),
    ("Regional Performance", ["North region revenue: 500,000", "South region revenue: 700,000", "Customer retention: 72%"]),
    ("Operating Metrics", ["Return rate: 4.2%", "Average delivery time: 3.1 days", "Survey respondents: 2,500"]),
]:
    page = doc.new_page()
    page.insert_text((55, 70), title, fontsize=22)
    for j, line in enumerate(lines):
        page.insert_text((55, 130 + j * 30), line, fontsize=13)
doc.save(path)
print(path)
