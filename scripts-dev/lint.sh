#!/usr/bin/env bash
# Runs linting scripts and type checking
# isort - sorts import statements
# black - opinionated code formatter
# flake8 - lints and finds mistakes
# mypy - checks type annotations

set -e

files=(
  "autoreply"
)

# Print out the commands being run
set -x

isort --profile=black "${files[@]}"
python3 -m black "${files[@]}"
flake8 "${files[@]}"