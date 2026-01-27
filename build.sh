#!/bin/bash
# Define the function
alice() {
    flatpak run technology.haniwa.alice "$@"
}
alice ex build -o dohnadohnaEx.ex dohnadohnaEx.txt
alice ain edit -t output.txt -o dohnadohna.ain-temp dohnadohna-orig.ain
alice ain edit -c Functions.txt -o dohnadohna.ain dohnadohna.ain-temp
rm -rf output
mkdir output
mv dohnadohna.ain output/dohnadohna.ain
mv dohnadohnaEx.ex output/dohnadohnaEx.ex
