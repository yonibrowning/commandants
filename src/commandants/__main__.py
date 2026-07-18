"""Command-line interface: ``commandants <subcommand>``.

Subcommands
-----------
install-ants     download prebuilt ANTs binaries into the managed directory
which            print the resolved path of an ANTs binary
version          print commandants and ANTs versions
list             list managed ANTs installs
uninstall-ants   remove a managed ANTs install
info             show the managed data directory
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .core.exceptions import CommandantsError


def _cmd_install_ants(args: argparse.Namespace) -> int:
    from .install import install_ants

    bindir = install_ants(
        version=args.version,
        dest=args.dest,
        asset=args.asset,
        force=args.force,
        quiet=args.quiet,
    )
    print(bindir)
    return 0


def _cmd_which(args: argparse.Namespace) -> int:
    from .core.executable import resolve_binary

    print(resolve_binary(args.name, auto_install=args.auto_install))
    return 0


def _cmd_version(args: argparse.Namespace) -> int:
    from .core.executable import is_available, version

    print(f"commandants {__version__}")
    if is_available():
        print(f"ANTs {version()}")
    else:
        print("ANTs: not found (run `commandants install-ants`)")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    from .install import installed_versions

    installs = installed_versions()
    if not installs:
        print("No managed ANTs installs. Run `commandants install-ants`.")
        return 0
    for ver, bindir in sorted(installs.items()):
        print(f"{ver}\t{bindir}")
    return 0


def _cmd_uninstall_ants(args: argparse.Namespace) -> int:
    from .install import uninstall_ants

    removed = uninstall_ants(version=args.version)
    if not removed:
        print("Nothing to remove.")
    for path in removed:
        print(f"removed {path}")
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    from .install import user_data_dir

    print(user_data_dir())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="commandants", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"commandants {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_install = sub.add_parser("install-ants", help="download prebuilt ANTs binaries")
    p_install.add_argument("--version", default="2.6.5", help="ANTs version or 'latest' (default: 2.6.5)")
    p_install.add_argument("--asset", default=None, help="explicit release asset name (override auto-select)")
    p_install.add_argument("--dest", default=None, help="install root (default: managed data dir)")
    p_install.add_argument("--force", action="store_true", help="re-download even if present")
    p_install.add_argument("--quiet", action="store_true", help="suppress progress output")
    p_install.set_defaults(func=_cmd_install_ants)

    p_which = sub.add_parser("which", help="print the resolved path of an ANTs binary")
    p_which.add_argument("name", nargs="?", default="antsRegistration")
    p_which.add_argument("--auto-install", dest="auto_install", action="store_true",
                         help="download managed ANTs if not found")
    p_which.set_defaults(func=_cmd_which)

    p_version = sub.add_parser("version", help="print commandants and ANTs versions")
    p_version.set_defaults(func=_cmd_version)

    p_list = sub.add_parser("list", help="list managed ANTs installs")
    p_list.set_defaults(func=_cmd_list)

    p_uninstall = sub.add_parser("uninstall-ants", help="remove a managed ANTs install")
    p_uninstall.add_argument("--version", default=None, help="version to remove (default: all)")
    p_uninstall.set_defaults(func=_cmd_uninstall_ants)

    p_info = sub.add_parser("info", help="show the managed data directory")
    p_info.set_defaults(func=_cmd_info)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CommandantsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
