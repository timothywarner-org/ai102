# Publishing Custom CodeQL Query Packs: A Hands-On Guide

This guide walks you through creating and publishing custom CodeQL query packs to GitHub Container Registry (GHCR). Use this as a reference for your Pluralsight courses, demos, and security training.

## What Are CodeQL Packs?

CodeQL packs are collections of related queries that:
- Can be published to and consumed from GitHub Container Registry (GHCR)
- Allow organizations to create and distribute custom security rules
- Enable centralized management of security queries across multiple repositories
- Support versioning and dependency management

## Prerequisites

- GitHub CLI (`gh`) installed
- CodeQL CLI installed (`codeql --version` to verify)
- A GitHub Personal Access Token (PAT) with `write:packages` scope
- A target organization in GitHub (such as your GHEC org)

## Step 1: Create Your CodeQL Pack Structure

A minimal CodeQL pack requires:

```
globomantics-secure-scan/              # Root directory
├── qlpack.yml                        # Pack configuration
├── queries/                          # Queries organized by language
│   └── javascript/                   # Language-specific directory
│       ├── detect-eval-use.ql        # Security query for eval()
│       ├── http-header-injection.ql  # Security query for header injection
│       └── security-suite.qls        # Query suite combining queries
```

### The qlpack.yml File

```yaml
name: timothywarner-org/globomantics-secure-scan
version: 1.0.0
description: "Globomantics Custom Security Query Pack for JavaScript"
dependencies:
  codeql/javascript-all: "*"
library: false
```

Key fields:
- `name`: Must follow `<scope>/<pack>` format (organization/pack-name)
- `version`: Semantic versioning (MAJOR.MINOR.PATCH)
- `dependencies`: Libraries your queries rely on

## Step 2: Build a Sample Query

Create a simple query to detect `eval()` usage:

```ql
/**
 * @name Use of eval
 * @description Using eval can lead to code injection vulnerabilities.
 * @kind problem
 * @problem.severity warning
 * @id js/globomantics/eval-use
 * @tags security
 *       external/cwe/cwe-95
 */

import javascript

from CallExpr evalCall
where
  evalCall.getCalleeName() = "eval"
  or
  evalCall.getCalleeName().matches("Function%")
  or
  evalCall.getCalleeName() = "setTimeout"
  or
  evalCall.getCalleeName() = "setInterval"
select evalCall, "Potentially unsafe use of " + evalCall.getCalleeName() + "."
```

## Step 3: Create a Query Suite

Query suites allow running multiple queries together. Create `queries/javascript/security-suite.qls`:

```yaml
# Globomantics JavaScript Security Query Suite
- description: Globomantics JavaScript Security Queries
- queries: .
- include:
    id:
      - js/globomantics/eval-use
      - js/globomantics/http-header-injection
```

## Step 4: Authentication

Always authenticate before publishing:

```bash
# Store your token securely as an environment variable
export GITHUB_PAT=your_github_personal_access_token

# Authenticate with GitHub CLI
echo $GITHUB_PAT | gh auth login --with-token
```

## Step 5: Build & Publish Your Pack

The publishing process involves three main steps:

1. **Install dependencies**:
   ```bash
   cd globomantics-secure-scan
   codeql pack install
   ```

2. **Create (build) the pack**:
   ```bash
   codeql pack create
   ```
   This compiles queries and prepares them for distribution.

3. **Publish to GHCR**:
   ```bash
   # Provide your PAT via stdin for authentication
   echo $GITHUB_PAT | codeql pack publish --github-auth-stdin
   ```

## Step 6: Automation Script

For repeatable publishing, create a script like this:

```bash
#!/usr/bin/env bash
set -euo pipefail

# --- Configurable Variables ---
PACK_DIR="globomantics-secure-scan"
GHCR_ORG="your-org-name"
GHCR_REGISTRY="ghcr.io/${GHCR_ORG}"
CODEQL_CLI="codeql" # Assumes codeql is in your PATH

# --- Auth to GHCR ---
if [[ -z "${GITHUB_PAT:-}" ]]; then
  echo "ERROR: Please export GITHUB_PAT with your GitHub token (write:packages scope)."
  exit 1
fi

# Authenticate with GitHub CLI
echo "${GITHUB_PAT}" | gh auth login --with-token

# --- First, install dependencies ---
cd "${PACK_DIR}"
"${CODEQL_CLI}" pack install

# --- Create the CodeQL Pack ---
"${CODEQL_CLI}" pack create

# --- Publish the Pack to GHCR ---
echo "${GITHUB_PAT}" | "${CODEQL_CLI}" pack publish --github-auth-stdin

echo "✅ CodeQL pack published to ${GHCR_REGISTRY}/${PACK_DIR}"
```

## Step 7: Verify Publication

Verify your pack is published:

```bash
# List packages in your organization
gh package list -R your-org/your-repo

# Or visit the web interface
https://github.com/orgs/your-org/packages
```

## Using Your Published Pack

To use your pack in code scanning:

1. **Download the pack**:
   ```bash
   codeql pack download your-org/your-pack-name
   ```

2. **Use the pack in analysis**:
   ```bash
   # Create a database
   codeql database create my-db --language=javascript --source-root=/path/to/code

   # Analyze using your custom pack
   codeql database analyze my-db your-org/your-pack-name --format=sarif-latest --output=results.sarif
   ```

3. **In GitHub Actions workflows**:
   ```yaml
   - uses: github/codeql-action/init@v2
     with:
       languages: javascript
       packs: your-org/your-pack-name@1.0.0
   ```

## Common Troubleshooting

- **Permission denied**: Check your PAT has `write:packages` permissions
- **Cannot find pack**: Verify the scope/name formatting is correct
- **Cannot compile queries**: Ensure dependencies are correctly specified
- **Dependency errors**: Run `codeql pack install` to resolve dependencies

## Next Steps

- Create model packs to extend language support
- Develop language-specific security rules
- Set up CI/CD to automatically publish pack updates
- Share your packs with your security team

Ready to scan your first application with your custom CodeQL queries? Run:
```bash
codeql database analyze your-database your-org/your-pack-name --format=sarif-latest --output=results.sarif
``` 