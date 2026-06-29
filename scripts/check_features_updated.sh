#!/usr/bin/env bash
# Stop-hook backstop: if application code changed in the working tree but
# FEATURES.md wasn't touched, remind that the feature catalogue may need updating.
# Non-blocking — the actual update is driven by the CLAUDE.md rule.
set -euo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 0

# Changed (staged + unstaged) tracked + untracked files.
changed="$(git status --porcelain 2>/dev/null | sed 's/^...//')" || exit 0
[ -z "$changed" ] && exit 0

# Did any app code change?
echo "$changed" | grep -Eq '^(app/|scripts/|khata\.spec)' || exit 0
# Was FEATURES.md among the changes?
echo "$changed" | grep -q '^FEATURES\.md$' && exit 0

printf '{"systemMessage": "Reminder: app code changed but FEATURES.md was not updated. If you added/changed/removed a user-facing feature, update FEATURES.md (see CLAUDE.md)."}\n'
