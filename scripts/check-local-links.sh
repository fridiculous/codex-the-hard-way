#!/usr/bin/env bash
set -euo pipefail

status=0

while IFS= read -r file; do
  dir=$(dirname "$file")

  while IFS= read -r target; do
    target=${target%%#*}
    [ -z "$target" ] && continue

    case "$target" in
      http:*|https:*|mailto:*) continue ;;
    esac

    if [ ! -e "$dir/$target" ]; then
      printf '%s: missing local link target: %s\n' "$file" "$target"
      status=1
    fi
  done < <(perl -nE 'while (/\[[^\]]+\]\(([^)]+)\)/g) { say $1 }' "$file")
done < <(
  find . -name '*.md' \
    -not -path './.git/*' \
    -not -path './tmp/*' \
    -not -path './.cache/*' \
    -not -path './notes/*' \
    -not -path './codex-src/*' \
    | sort
)

exit "$status"
