#!/usr/bin/env bash
# Shared settings for all scripts. Source it; don't run it.
set -euo pipefail

# Git Bash on Windows rewrites arguments starting with "/" into Windows paths.
# That breaks things like /aws/lambda/... log group names. Turn it off.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

export AWS_PROFILE="${AWS_PROFILE:-poc}"
export AWS_REGION="${AWS_REGION:-eu-north-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"
export AWS_PAGER=""

# With path conversion off, Windows-native tools (aws.exe, terraform.exe) can't read /d/... paths.
# `pwd -W` gives D:/... in Git Bash; fall back to plain pwd elsewhere.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && (pwd -W 2>/dev/null || pwd))"

# Python launcher differs between Windows installs.
PY="$(command -v python || command -v python3 || command -v py)"
INFRA_DIR="$REPO_ROOT/infra"

tf_out() { terraform -chdir="$INFRA_DIR" output -raw "$1"; }

ok()   { printf '  \033[32mOK\033[0m   %s\n' "$*"; }
warn() { printf '  \033[33mWARN\033[0m %s\n' "$*"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$*"; }
