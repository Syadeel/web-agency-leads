"""
Lead Generation Pipeline: Scrape → Validate → DB → Export.

Usage:
    python pipeline.py          # Full pipeline
    python pipeline.py --scrape-only   # Only scrape, skip DB
    python pipeline.py --db-only       # Only load CSV to DB + export
"""
import subprocess
import sys
import os

PIPELINE_STEPS = [
    ("scraper.py",         "Scraping leads from Google via SerpAPI"),
    ("load_leads_to_db.py","Loading scraped leads into Supabase"),
    ("export_leads.py",    "Exporting DB leads to CSV"),
]


def run_step(script, description):
    print(f"\n{'='*60}")
    print(f"[{PIPELINE_STEPS.index((script,description))+1}/{len(PIPELINE_STEPS)}] {description}...")
    print(f"{'='*60}")

    script_path = os.path.join(os.path.dirname(__file__), script)
    result = subprocess.run(
        [sys.executable, script_path],
        capture_output=True, text=True, timeout=300
    )

    # Print output lines (skip empty)
    for line in result.stdout.splitlines():
        if line.strip():
            print(f"  {line}")
    if result.stderr:
        for line in result.stderr.splitlines():
            if line.strip():
                print(f"  [!] {line}")

    if result.returncode != 0:
        print(f"  [!!!] {script} FAILED with code {result.returncode}")
        return False

    print(f"  [OK] {script} completed successfully")
    return True


def main():
    print("=" * 60)
    print("  LEAD GENERATION PIPELINE")
    print("=" * 60)

    args = set(sys.argv[1:])
    scrape_only = "--scrape-only" in args
    db_only = "--db-only" in args

    all_ok = True

    if db_only:
        # Skip scraping, start from loading
        steps = PIPELINE_STEPS[1:]
    elif scrape_only:
        steps = PIPELINE_STEPS[:1]
    else:
        steps = PIPELINE_STEPS

    for script, description in steps:
        if not run_step(script, description):
            all_ok = False
            print(f"\n[-] Pipeline stopped at: {script}")
            break

    print(f"\n{'='*60}")
    if all_ok:
        print("  PIPELINE COMPLETE ✅")
    else:
        print("  PIPELINE FINISHED WITH ERRORS ⚠️")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
