#!/usr/bin/env bash
# Ship a new claudeusage release.
#
#   ./release.sh 1.2.0
#
# Does the four things a release needs, in the order that keeps users safe:
#   1. tags and pushes this repo
#   2. points the Homebrew formula at the new tarball and its sha256
#   3. tells the stats service the new version exists, so installs that have
#      opted in start showing the "update available" banner
#
# The version bump in the script itself is checked, not done for you - bump
# __version__ and commit before running this.
set -euo pipefail

VERSION="${1:-}"
[ -n "$VERSION" ] || { echo "usage: ./release.sh <version>   e.g. ./release.sh 1.2.0"; exit 1; }
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "version must look like 1.2.0"; exit 1; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAP_DIR="${TAP_DIR:-$HOME/Desktop/Projects/homebrew-tap}"
REGION="${AWS_REGION:-us-east-1}"
FUNCTION="claudeusage-community"
TABLE="ClaudeUsageCommunity"

cd "$REPO_DIR"

# --- preflight ---------------------------------------------------------------
IN_SCRIPT="$(sed -n "s/^__version__ = '\(.*\)'$/\1/p" claudeusage)"
if [ "$IN_SCRIPT" != "$VERSION" ]; then
  echo "claudeusage says __version__ = '$IN_SCRIPT' but you asked to release $VERSION."
  echo "Bump __version__ in the script, commit, then re-run."
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "working tree is dirty - commit first so the tag matches what ships."
  exit 1
fi
[ -d "$TAP_DIR" ] || { echo "tap not found at $TAP_DIR (set TAP_DIR=...)"; exit 1; }

# --- 1. tag the source -------------------------------------------------------
echo "==> tagging v$VERSION"
git tag -a "v$VERSION" -m "claudeusage $VERSION"
git push origin main
git push origin "v$VERSION"

# --- 2. update the formula ---------------------------------------------------
echo "==> waiting for the release tarball"
URL="https://github.com/ryuhemingway/claudeusage/archive/refs/tags/v$VERSION.tar.gz"
for _ in $(seq 1 20); do
  curl -fsL -o /tmp/claudeusage-release.tar.gz "$URL" && break
  sleep 3
done
SHA="$(shasum -a 256 /tmp/claudeusage-release.tar.gz | cut -d' ' -f1)"
echo "    sha256 $SHA"

FORMULA="$TAP_DIR/Formula/claudeusage.rb"
/usr/bin/sed -i '' -e "s|url \".*\"|url \"$URL\"|" -e "s|sha256 \".*\"|sha256 \"$SHA\"|" "$FORMULA"
( cd "$TAP_DIR" && git add Formula/claudeusage.rb \
  && git commit -q -m "claudeusage $VERSION" && git push -q origin main )
echo "    formula updated and pushed"

# --- 3. announce it to installs that opted in --------------------------------
# Done last, on purpose: only advertise a version users can actually install.
echo "==> publishing $VERSION to the update feed"
aws lambda update-function-configuration --region "$REGION" --function-name "$FUNCTION" \
  --environment "Variables={TABLE_NAME=$TABLE,LATEST_VERSION=$VERSION}" >/dev/null
aws lambda wait function-updated --region "$REGION" --function-name "$FUNCTION"

echo
echo "released $VERSION"
echo "  users on brew:  brew update && brew upgrade claudeusage"
echo "  opted-in installs see the update banner within a day"
