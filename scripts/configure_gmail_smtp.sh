#!/usr/bin/env bash
set -euo pipefail
umask 077

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="$project_root/.env"
template_file="$project_root/.env.example"

if [[ ! -f "$env_file" ]]; then
  cp "$template_file" "$env_file"
fi

read -r -p "Gmail sender address: " email_user
read -r -s -p "Paste the 16-character Google App Password: " app_password
printf '\n'
app_password="${app_password// /}"
if [[ ${#app_password} -lt 16 ]]; then
  echo "The App Password looks incomplete. Nothing was changed." >&2
  exit 1
fi

django_secret="$(python -c "import secrets; print(secrets.token_urlsafe(48))")"

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

set_env DJANGO_DEBUG True
set_env DJANGO_SECRET_KEY "$django_secret"
set_env DJANGO_ALLOWED_HOSTS localhost,127.0.0.1
set_env DJANGO_CSRF_TRUSTED_ORIGINS http://localhost:8000,http://127.0.0.1:8000
set_env DJANGO_EMAIL_BACKEND django.core.mail.backends.smtp.EmailBackend
set_env EMAIL_HOST smtp.gmail.com
set_env EMAIL_PORT 587
set_env EMAIL_HOST_USER "$email_user"
set_env EMAIL_HOST_PASSWORD "$app_password"
set_env EMAIL_USE_TLS True
set_env EMAIL_USE_SSL False
set_env EMAIL_TIMEOUT 10
set_env DEFAULT_FROM_EMAIL "NEXORA <$email_user>"

unset app_password
echo "SMTP settings saved to .env. Restart the Django service before testing email."
