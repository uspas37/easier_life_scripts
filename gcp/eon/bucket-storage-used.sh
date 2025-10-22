#!/bin/bash

# ==============================================================================
# Description:
# This script lists all GCP projects within a specified organization, checks if
# the Cloud Storage API is enabled for each, and then calculates the size of
# every bucket in the enabled projects.
#
# The final output is a CSV file containing the project ID, bucket name, and
# its total size in bytes.
#
# Author: Pablo Sanchez
# Date: 2025-08-08
# ==============================================================================


# The name of the final CSV report file.
OUTPUT_FILE="gcp_bucket_sizes_report.csv"


# --- Main Logic ---

# Initialize the output file with a header
echo "project_id,bucket_name,size_in_bytes" > "$OUTPUT_FILE"
echo "✅ Report file created: $OUTPUT_FILE"
echo "-----------------------------------------------------"

# Get all active project IDs in the organization
PROJECT_IDS=$(gcloud projects list --format="value(projectId)" | egrep -v "sys-")

# Loop through each project ID
for PROJECT_ID in $PROJECT_IDS; do
  echo -e "\n▶️  Processing project: $PROJECT_ID"

  # Check if the Cloud Storage API (storage.googleapis.com) is enabled for the project
  API_ENABLED=$(gcloud services list --enabled --project="$PROJECT_ID" --format="value(config.name)" | grep -w "storage.googleapis.com")

  if [[ -n "$API_ENABLED" ]]; then
    echo "    ✅ Cloud Storage API is enabled. Fetching bucket sizes..."

    # List all buckets in the project. The `|| true` prevents the script from exiting if a project has no buckets.
    BUCKETS=$(gcloud storage ls --project="$PROJECT_ID" || true)

    if [[ -z "$BUCKETS" ]]; then
      echo "    ℹ️ No buckets found in this project."
      continue
    fi

    # For each bucket, get its size and write to the CSV
    while read -r BUCKET_URI; do
      # gsutil du returns a line like: 12345678  gs://bucket-name/
      # We read the size and name into separate variables.
      gsutil du -s "$BUCKET_URI" | while read -r SIZE BUCKET_NAME; do
        if [[ -n "$SIZE" && -n "$BUCKET_NAME" ]]; then
          echo "        -> Found bucket: $BUCKET_NAME | Size: $SIZE bytes"
          # Write the data to the CSV file
          echo "$PROJECT_ID,$BUCKET_NAME,$SIZE" >> "$OUTPUT_FILE"
        fi
      done
    done <<< "$BUCKETS"

  else
    echo "    ⏭️  Cloud Storage API not enabled. Skipping."
  fi
done

echo "-----------------------------------------------------"
echo "🎉 Analysis complete. Report saved to $OUTPUT_FILE"
