#!/bin/sh
# ClaudeMaxing installer.
#
#   curl -fsSL https://claudemax.sh | sh          (if the domain is set up)
#   curl -fsSL https://raw.githubusercontent.com/ryuhemingway/ClaudeMaxing/main/install.sh | sh
#
# Installs a single Python script into ~/.local/bin. No sudo, no dependencies,
# nothing compiled. Set CLAUDEMAX_BIN_DIR to install somewhere else.
set -eu

REPO="ryuhemingway/ClaudeMaxing"
BIN_DIR="${CLAUDEMAX_BIN_DIR:-$HOME/.local/bin}"

die() { printf '\n  error: %s\n\n' "$1" >&2; exit 1; }

command -v curl >/dev/null 2>&1 || die "curl is required."

PY=$(command -v python3 2>/dev/null || true)
[ -n "$PY" ] || die "python3 not found. Install Python 3.8 or newer, then re-run."
"$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' 2>/dev/null \
  || die "python3 is $("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])'), but 3.8+ is required."

# Newest semver tag, falling back to main if the API is unreachable.
TAG=$(curl -fsSL "https://api.github.com/repos/$REPO/tags" 2>/dev/null \
      | sed -n 's/.*"name"[: ]*"\(v[0-9][^"]*\)".*/\1/p' | sort -V | tail -1)
[ -n "$TAG" ] || TAG="main"

TMP=$(mktemp) || die "could not create a temporary file."
trap 'rm -f "$TMP"' EXIT INT TERM

curl -fsSL "https://raw.githubusercontent.com/$REPO/$TAG/claudemax" -o "$TMP" \
  || die "download failed. Check your connection, or install with Homebrew instead."

# Guard against a proxy or error page being written over the script.
head -n 1 "$TMP" | grep -q '^#!.*python' || die "downloaded file is not the expected script."

mkdir -p "$BIN_DIR" || die "could not create $BIN_DIR"
chmod +x "$TMP"
mv "$TMP" "$BIN_DIR/claudemax"
trap - EXIT INT TERM

VERSION=$("$BIN_DIR/claudemax" --check-update 2>/dev/null | sed -n 's/.*installed \([0-9.]*\).*/\1/p')
printf '\n  installed claudemax %s to %s\n' "${VERSION:-$TAG}" "$BIN_DIR/claudemax"

case ":$PATH:" in
  *":$BIN_DIR:"*)
    printf '  run it:  claudemax\n\n' ;;
  *)
    SHELL_RC="$HOME/.zshrc"
    [ "${SHELL##*/}" = "bash" ] && SHELL_RC="$HOME/.bashrc"
    printf '\n  %s is not on your PATH yet. Add it with:\n\n' "$BIN_DIR"
    printf '    echo '\''export PATH="%s:$PATH"'\'' >> %s && exec "$SHELL"\n\n' "$BIN_DIR" "$SHELL_RC"
    printf '  or run it directly:  %s/claudemax\n\n' "$BIN_DIR" ;;
esac
