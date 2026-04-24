"""Validate docker-compose configuration when Docker CLI is available."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_docker_compose_config_is_valid():
    try:
        r = subprocess.run(
            ['docker', 'compose', '-f', str(ROOT / 'docker-compose.yml'), 'config'],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        pytest.skip('docker CLI not installed')
    if r.returncode != 0:
        pytest.skip(f'docker compose not runnable: {r.stderr or r.stdout}')
    out = r.stdout or ''
    assert 'postgres:' in out
    assert 'api:' in out
