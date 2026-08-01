#!/usr/bin/env python3
"""Executable entry point for docker-reg-tool.

Usage:
    docker-reg-tool REGISTRY_BASE_URL ACTION [OPTIONS..]

Actions:
    - list               List all repositories
    - list REPO          List tags for a repository
    - delete REPO TAG    Delete a tag from a repository

Examples:
    docker-reg-tool https://registry.example.com list
    docker-reg-tool https://registry.example.com list my-repo
    docker-reg-tool https://registry.example.com delete my-repo v1.0.0
"""

import sys

from docker_reg_tool.cli import main

if __name__ == "__main__":
    sys.exit(main())
