"""Tests for docker_reg_tool.cli."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from docker_reg_tool.cli import (
    build_config,
    parse_registry_url,
)


class TestParseRegistryUrl:
    """Tests for URL parsing."""

    def test_https_url(self):
        """Should parse HTTPS URLs correctly."""
        protocol, host = parse_registry_url("https://registry.example.com:5000")
        assert protocol == "https"
        assert host == "registry.example.com:5000"

    def test_http_url(self):
        """Should parse HTTP URLs correctly."""
        protocol, host = parse_registry_url("http://localhost:5000")
        assert protocol == "http"
        assert host == "localhost:5000"

    def test_url_with_path(self):
        """Should strip trailing path."""
        protocol, host = parse_registry_url("https://registry.example.com/v2")
        assert protocol == "https"
        assert host == "registry.example.com"

    def test_url_without_protocol(self):
        """Should raise ValueError for URLs without protocol."""
        with pytest.raises(ValueError, match="protocol"):
            parse_registry_url("registry.example.com")


class TestBuildConfig:
    """Tests for config building."""

    def test_basic_auth_override(self):
        """BASIC_AUTH env var should override docker config."""
        with patch.dict("os.environ", {"BASIC_AUTH": "user:pass"}):
            config = build_config("http://localhost:5000")
            assert config.basic_auth == "user:pass"

    def test_insecure_flag(self):
        """INSECURE_REGISTRY env var should be respected."""
        with patch.dict(
            "os.environ", {"INSECURE_REGISTRY": "true", "BASIC_AUTH": "user:pass"}
        ):
            config = build_config("http://localhost:5000")
            assert config.insecure is True

    def test_trace_flag(self):
        """TRACE env var should be respected."""
        with patch.dict("os.environ", {"TRACE": "true", "BASIC_AUTH": "user:pass"}):
            config = build_config("http://localhost:5000")
            assert config.trace is True

    def test_custom_docker_config(self):
        """DOCKER_CONFIG env var should be respected."""
        with patch("docker_reg_tool.cli.parse_docker_config") as mock_parse:
            mock_parse.return_value = "dXNlcjpwYXNz"
            build_config(
                "http://localhost:5000",
                docker_config="/custom/path/config.json",
            )
            mock_parse.assert_called_once_with(
                "/custom/path/config.json", registry="localhost:5000"
            )

    def test_no_credentials(self):
        """Should raise error if no credentials found."""
        with patch("docker_reg_tool.cli.parse_docker_config") as mock_parse:
            mock_parse.return_value = None
            with pytest.raises(ValueError, match="No credentials"):
                build_config("http://localhost:5000")
