"""Docker Registry API client."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from requests.exceptions import ConnectionError

logger = logging.getLogger(__name__)


@dataclass
class RegistryConfig:
    """Configuration for connecting to a Docker Registry."""

    base_url: str
    basic_auth: str | None = None
    docker_config_path: str | None = None
    insecure: bool = False
    trace: bool = False

    def __post_init__(self) -> None:
        # Normalize base_url to ensure protocol and no trailing slash
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("Registry URL must include protocol (http:// or https://)")
        self.base_url = self.base_url.rstrip("/")

    @property
    def api_base(self) -> str:
        """Return the API base URL."""
        return f"{self.base_url}/v2"

    def get_session(self) -> requests.Session:
        """Create and configure a requests session."""
        session = requests.Session()
        session.verify = not self.insecure

        if self.basic_auth:
            import base64

            credentials = base64.b64encode(self.basic_auth.encode()).decode()
            session.headers["Authorization"] = f"Basic {credentials}"

        if self.trace:
            logging.basicConfig(level=logging.DEBUG)
            http_log = logging.getLogger("urllib3.connectionpool")
            http_log.setLevel(logging.DEBUG)
            http_log.debug("HTTP tracing enabled")

        return session


class RegistryError(Exception):
    """Base exception for registry operations."""


class RegistryConnectionError(RegistryError):
    """Failed to connect to the registry."""


class RegistryAuthError(RegistryError):
    """Authentication failed."""


class RegistryAPIError(RegistryError):
    """Registry API returned an error."""

    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        super().__init__(f"Registry API error {status_code}: {message}")


@dataclass
class ManifestInfo:
    """Information about a container image manifest."""

    digest: str
    media_type: str


class RegistryClient:
    """Client for interacting with Docker Registry v2 API."""

    def __init__(self, config: RegistryConfig) -> None:
        self.config = config
        self.session = config.get_session()

    def _request(
        self,
        method: str,
        path: str,
        headers: dict | None = None,
        **kwargs,
    ) -> requests.Response:
        """Make an HTTP request to the registry API."""
        url = f"{self.config.api_base}/{path.lstrip('/')}"
        req_headers = {
            "Accept": "application/vnd.docker.distribution.manifest.list.v2+json",
            **(headers or {}),
        }

        try:
            logger.debug("%s %s", method, url)
            response = self.session.request(method, url, headers=req_headers, **kwargs)
            logger.debug("Response %d", response.status_code)

            if response.status_code == 401:
                raise RegistryAuthError("Authentication failed")

            if response.status_code == 404:
                raise RegistryAPIError(404, f"Resource not found: {path}")

            if response.status_code >= 400:
                raise RegistryAPIError(response.status_code, response.text)

            return response

        except ConnectionError as e:
            raise RegistryConnectionError(
                f"Cannot connect to registry at {self.config.base_url}: {e}"
            ) from e

    def list_repositories(self, n: int = 500) -> list[str]:
        """List all repositories in the registry.

        Args:
            n: Maximum number of repositories to return.

        Returns:
            List of repository names.
        """
        params = {"n": n}
        response = self._request("GET", "_catalog", params=params)
        data = response.json()
        repositories = data.get("repositories", [])
        logger.info("Found %d repositories", len(repositories))
        return repositories

    def list_tags(self, repo: str) -> list[str]:
        """List all tags for a repository.

        Args:
            repo: Repository name (e.g., 'my-org/my-app').

        Returns:
            List of tag names.
        """
        response = self._request("GET", f"{repo}/tags/list")
        data = response.json()
        tags = data.get("tags", [])
        logger.info("Repository '%s' has %d tags", repo, len(tags))
        return tags

    def get_manifest(self, repo: str, tag: str) -> ManifestInfo:
        """Get manifest info for a specific tag.

        Attempts both Docker and OCI manifest formats.

        Args:
            repo: Repository name.
            tag: Image tag.

        Returns:
            ManifestInfo with digest and media type.
        """
        accept_types = [
            "application/vnd.docker.distribution.manifest.v2+json",
            "application/vnd.oci.image.manifest.v1+json",
        ]

        last_error: Exception | None = None

        for accept in accept_types:
            try:
                response = self._request(
                    "GET",
                    f"{repo}/manifests/{tag}",
                    headers={"Accept": accept},
                )
                digest = response.headers.get("Docker-Content-Digest", "")

                if not digest:
                    # Some registries don't return the header on GET;
                    # parse from body if needed
                    body = response.json()
                    digest = body.get("config", {}).get("digest", "")

                if not digest:
                    raise RegistryAPIError(
                        response.status_code, "No Docker-Content-Digest header"
                    )

                logger.info(
                    "Manifest digest for %s/%s:%s = %s",
                    self.config.base_url,
                    repo,
                    tag,
                    digest,
                )
                return ManifestInfo(
                    digest=digest.strip(),
                    media_type=accept,
                )

            except RegistryAPIError as e:
                last_error = e
                logger.debug("Failed to get manifest with %s: %s", accept, e)
                continue

        raise RegistryAPIError(
            500,
            f"Could not retrieve manifest for {repo}:{tag}. Last error: {last_error}",
        )

    def delete_tag(self, repo: str, tag: str) -> bool:
        """Delete a tag from a repository.

        Args:
            repo: Repository name.
            tag: Image tag to delete.

        Returns:
            True if deletion was successful.

        Raises:
            RegistryAPIError: If deletion failed.
        """
        manifest = self.get_manifest(repo, tag)

        response = self._request(
            "DELETE",
            f"{repo}/manifests/{manifest.digest}",
            headers={"Accept": manifest.media_type},
        )

        if response.status_code == 202:
            logger.info(
                "Deleted %s/%s:%s (digest: %s)",
                self.config.base_url,
                repo,
                tag,
                manifest.digest,
            )
            return True

        raise RegistryAPIError(
            response.status_code,
            f"Failed to delete {repo}:{tag}",
        )
