#!/usr/bin/env python3
"""Read-only helper for common HEPData-CLI fetch workflows."""

from __future__ import annotations

import argparse
import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path


ID_TYPES = ("hepdata", "inspire", "arxiv")
FORMATS = ("csv", "root", "yaml", "yoda", "yoda1", "yoda.h5", "json")


def run_command(args: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=True,
            text=True,
            capture_output=capture,
        )
    except FileNotFoundError:
        raise SystemExit(
            "hepdata-cli was not found. Install it with: python3 -m pip install --user hepdata-cli"
        )
    except subprocess.CalledProcessError as exc:
        if capture:
            if exc.stdout:
                print(exc.stdout, end="", file=sys.stdout)
            if exc.stderr:
                print(exc.stderr, end="", file=sys.stderr)
        raise SystemExit(exc.returncode)


def parse_ids(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []

    try:
        value = ast.literal_eval(stripped)
    except (SyntaxError, ValueError):
        value = None

    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []

    candidates = re.findall(r"[A-Za-z0-9_.:/-]+", stripped)
    ignored = {
        "INFO",
        "DEBUG",
        "WARNING",
        "ERROR",
        "hepdata-cli",
    }
    return [token for token in candidates if token not in ignored]


def cli_path(cli_bin: str) -> str:
    found = shutil.which(cli_bin)
    if found:
        return found
    if Path(cli_bin).exists():
        return cli_bin
    raise SystemExit(
        f"{cli_bin!r} was not found. Install it with: python3 -m pip install --user hepdata-cli"
    )


def build_find_command(args: argparse.Namespace) -> list[str]:
    command = [args.cli_bin]
    if args.verbose:
        command.append("--verbose")
    command.extend(["find", args.query])
    if args.keyword:
        command.extend(["--keyword", args.keyword])
    if args.ids:
        command.extend(["--ids", args.ids])
    return command


def build_names_command(args: argparse.Namespace, ids: list[str] | None = None) -> list[str]:
    command = [args.cli_bin]
    if args.verbose:
        command.append("--verbose")
    command.append("fetch-names")
    command.extend(ids if ids is not None else args.record_ids)
    command.extend(["--ids", args.ids])
    return command


def build_download_command(args: argparse.Namespace, ids: list[str] | None = None) -> list[str]:
    command = [args.cli_bin]
    if args.verbose:
        command.append("--verbose")
    command.append("download")
    command.extend(ids if ids is not None else args.record_ids)
    command.extend(["--file-format", args.file_format, "--ids", args.ids])
    if args.table_name:
        command.extend(["--table-name", args.table_name])
    if args.download_dir:
        command.extend(["--download-dir", args.download_dir])
    return command


def cmd_check(args: argparse.Namespace) -> int:
    args.cli_bin = cli_path(args.cli_bin)
    completed = run_command([args.cli_bin, "--version"], capture=True)
    version = completed.stdout.strip() or completed.stderr.strip() or "hepdata-cli is installed"
    print(version)
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    args.cli_bin = cli_path(args.cli_bin)
    run_command(build_find_command(args))
    return 0


def cmd_names(args: argparse.Namespace) -> int:
    args.cli_bin = cli_path(args.cli_bin)
    run_command(build_names_command(args))
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    args.cli_bin = cli_path(args.cli_bin)
    run_command(build_download_command(args))
    return 0


def cmd_search_download(args: argparse.Namespace) -> int:
    args.cli_bin = cli_path(args.cli_bin)
    find_args = argparse.Namespace(**vars(args))
    find_result = run_command(build_find_command(find_args), capture=True)
    record_ids = parse_ids(find_result.stdout)
    if not record_ids:
        print("No IDs were returned by hepdata-cli find.", file=sys.stderr)
        return 1

    print("IDs:", " ".join(record_ids), file=sys.stderr)
    run_command(build_download_command(args, record_ids))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Read-only wrapper around HEPData-CLI for search, table-name lookup, and download."
    )
    root.add_argument("--cli-bin", default="hepdata-cli", help="Path or command name for hepdata-cli.")
    subparsers = root.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Check that hepdata-cli is installed.")
    check.set_defaults(func=cmd_check)

    find = subparsers.add_parser("find", help="Search HEPData records.")
    find.add_argument("query", help="HEPData search query.")
    find.add_argument("--keyword", "-kw", help="Metadata keyword to return.")
    find.add_argument("--ids", "-i", choices=ID_TYPES, help="Return IDs of this type.")
    find.add_argument("--verbose", action="store_true")
    find.set_defaults(func=cmd_find)

    names = subparsers.add_parser("names", help="Fetch table names for records.")
    names.add_argument("record_ids", nargs="+", help="Record IDs.")
    names.add_argument("--ids", "-i", choices=ID_TYPES, default="hepdata", help="Input ID type.")
    names.add_argument("--verbose", action="store_true")
    names.set_defaults(func=cmd_names)

    download = subparsers.add_parser("download", help="Download records or one named table.")
    download.add_argument("record_ids", nargs="+", help="Record IDs.")
    download.add_argument("--ids", "-i", choices=ID_TYPES, default="hepdata", help="Input ID type.")
    download.add_argument("--format", "-f", dest="file_format", choices=FORMATS, default="csv")
    download.add_argument("--table-name", "-t", help="Download only this HEPData table name.")
    download.add_argument("--download-dir", "-d", default="hepdata-downloads")
    download.add_argument("--verbose", action="store_true")
    download.set_defaults(func=cmd_download)

    search_download = subparsers.add_parser(
        "search-download",
        help="Search for IDs, then download matching records. Requires --ids.",
    )
    search_download.add_argument("query", help="HEPData search query.")
    search_download.add_argument("--ids", "-i", choices=ID_TYPES, required=True, help="ID type for search and download.")
    search_download.add_argument("--keyword", "-kw", help="Metadata keyword to return. Usually omit for downloads.")
    search_download.add_argument("--format", "-f", dest="file_format", choices=FORMATS, default="csv")
    search_download.add_argument("--table-name", "-t", help="Download only this HEPData table name.")
    search_download.add_argument("--download-dir", "-d", default="hepdata-downloads")
    search_download.add_argument("--verbose", action="store_true")
    search_download.set_defaults(func=cmd_search_download)

    return root


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
