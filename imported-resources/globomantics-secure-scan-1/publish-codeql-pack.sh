#!/usr/bin/env bash
set -euo pipefail

# --- Configurable Variables ---
PACK_DIR="globomantics-secure-scan"
GHCR_ORG="timothywarner-org"
GHCR_REGISTRY="ghcr.io/${GHCR_ORG}"
CODEQL_CLI="codeql" # Assumes codeql is in your PATH
# GITHUB_PAT=""

# --- Auth to GHCR ---
echo "${GITHUB_PAT}" | gh auth login --with-token

# --- First, install dependencies ---
cd "${PACK_DIR}"
"${CODEQL_CLI}" pack install

# --- Create the CodeQL Pack ---
"${CODEQL_CLI}" pack create

# --- Publish the Pack to GHCR ---
# Using github-auth-stdin for authentication
# This redirects the token to stdin of the codeql command
echo "${GITHUB_PAT}" | "${CODEQL_CLI}" pack publish --github-auth-stdin

echo "✅ CodeQL pack published to ${GHCR_REGISTRY}/globomantics-secure-scan" 