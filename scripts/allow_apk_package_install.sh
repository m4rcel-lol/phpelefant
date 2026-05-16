#!/usr/bin/env sh
set -eu

USER_NAME="${SHELL_RUNTIME_USER:-phpelefant-env}"
SUDOERS_FILE="/etc/sudoers.d/phpelefant-env-apk"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script as root." >&2
  exit 1
fi

if ! command -v apk >/dev/null 2>&1; then
  echo "apk was not found. This helper is for Alpine Linux hosts." >&2
  exit 1
fi

if ! id "$USER_NAME" >/dev/null 2>&1; then
  echo "User does not exist: $USER_NAME" >&2
  exit 1
fi

cat >"$SUDOERS_FILE" <<EOF
# PHPelefant package-management permissions.
# This allows the Telegram bot runtime user to install Alpine packages without a password.
# Treat anyone with PHPelefant /shell access as trusted once this is enabled.
$USER_NAME ALL=(root) NOPASSWD: /sbin/apk add *, /sbin/apk update, /sbin/apk search *, /sbin/apk info *
EOF

chmod 0440 "$SUDOERS_FILE"

if command -v visudo >/dev/null 2>&1; then
  visudo -cf "$SUDOERS_FILE"
fi

echo "Installed sudoers rule: $SUDOERS_FILE"
echo "Test with: sudo -u $USER_NAME sudo -n /sbin/apk add sl"

