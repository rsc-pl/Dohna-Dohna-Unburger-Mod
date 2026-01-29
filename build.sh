#!/bin/bash
# Define the function
alice() {
    flatpak run technology.haniwa.alice "$@"
}
alice ex build -o dohnadohnaEx.ex dohnadohnaEx.txt
alice ain edit -t Script.txt -o dohnadohna.ain-temp dohnadohna-orig.ain
alice ain edit -c Functions.txt -o dohnadohna.ain dohnadohna.ain-temp
rm -rf output
mkdir output
mv dohnadohna.ain output/dohnadohna.ain
mv dohnadohnaEx.ex output/dohnadohnaEx.ex
rm dohnadohna.ain-temp
cd output

BASE_NAME="Dohna-Dohna-Unburger-"
read -p "Enter the version: " SUFFIX

# Construct the full zip name
ZIP_NAME="${BASE_NAME}_${SUFFIX}.zip"
SCRIPT_NAME=$(basename "$0")

echo "------------------------------------------------"
echo "Target Zip: $ZIP_NAME"
echo "Compressing files with level 9 (Max)..."
echo "------------------------------------------------"

zip -r -9 "$ZIP_NAME" . -x "$ZIP_NAME" "$SCRIPT_NAME"
if [ $? -eq 0 ]; then
    echo "------------------------------------------------"
    echo "Zip created successfully. Cleaning up..."

    # 4. Delete files
    # This finds all files/folders in the current directory
    # ! -name checks ensure we do NOT delete the new zip or this script
    find . -maxdepth 1 -mindepth 1 \
        ! -name "$ZIP_NAME" \
        ! -name "$SCRIPT_NAME" \
        -exec rm -rf {} +

    echo "Cleanup complete. Only $ZIP_NAME and $SCRIPT_NAME remain."
else
    echo "Error: Zip creation failed. No files were deleted."
    exit 1
fi
