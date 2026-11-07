"""From backend/: uv run python scripts/scan.py --dump or --load-seed."""

import argparse
import asyncio
import logging
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar.scanner import SEED_PATH, catalogue_stats, default_config, dump_seed, load_seed, scan


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect current Oslo-area jobs from NAV.")
    parser.add_argument("--days", type=int, default=14, choices=range(1, 181), metavar="1..180")
    parser.add_argument("--limit", type=int, default=250, help="Target active jobs before deduplication")
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--latest", action="store_true", help="Read the newest NAV page only")
    parser.add_argument("--source", action="append", choices=["nav", "teamtailor", "greenhouse", "lever", "ashby"], help="Select providers; repeat for multiple sources")
    parser.add_argument("--dump", nargs="?", const=SEED_PATH, type=Path, help="Save active jobs to JSON")
    parser.add_argument("--load-seed", nargs="?", const=SEED_PATH, type=Path, help="Import JSON without network requests")
    args = parser.parse_args()
    if args.limit < 1 or args.max_pages < 1:
        parser.error("--limit and --max-pages must be positive")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.load_seed:
        count = load_seed(args.load_seed)
        print(f"Seed loaded. Active unique jobs in database: {count}")
    else:
        sources = {"sources": args.source} if args.source else {}
        result = asyncio.run(scan(default_config(days=args.days, limit=args.limit, max_pages=args.max_pages, latest_only=args.latest, **sources)))
        print(f"Updates processed: {result['updates']}. Active unique jobs: {result['active_unique_jobs']}")
    if args.dump:
        count = dump_seed(args.dump)
        print(f"Seed saved: {count} jobs in {args.dump}")
    print(json.dumps(catalogue_stats(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
