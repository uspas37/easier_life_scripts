#!/bin/bash

# Set the output file name
OUTPUT_FILE="gcp_disk_inventory_$(date +%Y%m%d_%H%M%S).csv"

# Print the header to the CSV file
echo "PROJECT_ID,NAME,LOCATION,LOCATION_SCOPE,SIZE_GB,TYPE,STATUS" > "$OUTPUT_FILE"

# Get a list of all projects in the organization
PROJECTS=$(gcloud projects list --format="value(projectId)" | grep -v "sys-")

# Loop through each project
for PROJECT_ID in $PROJECTS
do
  echo "Checking project: $PROJECT_ID"
  
  # Check if the Compute Engine API is enabled for the project
  API_STATUS=$(gcloud services list --project="$PROJECT_ID" --filter="NAME:compute.googleapis.com" --format="value(STATE)" 2>/dev/null)
  
  if [ "$API_STATUS" == "ENABLED" ]; then
    echo "Compute Engine API is enabled. Retrieving disk information..."
    
    # Run the gcloud command to list disks and format the output as CSV
    # The --quiet flag is used to disable prompts, which is good practice in scripts.
    # The --format flag is used to specify the output format and columns.
    gcloud compute disks list --project="$PROJECT_ID" --format="csv[no-heading](name,zone,scope(location),sizeGb,type,status)" --quiet >> "$OUTPUT_FILE"
  else
    echo "Compute Engine API is disabled. Skipping project."
  fi
done

echo "Script finished. Results are saved in $OUTPUT_FILE"
