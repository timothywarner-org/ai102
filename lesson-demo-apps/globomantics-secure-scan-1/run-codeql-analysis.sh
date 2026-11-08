#!/bin/bash
# Globomantics CodeQL Analysis Script
# This script demonstrates how to run CodeQL analysis using the CLI
# and our custom query pack.

# Set colors for better readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}  Globomantics CodeQL Analysis Demo Script${NC}"
echo -e "${BLUE}====================================================${NC}"

# Set the database name
DB_NAME="globomantics-js-db"

# Check if CodeQL CLI is installed
if ! command -v codeql &> /dev/null; then
    echo -e "${YELLOW}CodeQL CLI not found. Please install it first.${NC}"
    echo "Visit: https://github.com/github/codeql-cli-binaries/releases"
    exit 1
fi

echo -e "${GREEN}Step 1: Creating CodeQL database for JavaScript${NC}"
echo "Command: codeql database create $DB_NAME --language=javascript --source-root=."
echo -e "${YELLOW}This may take a few minutes...${NC}"

codeql database create $DB_NAME --language=javascript --source-root=.

echo -e "${GREEN}Step 2: Running the entire custom query suite${NC}"
echo "Command: codeql database analyze $DB_NAME globomantics/javascript-security-queries:security-suite.qls --format=sarif-latest --output=suite-results.sarif"

codeql database analyze $DB_NAME globomantics/javascript-security-queries:security-suite.qls --format=sarif-latest --output=suite-results.sarif

echo -e "${GREEN}Step 3: Running individual queries${NC}"

echo -e "${BLUE}3.1: Running the detect-eval-use query${NC}"
echo "Command: codeql database analyze $DB_NAME globomantics/javascript-security-queries:queries/javascript/detect-eval-use.ql --format=sarif-latest --output=eval-results.sarif"

codeql database analyze $DB_NAME globomantics/javascript-security-queries:queries/javascript/detect-eval-use.ql --format=sarif-latest --output=eval-results.sarif

echo -e "${BLUE}3.2: Running the http-header-injection query${NC}"
echo "Command: codeql database analyze $DB_NAME globomantics/javascript-security-queries:queries/javascript/http-header-injection.ql --format=sarif-latest --output=header-injection-results.sarif"

codeql database analyze $DB_NAME globomantics/javascript-security-queries:queries/javascript/http-header-injection.ql --format=sarif-latest --output=header-injection-results.sarif

echo -e "${BLUE}3.3: Running the insecure-randomness query${NC}"
echo "Command: codeql database analyze $DB_NAME globomantics/javascript-security-queries:queries/javascript/insecure-randomness.ql --format=sarif-latest --output=randomness-results.sarif"

codeql database analyze $DB_NAME globomantics/javascript-security-queries:queries/javascript/insecure-randomness.ql --format=sarif-latest --output=randomness-results.sarif

echo -e "${GREEN}Step 4: Convert SARIF to more readable format${NC}"
echo "Command: codeql bqrs decode --format=csv suite-results.bqrs.* > suite-results.csv"

# Use a wildcard as CodeQL creates numbered files
for bqrs_file in suite-results.bqrs.*; do
    if [ -f "$bqrs_file" ]; then
        base_name=$(basename "$bqrs_file" | cut -d. -f1-2)
        echo "Converting $bqrs_file to CSV"
        codeql bqrs decode --format=csv "$bqrs_file" > "${base_name}.csv"
    fi
done

echo -e "${GREEN}Analysis complete! Results are available in the following files:${NC}"
echo " - suite-results.sarif (All queries)"
echo " - eval-results.sarif (Eval use)"
echo " - header-injection-results.sarif (HTTP header injection)"
echo " - randomness-results.sarif (Insecure randomness)"
echo " - suite-results.csv (CSV format)"

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}  Tips for reviewing SARIF results:${NC}"
echo -e "${BLUE}====================================================${NC}"
echo "1. Use a SARIF viewer extension in VS Code to visualize results"
echo "2. GitHub's Security tab can display these results"
echo "3. For command-line review, use the CSV output"
echo "4. Try: cat suite-results.csv | column -t -s, | less -S"
echo -e "${BLUE}====================================================${NC}"

# Clean up temporary files
echo -e "${GREEN}Do you want to keep the CodeQL database? (y/n)${NC}"
read -r keep_db
if [[ $keep_db != "y" && $keep_db != "Y" ]]; then
    echo "Removing database directory: $DB_NAME"
    rm -rf "$DB_NAME"
fi

echo "Done!" 