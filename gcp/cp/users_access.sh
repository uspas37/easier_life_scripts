#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:cp-gio-dev-cloudeng}"
DAYS="${DAYS:-100}"

# Build member -> roles map
declare -A ROLES
while IFS=$'\t' read -r role member; do
  [[ -z "$member" || "$member" == "*" ]] && continue
  if [[ -n "${ROLES[$member]:-}" ]]; then
    ROLES["$member"]+=",${role}"
  else
    ROLES["$member"]="$role"
  fi
done < <(gcloud projects get-iam-policy "$PROJECT_ID" --format='tsv(bindings.role,bindings.members)')

# Build principal -> {count,last_seen} from Cloud Audit Logs
declare -A COUNT LAST
while IFS=, read -r email ts; do
  [[ -z "$email" ]] && continue
  ((COUNT["$email"]++))
  # Keep the most recent timestamp
  [[ -z "${LAST[$email]:-}" || "$ts" > "${LAST[$email]}" ]] && LAST["$email"]="$ts"
done < <(gcloud logging read \
  'logName:"cloudaudit.googleapis.com" AND protoPayload.authenticationInfo.principalEmail:*' \
  --project="$PROJECT_ID" \
  --freshness="${DAYS}d" \
  --order=desc \
  --format='csv[no-heading](protoPayload.authenticationInfo.principalEmail,timestamp)' \
  --limit=200000)

# Header
echo "member,roles,last_seen,api_calls_last_${DAYS}_days"

# Emit rows for every IAM principal; add activity if present
for m in "${!ROLES[@]}"; do
  roles="${ROLES[$m]}"
  last="${LAST[$m]:-none}"
  cnt="${COUNT[$m]:-0}"
  echo "$m,$roles,$last,$cnt"
done | sort