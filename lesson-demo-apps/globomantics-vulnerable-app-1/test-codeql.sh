#!/bin/bash

# Create a logs directory if it doesn't exist
mkdir -p logs

echo "=== Testing Globomantics JavaScript Security Queries ==="
echo

# Step 1: Create a CodeQL database for the app
echo "Step 1: Creating CodeQL database..."
codeql database create js-db --language=javascript --source-root=.

# Step 2: Run each query individually
echo 
echo "Step 2: Running individual queries..."

# Detect eval use
echo "Testing detect-eval-use query..."
codeql database analyze js-db ../globomantics-secure-scan/queries/javascript/detect-eval-use.ql \
  --format=sarif-latest --output=logs/eval-results.sarif

# HTTP header injection
echo "Testing http-header-injection query..."
codeql database analyze js-db ../globomantics-secure-scan/queries/javascript/http-header-injection.ql \
  --format=sarif-latest --output=logs/header-injection-results.sarif

# Insecure randomness
echo "Testing insecure-randomness query..."
codeql database analyze js-db ../globomantics-secure-scan/queries/javascript/insecure-randomness.ql \
  --format=sarif-latest --output=logs/randomness-results.sarif

# Step 3: Run the entire security suite
echo
echo "Step 3: Running the complete security suite..."
codeql database analyze js-db ../globomantics-secure-scan/queries/javascript/security-suite.qls \
  --format=sarif-latest --output=logs/suite-results.sarif

echo
echo "=== Testing completed ==="
echo "Results are saved in the logs directory"

# Display summary of findings
echo
echo "=== Summary of Findings ==="
echo "Eval use: $(grep -c "ruleId.*js/detect-eval-use" logs/eval-results.sarif) issues found"
echo "HTTP header injection: $(grep -c "ruleId.*js/http-header-injection" logs/header-injection-results.sarif) issues found"
echo "Insecure randomness: $(grep -c "ruleId.*js/insecure-randomness" logs/randomness-results.sarif) issues found"
echo
echo "For detailed results, check the SARIF files in the logs directory." 