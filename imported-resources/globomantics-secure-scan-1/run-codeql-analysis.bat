@echo off
:: Globomantics CodeQL Analysis Script for Windows
:: This script demonstrates how to run CodeQL analysis using the CLI
:: and our custom query pack.

echo ====================================================
echo   Globomantics CodeQL Analysis Demo Script
echo ====================================================

:: Set the database name
set DB_NAME=globomantics-js-db

:: Check if CodeQL CLI is installed
where codeql >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo CodeQL CLI not found. Please install it first.
    echo Visit: https://github.com/github/codeql-cli-binaries/releases
    exit /b 1
)

echo Step 1: Creating CodeQL database for JavaScript
echo Command: codeql database create %DB_NAME% --language=javascript --source-root=.
echo This may take a few minutes...

codeql database create %DB_NAME% --language=javascript --source-root=.

echo Step 2: Running the entire custom query suite
echo Command: codeql database analyze %DB_NAME% globomantics/javascript-security-queries:security-suite.qls --format=sarif-latest --output=suite-results.sarif

codeql database analyze %DB_NAME% globomantics/javascript-security-queries:security-suite.qls --format=sarif-latest --output=suite-results.sarif

echo Step 3: Running individual queries

echo 3.1: Running the detect-eval-use query
echo Command: codeql database analyze %DB_NAME% globomantics/javascript-security-queries:queries/javascript/detect-eval-use.ql --format=sarif-latest --output=eval-results.sarif

codeql database analyze %DB_NAME% globomantics/javascript-security-queries:queries/javascript/detect-eval-use.ql --format=sarif-latest --output=eval-results.sarif

echo 3.2: Running the http-header-injection query
echo Command: codeql database analyze %DB_NAME% globomantics/javascript-security-queries:queries/javascript/http-header-injection.ql --format=sarif-latest --output=header-injection-results.sarif

codeql database analyze %DB_NAME% globomantics/javascript-security-queries:queries/javascript/http-header-injection.ql --format=sarif-latest --output=header-injection-results.sarif

echo 3.3: Running the insecure-randomness query
echo Command: codeql database analyze %DB_NAME% globomantics/javascript-security-queries:queries/javascript/insecure-randomness.ql --format=sarif-latest --output=randomness-results.sarif

codeql database analyze %DB_NAME% globomantics/javascript-security-queries:queries/javascript/insecure-randomness.ql --format=sarif-latest --output=randomness-results.sarif

echo Step 4: Convert SARIF to more readable format
echo Command: codeql bqrs decode --format=csv suite-results.bqrs.* ^> suite-results.csv

:: Use dir to find the bqrs files
for /f "tokens=*" %%f in ('dir /b suite-results.bqrs.*') do (
    echo Converting %%f to CSV
    codeql bqrs decode --format=csv "%%f" > "suite-results.csv"
)

echo Analysis complete! Results are available in the following files:
echo  - suite-results.sarif (All queries)
echo  - eval-results.sarif (Eval use)
echo  - header-injection-results.sarif (HTTP header injection)
echo  - randomness-results.sarif (Insecure randomness)
echo  - suite-results.csv (CSV format)

echo ====================================================
echo   Tips for reviewing SARIF results:
echo ====================================================
echo 1. Use a SARIF viewer extension in VS Code to visualize results
echo 2. GitHub's Security tab can display these results
echo 3. For command-line review, use the CSV output
echo 4. Try opening the CSV file in Excel or a text editor
echo ====================================================

:: Clean up temporary files
set /p keep_db=Do you want to keep the CodeQL database? (y/n): 
if /i not "%keep_db%"=="y" (
    echo Removing database directory: %DB_NAME%
    rmdir /s /q "%DB_NAME%"
)

echo Done!
pause 