import pymupdf as fitz
from insight_generator.service import run_job
from insight_generator.export import to_excel, to_markdown

def test_demo_and_resume(tmp_path):
    path = tmp_path / "small.pdf"
    doc = fitz.open()
    for n in range(2):
        page = doc.new_page()
        page.insert_text((70, 70), f"Reported revenue in region {n + 1} was 120 units")
    doc.save(path)
    first = run_job(path, data_dir=tmp_path / "db")
    second = run_job(path, data_dir=tmp_path / "db")
    assert first.job_id == second.job_id
    assert len(first.pages) == 2
    assert all(p.status == "accepted" for p in first.pages)
    assert "Page 1" in to_markdown(first)
    assert len(to_excel(first)) > 100

def test_image_only_requires_review(tmp_path):
    path = tmp_path / "blank.pdf"
    doc = fitz.open(); doc.new_page(); doc.save(path)
    result = run_job(path, data_dir=tmp_path / "db")
    assert result.review_pages == [1]


def test_analytical_end_to_end(tmp_path):
    path = tmp_path / "metrics.pdf"
    doc = fitz.open()
    pg = doc.new_page()
    pg.insert_text((60,70), "Revenue 2025: 1,200,000")
    pg.insert_text((60,100), "Revenue 2026: 1,440,000")
    doc.save(path)
    job = run_job(path, data_dir=tmp_path / "db")
    assert len(job.analytical_insights) == 1
    assert "20.0%" in job.analytical_insights[0].observation
    assert "Calculated Insights" in __import__("pandas").ExcelFile(__import__("io").BytesIO(to_excel(job))).sheet_names
