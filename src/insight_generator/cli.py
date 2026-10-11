import argparse
from pathlib import Path
from .service import run_job
from .export import to_markdown, to_excel


def main():
    parser = argparse.ArgumentParser(description="Auditable LangGraph PDF insight generator")
    parser.add_argument("pdf")
    parser.add_argument("--provider", choices=["demo", "openai"], default="demo")
    parser.add_argument("--model", default=None)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int)
    parser.add_argument("--force", action="store_true", help="Reprocess cached pages")
    parser.add_argument("--output", type=Path, default=Path("data/exports"))
    args = parser.parse_args()
    job = run_job(args.pdf, provider=args.provider, model=args.model, start=args.start, end=args.end, force=args.force)
    args.output.mkdir(parents=True, exist_ok=True)
    base = args.output / job.job_id
    base.with_suffix(".json").write_text(job.model_dump_json(indent=2), encoding="utf-8")
    base.with_suffix(".md").write_text(to_markdown(job), encoding="utf-8")
    base.with_suffix(".xlsx").write_bytes(to_excel(job))
    print(f"Saved {len(job.pages)} pages | review={job.review_pages} | files={base}.*")

if __name__ == "__main__":
    main()
