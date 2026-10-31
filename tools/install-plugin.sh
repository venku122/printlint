#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p evidence/orca-native/data/orca_plugins/PrintLint
cp plugins/printlint_native.py evidence/orca-native/data/orca_plugins/PrintLint/printlint_native.py
printf '%s\n' 'Installed only in isolated Orca beta data. Launch tools/orca-printlint.'
