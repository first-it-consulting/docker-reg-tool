"""Docker config file authentication parser."""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_docker_config(config_path: str, registry: str | None = None) -> str | None:
    """Parse Docker config.json and return auth credentials for a registry.

    Looks up credentials by both the registry hostname and the full URL
    (including protocol) to handle various config formats.

    Args:
        config_path: Path to docker/config.json file.
        registry: Optional registry hostname (e.g. 'registry.example.com:5000')
            to look up first before falling back to all configured entries.

    Returns:
        Base64-encoded credentials string, or None if not found.
    """
    path = Path(config_path)

    if not path.is_file():
        logger.debug("Docker config not found at %s", config_path)
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to parse Docker config at %s: %s", config_path, e)
        return None

    auths = data.get("auths", {})
    if not auths:
        logger.debug("No auths found in Docker config")
        return None

    return _lookup_auth(auths, registry)


def _lookup_auth(auths: dict, registry: str | None = None) -> str | None:
    """Look up auth credentials in the auths dict.

    Args:
        auths: The 'auths' dict from docker/config.json.
        registry: Optional registry hostname to look up. If None, tries all.

    Returns:
        Base64-encoded credentials or None.
    """
    # Try exact matches first, then without protocol
    candidates = []

    if registry:
        # Add the registry as-is
        candidates.append(registry)
        # Strip protocol if present
        for prefix in ("https://", "http://"):
            if registry.startswith(prefix):
                candidates.append(registry[len(prefix) :])
                break

    # Always try localhost:5000 variants
    for candidate in candidates + list(auths.keys()):
        if candidate in auths:
            auth_entry = auths[candidate]
            auth_str = auth_entry.get("auth", "")
            if auth_str:
                logger.debug("Found credentials for registry: %s", candidate)
                return auth_str

    logger.debug("No credentials found for registry in config")
    return None


def verify_credentials(auth_str: str) -> tuple[str, str]:
    """Verify and decode base64 credentials.

    Args:
        auth_str: Base64-encoded 'username:password' string.

    Returns:
        Tuple of (username, password).

    Raises:
        ValueError: If credentials are invalid.
    """
    try:
        decoded = base64.b64decode(auth_str).decode("utf-8")
        username, _, password = decoded.partition(":")
        if not username or not password:
            raise ValueError("Credentials must be in format 'user:password'")
        return username, password
    except Exception as e:
        raise ValueError(f"Invalid credentials format: {e}") from e
