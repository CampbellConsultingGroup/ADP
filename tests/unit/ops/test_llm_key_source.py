"""Where deploy.sh gets the Anthropic key for Key Vault (infra/azure/llm-key.sh).

The key normally comes from the environment (direnv loads it from 1Password); a line in
the repo-root .env is the fallback. The key itself must never be printed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

HELPER = Path(__file__).resolve().parents[3] / "infra" / "azure" / "llm-key.sh"


def _resolve(repo_root: Path, env_key: str | None) -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin"}
    if env_key is not None:
        env["ADP_LLM_API_KEY"] = env_key
    script = (
        f'source "{HELPER}"; resolve_llm_api_key "{repo_root}"; '
        'printf "key=%s\\nsource=%s\\n" "$LLM_API_KEY" "$LLM_API_KEY_SOURCE"'
    )
    return subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, check=True
    )


def test_environment_wins_over_dotenv(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("ADP_LLM_API_KEY=from-dotenv\n")
    out = _resolve(tmp_path, "from-env").stdout
    assert "key=from-env\n" in out
    assert "source=environment\n" in out


def test_falls_back_to_repo_root_dotenv(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("OTHER=1\nADP_LLM_API_KEY=from-dotenv\n")
    out = _resolve(tmp_path, None).stdout
    assert "key=from-dotenv\n" in out
    assert "source=repo-root .env\n" in out


def test_commented_dotenv_line_is_not_a_key(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("# ADP_LLM_API_KEY: set by .envrc from 1Password\n")
    out = _resolve(tmp_path, None).stdout
    assert "key=\n" in out
    assert "source=\n" in out


def test_no_key_anywhere(tmp_path: Path) -> None:
    out = _resolve(tmp_path, "").stdout
    assert "key=\n" in out


def test_helper_never_prints_the_key(tmp_path: Path) -> None:
    env = {"PATH": "/usr/bin:/bin", "ADP_LLM_API_KEY": "secret-value"}
    result = subprocess.run(
        ["bash", "-c", f'source "{HELPER}"; resolve_llm_api_key "{tmp_path}"'],
        env=env, capture_output=True, text=True, check=True,
    )  # fmt: skip
    assert "secret-value" not in result.stdout + result.stderr
