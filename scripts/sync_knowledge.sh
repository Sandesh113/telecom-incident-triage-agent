#!/usr/bin/env bash
# B5 — Upload the skill bundle. ONLY the agent-readable files go up.
# Never uploads scenarios/ or dictionary/ (BUILD SPEC v3 §4 data separation).
# Usage: bash scripts/sync_knowledge.sh [knowledge-dir]   (default: ./knowledge)
source "$(dirname "$0")/_common.sh"

SRC="${1:-$REPO_ROOT/knowledge}"
BUCKET="$(tf_out knowledge_bucket)"

[[ -d "$SRC" ]] || { fail "No knowledge dir at $SRC"; exit 1; }

for f in SKILL.md catalog.json shared-rules.md; do
  if [[ -f "$SRC/$f" ]]; then aws s3 cp "$SRC/$f" "s3://$BUCKET/$f"; else warn "missing $f"; fi
done
for d in sops reference; do
  if [[ -d "$SRC/$d" ]]; then aws s3 sync "$SRC/$d" "s3://$BUCKET/$d" --delete; else warn "missing $d/"; fi
done

echo; echo "Bucket contents:"
aws s3 ls "s3://$BUCKET" --recursive
if aws s3 ls "s3://$BUCKET" --recursive | grep -Eiq 'scenario|dictionary|oracle'; then
  fail "Forbidden content found in the knowledge bucket. Remove it."; exit 1
fi
ok "Knowledge bucket holds only allowed paths."
