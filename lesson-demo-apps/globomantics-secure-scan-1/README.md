# Globomantics JavaScript Security Query Pack

A comprehensive CodeQL query pack for identifying security vulnerabilities in JavaScript applications. This custom query pack can be used with GitHub Advanced Security (GHAS) or with the CodeQL CLI.

## 🔍 Overview

This repository contains custom CodeQL queries designed to help identify security vulnerabilities in JavaScript code. It's designed as a teaching tool for GitHub Enterprise Cloud and CodeQL education.

## 📦 Query Pack Contents

This query pack includes three custom security queries for JavaScript:

- **Detect Eval Use** (`queries/javascript/detect-eval-use.ql`): Identifies potentially dangerous uses of `eval()`, `Function()` constructor, and similar functions that can lead to code injection vulnerabilities (CWE-95).

- **HTTP Header Injection** (`queries/javascript/http-header-injection.ql`): Detects when user-controlled data flows into HTTP headers without proper sanitization, which can lead to header injection attacks (CWE-113).

- **Insecure Randomness** (`queries/javascript/insecure-randomness.ql`): Flags instances where `Math.random()` is used in security-sensitive contexts instead of cryptographically secure alternatives (CWE-338).

These queries are organized in a suite (`queries/javascript/security-suite.qls`) for easy execution.

## 🚀 Usage

### Prerequisites

- [CodeQL CLI](https://github.com/github/codeql-cli-binaries/releases)
- A JavaScript project to analyze
- GitHub account with access to GitHub Container Registry (GHCR)

## 📚 Working with GitHub Container Registry (GHCR)

This query pack is published to GitHub Container Registry, allowing organization-wide access to standardized security queries.

### Authentication with GHCR

Before using this query pack from GHCR, authenticate with your GitHub account:

```bash
# Login to GitHub Container Registry
echo $GITHUB_TOKEN | codeql github login --token-stdin

# Or use a Personal Access Token (PAT) with package read permissions
echo $PAT | codeql github login --token-stdin
```

### Listing Available Query Packs

You can view available query packs in the registry:

```bash
# List all query packs in the organization
codeql pack list --registry=https://ghcr.io timothywarner-org/*
```

### Using the Query Pack from GHCR

Once authenticated, you can use the query pack directly from GHCR:

```bash
# Create a CodeQL database for your project
codeql database create js-db --language=javascript --source-root=/path/to/source

# Run the entire security suite from GHCR
codeql database analyze js-db timothywarner-org/globomantics-security-queries:queries/javascript/security-suite.qls --format=sarif-latest --output=suite-results.sarif

# Run a specific query from GHCR
codeql database analyze js-db timothywarner-org/globomantics-security-queries:queries/javascript/detect-eval-use.ql --format=sarif-latest --output=eval-results.sarif
```

### Using a Specific Version

You can specify a particular version of the query pack:

```bash
# Run with a specific version
codeql database analyze js-db timothywarner-org/globomantics-security-queries@1.0.0:queries/javascript/security-suite.qls --format=sarif-latest --output=suite-results.sarif
```

## 🧪 Developing Custom Query Packs

If you want to create your own custom query pack like this one:

### 1. Set up your repository structure

```
your-query-pack/
├── .github/
│   └── workflows/
│       └── publish-query-pack.yml
├── queries/
│   └── javascript/
│       ├── your-query1.ql
│       ├── your-query2.ql
│       └── security-suite.qls
├── codeql-pack.yml
└── qlpack.yml
```

### 2. Configure pack metadata

Create `codeql-pack.yml`:

```yaml
name: your-org/your-pack-name
version: 1.0.0
description: "Description of your query pack"
license: MIT
defaultSuite: queries/javascript/security-suite.qls
```

Create `qlpack.yml`:

```yaml
name: your-org/your-pack-name
version: 1.0.0
dependencies:
  codeql/javascript-all: "*"
  codeql/javascript-queries: "*"
library: false
```

### 3. Create, test, and publish your pack

```bash
# Create the pack
codeql pack create

# Test a query locally
codeql database analyze path/to/database queries/javascript/your-query.ql

# Publish to GHCR (requires authentication)
codeql pack publish --registry=https://ghcr.io your-org/your-pack-name
```

### 4. Automate publishing with GitHub Actions

Set up a workflow similar to the one in this repository to automatically publish updates to your query pack.

## 🔒 Integration with GitHub Advanced Security

This query pack can be used with GitHub Advanced Security by adding it to your CodeQL workflow:

```yaml
- uses: github/codeql-action/init@v2
  with:
    languages: javascript
    queries: timothywarner-org/globomantics-security-queries@main
```

## 🧪 Testing

For testing these queries, check out our companion repository [globomantics-vulnerable-app](https://github.com/timothywarner-org/globomantics-vulnerable-app), which contains a deliberately vulnerable Express.js application designed to trigger these queries.

## 📚 Educational Purpose

This repository is part of the GitHub Enterprise Cloud training materials created by Tim Warner for Pluralsight. It demonstrates how organizations can create and govern custom CodeQL query packs that can be centrally published to GitHub Container Registry and consumed across multiple repositories.

## 📄 License

MIT 