#!/bin/bash

# use: ./run_analysis.sh <DL_SCRIPT> <HEX_FILE>
# example:  sudo bash ./run_analysis.sh ./clients/analyze.dl ./examples/test.hex

DL_SCRIPT=$1
HEX_FILE=$2

if [ -z "$DL_SCRIPT" ] || [ -z "$HEX_FILE" ]; then
  echo "sudo bash ./run_analysis.sh ./clients/analyze.dl ./examples/test.hex"
  exit 1
fi


BASE_NAME=$(basename "$HEX_FILE" .hex)
OUT_DIR="./.temp/$BASE_NAME"



sudo rm -rf "$OUT_DIR"
echo "Remove: $OUT_DIR"

# run
sudo python3 ./gigahorse.py -C "$DL_SCRIPT" "$HEX_FILE"
