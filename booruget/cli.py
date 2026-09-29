from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import load_credentials
from .downloader import DownloadRunner
from .models import SearchOptions
from .providers import (
    DEFAULT_PROVIDER_IDS,
    PROVIDER_SPECS,
    provider_ids,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="BooruGet",
        description="Search and download posts from multiple booru sites.",
    )
    p.add_argument("search", nargs="*", help="tags, separated by spaces")
    p.add_argument("--gui", action="store_true", help="open the graphical interface")
    p.add_argument("--version", action="version", version=f"BooruGet {__version__}")
    p.add_argument("-o", "--out", default="downloads", help="output directory (default: downloads)")
    p.add_argument("--config", default="booruget.ini", help="credentials/config INI file")

    p.add_argument(
        "--providers",
        nargs="+",
        choices=provider_ids(),
        metavar="ID",
        help="providers to search (use --list-providers to see IDs)",
    )
    p.add_argument(
        "--all-providers",
        action="store_true",
        help="search all built-in providers",
    )
    p.add_argument(
        "--list-providers",
        action="store_true",
        help="list built-in providers and exit",
    )

    # Legacy compatibility switches.
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
    p.add_argument("--max-pages", type=int, default=0, help="search at most N pages per provider (0 = until exhausted)")
    p.add_argument("--workers", type=int, default=4, help="parallel file downloads (1-16)")
    p.add_argument("--dry-run", action="store_true", help="search/filter but do not download")
    p.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    return p


def _selected_providers(args) -> set[str]:
    if args.all_providers:
        selected = set(provider_ids())
    elif args.providers:
        selected = set(args.providers)
    else:
        selected = set(DEFAULT_PROVIDER_IDS)
        if args.nodan:
            selected.discard("danbooru")
        if args.nogel:
            selected.discard("gelbooru")

    if args.danbooru_only:
        return {"danbooru"}
    if args.gelbooru_only:
        return {"gelbooru"}
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_providers:
        for spec in PROVIDER_SPECS:
            flags = []
            if spec.default_enabled:
                flags.append("default")
            if spec.adult_site:
                flags.append("adult")
            suffix = f" ({', '.join(flags)})" if flags else ""
            print(f"{spec.id:12} {spec.label}{suffix}")
        return 0

    if args.gui:
        from .gui import launch_gui
        launch_gui(args.config)
        return 0

    tags = " ".join(args.search).strip()
    if not tags:
        parser.print_help()
        return 2

    selected = _selected_providers(args)
    if not selected:
        parser.error("at least one provider must be enabled")

    any_size = args.anysize or (args.width <= 0 and args.height <= 0)
    options = SearchOptions(
        tags=tags,
        output_dir=args.out,
        use_danbooru="danbooru" in selected,
        use_gelbooru="gelbooru" in selected,
        provider_ids=selected,
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
        stats = DownloadRunner(
            options,
            load_credentials(args.config),
        ).run()
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return (
        1
        if stats.failed and stats.downloaded == 0 and not args.dry_run
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
