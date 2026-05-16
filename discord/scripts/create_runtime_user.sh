#!/usr/bin/env sh
set -eu

USER_NAME="${SHELL_RUNTIME_USER:-phpelefant-env}"
GROUP_NAME="$USER_NAME"
HOME_DIR="/home/$USER_NAME"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script as root." >&2
  exit 1
fi

if ! getent group "$GROUP_NAME" >/dev/null 2>&1; then
  groupadd --system "$GROUP_NAME"
fi

if ! id "$USER_NAME" >/dev/null 2>&1; then
  useradd --system --gid "$GROUP_NAME" --home-dir "$HOME_DIR" --create-home --shell /bin/sh "$USER_NAME"
fi

echo "Runtime user ready: $USER_NAME"

