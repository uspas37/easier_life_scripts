#!/bin/bash

# This script checks for enabled APIs on all GCP Projects.
#
# Define API service names
VERTEX_AI_API="aiplatform.googleapis.com"
GENERATIVE_AI_API="generativelanguage.googleapis.com"

# Define the output CSV file
OUTPUT_FILE="gcp-ai-projects.csv"

# Add CSV header to the file
echo "Project ID,Enabled APIs" > "$OUTPUT_FILE"

# Get a list of all GCP project IDs
PROJECT_IDS=$(gcloud projects list --format="value(PROJECT_ID)" | grep -v "sys-")

# Loop through each project ID
for PROJECT in $PROJECT_IDS; do
    # Check for enabled APIs in the current project
    ENABLED_APIS=$(gcloud services list --project="$PROJECT" \
        --filter="name:$VERTEX_AI_API OR name:$GENERATIVE_AI_API" \
        --format="value(NAME)")

    # Check if any of the target APIs are enabled
    if [ ! -z "$ENABLED_APIS" ]; then
        # Replace the service name with a more user-friendly name if desired
        # The gcloud services list command returns the full service name (e.g., aiplatform.googleapis.com).
        # We can format the output to be more readable.
        FORMATTED_APIS=$(echo "$ENABLED_APIS" | sed \
            -e "s/$VERTEX_AI_API/Vertex AI API/" \
            -e "s/$GENERATIVE_AI_API/Generative AI API/")

        # Append the results to the CSV file, with a single line for each project
        echo "$PROJECT,\"$(echo "$FORMATTED_APIS" | tr '\n' ' ' | sed 's/,$//')\"" >> "$OUTPUT_FILE"
    fi
done

echo "✅ Script complete. Results saved to $OUTPUT_FILE"
