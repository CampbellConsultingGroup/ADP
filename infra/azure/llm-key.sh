# shellcheck shell=bash
# Sourced by deploy.sh. Finds the Anthropic key to store in Key Vault as adp-llm-api-key.
#
#   resolve_llm_api_key <repo-root>
#
# Sets LLM_API_KEY and LLM_API_KEY_SOURCE ("environment", "repo-root .env", or empty when
# there is no key). The environment wins: the project .envrc (direnv) loads
# ADP_LLM_API_KEY from 1Password, so the key needn't be written into any file. A line in
# the repo-root .env is still read as a fallback. Never prints the key.

# shellcheck disable=SC2034  # LLM_API_KEY and LLM_API_KEY_SOURCE are read by deploy.sh
resolve_llm_api_key() {
  local repo_root="$1"
  LLM_API_KEY="${ADP_LLM_API_KEY:-}"
  LLM_API_KEY_SOURCE=""
  if [[ -n "$LLM_API_KEY" ]]; then
    LLM_API_KEY_SOURCE="environment"
  elif [[ -f "$repo_root/.env" ]]; then
    LLM_API_KEY="$(grep -E '^ADP_LLM_API_KEY=' "$repo_root/.env" | head -1 | cut -d= -f2- || true)"
    [[ -n "$LLM_API_KEY" ]] && LLM_API_KEY_SOURCE="repo-root .env"
  fi
  return 0
}
