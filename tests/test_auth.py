"""Tests for docker_reg_tool.auth."""

from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path

import pytest

from docker_reg_tool.auth import parse_docker_config, verify_credentials


class TestParseDockerConfig:
    """Tests for Docker config parsing."""

    def test_parses_valid_config(self, tmp_path):
        """Should parse a valid Docker config."""
        config_file = tmp_path / "config.json"
        auth_str = base64.b64encode(b"user:pass").decode()
        config_file.write_text(json.dumps({
            "auths": {
                "localhost:5000": {"auth": auth_str},
            }
        }))

        result = parse_docker_config(str(config_file))
        assert result == auth_str

    def test_returns_none_for_missing_file(self, tmp_path):
        """Should return None for non-existent config file."""
        result = parse_docker_config(str(tmp_path / "nonexistent.json"))
        assert result is None

    def test_returns_none_for_invalid_json(self, tmp_path):
        """Should return None for invalid JSON."""
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json")

        result = parse_docker_config(str(config_file))
        assert result is None

    def test_returns_none_for_no_auths(self, tmp_path):
        """Should return None if no auths section."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}))

        result = parse_docker_config(str(config_file))
        assert result is None


class TestVerifyCredentials:
    """Tests for credential verification."""

    def test_valid_credentials(self):
        """Should decode valid credentials."""
        auth_str = base64.b64encode(b"user:pass").decode()
        username, password = verify_credentials(auth_str)
        assert username == "user"
        assert password == "pass"

    def test_invalid_format(self):
        """Should raise error for invalid format."""
        with pytest.raises(ValueError, match="Invalid credentials"):
            verify_credentials("not-valid-base64!!!")

    def test_missing_password(self):
        """Should raise error if no password."""
        auth_str = base64.b64encode(b"user:").decode()
        with pytest.raises(ValueError, match="format"):
            verify_credentials(auth_str)
