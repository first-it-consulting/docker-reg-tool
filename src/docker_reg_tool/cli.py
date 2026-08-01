"""CLI argument parsing and command dispatch."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

from docker_reg_tool.client import (
    RegistryClient,
    RegistryConfig,
    RegistryError,
)


def setup_logging(trace: bool = False) -> None:
    """Configure logging based on settings.

    Args:
        trace: If True, enable DEBUG level logging.
    """
    level = logging.DEBUG if trace else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_registry_url(url: str) -> tuple[str, str]:
    """Parse a registry URL into protocol and hostname.

    Args:
        url: Full registry URL (e.g., 'https://registry.example.com:5000').

    Returns:
        Tuple of (protocol, registry_host).

    Raises:
        ValueError: If URL is malformed.
    """
    if "://" not in url:
        raise ValueError("URL must include protocol (http:// or https://)")

    protocol, _, rest = url.partition("://")
    if not rest:
        raise ValueError("URL must include a hostname after the protocol")

    # Remove trailing path if any
    registry = rest.split("/")[0]

    return protocol, registry


def build_config(
    url: str,
    basic_auth: Optional[str] = None,
    docker_config: Optional[str] = None,
    insecure: bool = False,
    trace: bool = False,
) -> RegistryConfig:
    """Build a RegistryConfig from CLI arguments and environment.

    Args:
        url: Registry base URL.
        basic_auth: Optional Basic auth string (user:pass).
        docker_config: Path to Docker config.json.
        insecure: Whether to skip TLS verification.
        trace: Whether to enable debug logging.

    Returns:
        Configured RegistryConfig instance.
    """
    # Determine Docker config path
    if docker_config is None:
        docker_config = os.environ.get(
            "DOCKER_CONFIG",
            os.path.expanduser("~/.docker/config.json"),
        )

    # Parse URL to get registry hostname for auth lookup
    _, registry_host = parse_registry_url(url)

    # Get credentials
    auth = basic_auth
    if not auth:
        from docker_reg_tool.auth import parse_docker_config

        auth = parse_docker_config(docker_config)
        if not auth:
            raise ValueError(
                "No credentials found. Set BASIC_AUTH env var or run 'docker login'."
            )

    return RegistryConfig(
        base_url=url,
        basic_auth=auth,
        docker_config_path=docker_config,
        insecure=insecure,
        trace=trace,
    )


def cmd_list(client: RegistryClient, args: argparse.Namespace) -> int:
    """Handle the 'list' command.

    Args:
        client: RegistryClient instance.
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success).
    """
    repo = getattr(args, "repo", None)

    if repo:
        try:
            tags = client.list_tags(repo)
            for tag in tags:
                print(tag)
        except RegistryError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
    else:
        try:
            repos = client.list_repositories()
            for repo in repos:
                print(repo)
        except RegistryError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    return 0


def cmd_delete(client: RegistryClient, args: argparse.Namespace) -> int:
    """Handle the 'delete' command.

    Args:
        client: RegistryClient instance.
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    repo = args.repo
    tag = args.tag

    try:
        success = client.delete_tag(repo, tag)
        if success:
            print("Successfully deleted")
            return 0
        return 3
    except RegistryError as e:
        print(f"Failed to delete: {e}", file=sys.stderr)
        return 3


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="docker-reg-tool",
        description="Docker Registry v2 CLI tool for listing and deleting images.",
    )

    parser.add_argument(
        "url",
        help="Registry base URL (e.g., https://registry.example.com:5000)",
    )

    subparsers = parser.add_subparsers(dest="action", required=True)

    # list subcommand
    list_parser = subparsers.add_parser(
        "list",
        help="List repositories or tags",
    )
    list_parser.add_argument(
        "repo",
        nargs="?",
        default=None,
        help="Repository name (optional - if omitted, lists all repos)",
    )
    list_parser.set_defaults(func=cmd_list)

    # delete subcommand
    delete_parser = subparsers.add_parser(
        "delete",
        help="Delete an image tag",
    )
    delete_parser.add_argument("repo", help="Repository name")
    delete_parser.add_argument("tag", help="Image tag to delete")
    delete_parser.set_defaults(func=cmd_delete)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code.
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Build config from args and environment
    try:
        config = build_config(
            url=args.url,
            basic_auth=os.environ.get("BASIC_AUTH"),
            docker_config=os.environ.get("DOCKER_CONFIG"),
            insecure=bool(os.environ.get("INSECURE_REGISTRY")),
            trace=bool(os.environ.get("TRACE")),
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 4

    setup_logging(trace=config.trace)

    client = RegistryClient(config)

    try:
        return args.func(client, args)
    except KeyboardInterrupt:
        print("\nOperation cancelled.", file=sys.stderr)
        return 130
    except RegistryError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logging.exception("Unexpected error")
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        return 2
