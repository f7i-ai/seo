#!/usr/bin/env bash
# Upload the 17 updated posts (accuracy fixes) to Prismic.
#
# Run from seo/:  ./upload-updated-posts.sh
# (Loads .env automatically. Or export PRISMIC_API_KEY=your_token)
#
# Note: Documents that are already PUBLISHED in Prismic will be updated.
# If a post exists only as a DRAFT, the uploader cannot get its ID and will
# report "UID already exists". Fix by either:
#   1. Publishing that document in Prismic (Dashboard → document → Publish), then re-run this script, or
#   2. Deleting the draft in Prismic and re-running so the script can create it fresh.

set -e
cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ -z "$PRISMIC_API_KEY" ]; then
  echo "Error: PRISMIC_API_KEY not set. Export it or add to .env"
  exit 1
fi

POSTS=(
  "generated_content/maintenance-contractor-compliance-checklist.json"
  "generated_content/signal-analysis-for-condition-monitoring.json"
  "generated_content/industrial-data-architecture-for-predictive-mainte.json"
  "generated_content/change-management-for-maintenance-teams.json"
  "generated_content/aligning-maintenance-with-operations-goals.json"
  "generated_content/conveyor-breakdown-prevention.json"
  "generated_content/asset-data-hygiene-best-practices.json"
  "generated_content/downtime-pattern-analysis.json"
  "generated_content/maintenance-operations-and-CMMS-implementation-gui.json"
  "generated_content/what-is-predictive-maintenance.json"
  "generated_content/predictive-vs-preventive-maintenance-cost-benefit-2026.json"
  "generated_content/how-to-prevent-recurring-equipment-failures.json"
  "generated_content/confined-space-entry-requirements.json"
  "generated_content/hot-works-certificate-requirements.json"
  "generated_content/maintenance-documentation-best-practices.json"
  "generated_content/CMMS-optimisation-tips-and-pitfalls.json"
  "generated_content/predictive-maintenance-compliance-australia.json"
)

echo "Uploading ${#POSTS[@]} updated posts to Prismic..."
for f in "${POSTS[@]}"; do
  if [ ! -f "$f" ]; then
    echo "Skip (missing): $f"
    continue
  fi
  echo "--- $f ---"
  node prismic_uploader.js "$f" || true
  echo ""
done
echo "Done."
