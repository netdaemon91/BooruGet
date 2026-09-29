from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import load_credentials
from .downloader import DownloadRunner
from .models import SearchOptions


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="BooruGet",
        description="Download posts from Danbooru and Gelbooru by tag search.",
    )
    p.add_argument("search", nargs="*", help="tags, separated by spaces")
    p.add_argument("--gui", action="store_true", help="open the graphical interface")
    p.add_argument("--version", action="version", version=f"BooruGet {__version__}")
    p.add_argument("-o", "--out", default="downloads", help="output directory (default: downloads)")
    p.add_argument("--config", default="booruget.ini", help="credentials/config INI file")
    p.add_argument("--nodan", action="store_true", help="disable Danbooru")
    p.add_argument("--nogel", action="store_true", help="disable Gelbooru")
    p.add_argument("--danbooru-only", action="store_true", help="only use Danbooru")
    p.add_argument("--gelbooru-only", action="store_true", help="only use Gelbooru")
    p.add_argument("-a", "--anysize", action="store_true", help="ignore resolution/aspect-ratio filter")
    p.add_argument("-w", "--width", type=int, default=-1, help="target/minimum width")
    p.add_argument("-t", "--height", type=int, default=-1, help="target/minimum height")
    p.add_argument("-e", "--error", type=float, default=0.05, help="size/aspect tolerance, e.g. 0.05")
    p.add_argument("--nsfw", action="store_true", help="allow all ratings instead of general-only")
    p.add_argument(
        "--ratings",
        nargs="+",
        choices=("general", "sensitive", "questionable", "explicit"),
        help="explicitly choose allowed ratings",
    )
    p.add_argument("--max-results", type=int, default=0, help="stop after N accepted posts (0 = unlimited)")
    p.add_argument("--max-pages", type=int, default=0, help="search at most N API pages per provider (0 = until exhausted)")
    p.add_argument("--workers", type=int, default=4, help="parallel file downloads (1-16)")
    p.add_argument("--dry-run", action="store_true", help="search/filter but do not download")
    p.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.gui:
        from .gui import launch_gui
        launch_gui(args.config)
        return 0

    tags = " ".join(args.search).strip()
    if not tags:
        build_parser().print_help()
        return 2

    use_dan = not args.nodan
    use_gel = not args.nogel
    if args.danbooru_only:
        use_dan, use_gel = True, False
    if args.gelbooru_only:
        use_dan, use_gel = False, True

    any_size = args.anysize or (args.width <= 0 and args.height <= 0)
    options = SearchOptions(
        tags=tags,
        output_dir=args.out,
        use_danbooru=use_dan,
        use_gelbooru=use_gel,
        any_size=any_size,
        target_width=args.width,
        target_height=args.height,
        size_error=args.error,
        allow_nsfw=args.nsfw,
        allowed_ratings=set(args.ratings) if args.ratings else None,
        max_results=max(0, args.max_results),
        max_pages=max(0, args.max_pages),
        workers=max(1, min(16, args.workers)),
        verbose=args.verbose,
        dry_run=args.dry_run,
    )
    try:
        stats = DownloadRunner(options, load_credentials(args.config)).run()
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 1 if stats.failed and stats.downloaded == 0 and not args.dry_run else 0


if __name__ == "__main__":
    raise SystemExit(main())
