#!/usr/bin/env bash
set -euo pipefail
umask 077

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="$project_root/.env"
template_file="$project_root/.env.example"

if [[ ! -f "$env_file" ]]; then
  cp "$template_file" "$env_file"
fi

read -r -s -p "Paste the Gemini API key: " api_key
printf '\n'
if [[ ${#api_key} -lt 20 ]]; then
  echo "The Gemini API key looks incomplete. Nothing was changed." >&2
  exit 1
fi

set_env() {
  NEXORA_ENV_FILE="$env_file" NEXORA_ENV_KEY="$1" NEXORA_ENV_VALUE="$2" python - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["NEXORA_ENV_FILE"])
key = os.environ["NEXORA_ENV_KEY"]
value = os.environ["NEXORA_ENV_VALUE"]
lines = path.read_text(encoding="utf-8-sig").splitlines()
replacement = f"{key}={value}"
for index, line in enumerate(lines):
    if line.startswith(f"{key}="):
        lines[index] = replacement
        break
else:
    lines.append(replacement)
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

set_env GEMINI_API_KEY "$api_key"
set_env GEMINI_MODEL gemini-2.5-flash-lite
set_env GEMINI_ENABLED True

unset api_key
echo "Gemini settings saved to .env. Restart the Django service to activate them."
