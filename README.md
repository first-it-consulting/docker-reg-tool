# Docker Registry Tool

A Python CLI tool for managing Docker Registry v2 repositories.

## Features

- List all repositories in a registry
- List tags for a specific repository
- Delete image tags by manifest digest
- Automatic credential detection from Docker config
- Support for Basic authentication
- Insecure registry support (self-signed certs)
- Debug/tracing mode

## Installation

### From source

```bash
git clone https://github.com/yourusername/docker-reg-tool.git
cd docker-reg-tool
pip install -e .
```

### Using pip

```bash
pip install docker-reg-tool
```

## Usage

```bash
# List all repositories
docker-reg-tool https://registry.example.com:5000 list

# List tags for a repository
docker-reg-tool https://registry.example.com:5000 list my-repo

# Delete a tag
docker-reg-tool https://registry.example.com:5000 delete my-repo v1.0.0
```

## Authentication

Credentials are automatically detected from `~/.docker/config.json` (or the path specified by `DOCKER_CONFIG`).

Alternatively, set the `BASIC_AUTH` environment variable:

```bash
export BASIC_AUTH="username:password"
docker-reg-tool https://registry.example.com:5000 list
```

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `BASIC_AUTH` | Basic auth credentials (user:pass) | - |
| `DOCKER_CONFIG` | Path to Docker config.json | `~/.docker/config.json` |
| `INSECURE_REGISTRY` | Skip TLS verification (set to `true`) | `false` |
| `TRACE` | Enable debug logging (set to `true`) | `false` |

## Development

### Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/ -v
```

### Linting

```bash
ruff check src/
```

## Docker Image

Build and run:

```bash
docker build -t docker-reg-tool .
docker run --rm -v ~/.docker:/root/.docker docker-reg-tool https://registry.example.com:5000 list
```

## Registry Requirements

The registry must have deletion enabled:

```yaml
storage:
  delete:
    enabled: true
```

After deleting tags, run the garbage collector to reclaim space:

```bash
docker exec registry /bin/registry garbage-collect /etc/docker/registry/config.yml
```

## License

MIT




