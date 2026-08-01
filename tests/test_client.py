#!/usr/bin/env python3
"""Tests for docker_reg_tool.client."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from docker_reg_tool.client import (
    RegistryClient,
    RegistryConfig,
    RegistryError,
    RegistryAPIError,
)


@pytest.fixture
def config():
    """Create a test registry config."""
    return RegistryConfig(
        base_url="http://localhost:5000",
        basic_auth="testuser:testpassword",
        insecure=True,
    )


@pytest.fixture
def client(config):
    """Create a test client with mocked session."""
    with patch.object(requests, "Session") as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        client = RegistryClient(config)
        client.session = mock_session
        yield client


class TestRegistryConfig:
    """Tests for RegistryConfig."""

    def test_normalizes_url(self):
        """URL should have trailing slash removed."""
        cfg = RegistryConfig(base_url="http://example.com/")
        assert cfg.base_url == "http://example.com"

    def test_requires_protocol(self):
        """URL without protocol should raise ValueError."""
        with pytest.raises(ValueError, match="protocol"):
            RegistryConfig(base_url="example.com")

    def test_api_base(self):
        """API base should include /v2."""
        cfg = RegistryConfig(base_url="http://example.com")
        assert cfg.api_base == "http://example.com/v2"


class TestRegistryClientList:
    """Tests for listing operations."""

    def test_list_repositories(self, client):
        """Should list all repositories."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "repositories": ["hello-world", "nginx", "redis"]
        }
        client.session.request.return_value = mock_response

        repos = client.list_repositories()

        assert repos == ["hello-world", "nginx", "redis"]
        client.session.request.assert_called_once()
        call_args = client.session.request.call_args
        assert call_args[0][0] == "GET"
        assert "_catalog" in call_args[0][1]

    def test_list_repositories_empty(self, client):
        """Should handle empty repository list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"repositories": []}
        client.session.request.return_value = mock_response

        repos = client.list_repositories()
        assert repos == []

    def test_list_tags(self, client):
        """Should list tags for a repository."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tags": ["latest", "v1.0", "v2.0"]}
        client.session.request.return_value = mock_response

        tags = client.list_tags("hello-world")

        assert tags == ["latest", "v1.0", "v2.0"]
        call_args = client.session.request.call_args
        assert "hello-world/tags/list" in call_args[0][1]


class TestRegistryClientDelete:
    """Tests for delete operations."""

    def test_delete_tag_success(self, client):
        """Should delete a tag by digest."""
        # Mock the GET manifest response
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.headers = {"Docker-Content-Digest": "sha256:abc123"}
        get_response.json.return_value = {"config": {"digest": "sha256:abc123"}}

        # Mock the DELETE response
        delete_response = MagicMock()
        delete_response.status_code = 202

        client.session.request.side_effect = [get_response, delete_response]

        result = client.delete_tag("hello-world", "latest")

        assert result is True
        assert client.session.request.call_count == 2

    def test_delete_tag_not_found(self, client):
        """Should raise error when manifest not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "manifest not found"

        client.session.request.return_value = mock_response

        with pytest.raises(RegistryAPIError, match="404"):
            client.delete_tag("hello-world", "latest")

    def test_delete_tag_failed(self, client):
        """Should raise error when delete returns non-202."""
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.headers = {"Docker-Content-Digest": "sha256:abc123"}

        delete_response = MagicMock()
        delete_response.status_code = 500
        delete_response.text = "internal error"

        client.session.request.side_effect = [get_response, delete_response]

        with pytest.raises(RegistryAPIError):
            client.delete_tag("hello-world", "latest")


class TestRegistryClientAuth:
    """Tests for authentication handling."""

    def test_auth_error(self, client):
        """Should raise RegistryAuthError on 401."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        client.session.request.return_value = mock_response

        from docker_reg_tool.client import RegistryAuthError

        with pytest.raises(RegistryAuthError):
            client.list_repositories()


class TestRegistryClientConnection:
    """Tests for connection error handling."""

    def test_connection_error(self, client):
        """Should raise RegistryConnectionError on connection failure."""
        client.session.request.side_effect = requests.exceptions.ConnectionError()

        with pytest.raises(RegistryError, match="Cannot connect"):
            client.list_repositories()
