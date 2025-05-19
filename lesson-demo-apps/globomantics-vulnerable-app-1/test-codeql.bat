@echo off
setlocal

REM Create a logs directory if it doesn't exist
if not exist logs mkdir logs

echo === Testing Globomantics JavaScript Security Queries ===
echo.

REM Step 1: Create a CodeQL database for the app
echo Step 1: Creating CodeQL database...
call codeql database create js-db --language=javascript --source-root=.

REM Step 2: Run each query individually
echo.
echo Step 2: Running individual queries...

REM Detect eval use
echo Testing detect-eval-use query...
call codeql database analyze js-db ..\globomantics-secure-scan\queries\javascript\detect-eval-use.ql --format=sarif-latest --output=logs\eval-results.sarif

REM HTTP header injection
echo Testing http-header-injection query...
call codeql database analyze js-db ..\globomantics-secure-scan\queries\javascript\http-header-injection.ql --format=sarif-latest --output=logs\header-injection-results.sarif

REM Insecure randomness
echo Testing insecure-randomness query...
call codeql database analyze js-db ..\globomantics-secure-scan\queries\javascript\insecure-randomness.ql --format=sarif-latest --output=logs\randomness-results.sarif

REM Step 3: Run the entire security suite
echo.
echo Step 3: Running the complete security suite...
call codeql database analyze js-db ..\globomantics-secure-scan\queries\javascript\security-suite.qls --format=sarif-latest --output=logs\suite-results.sarif

echo.
echo === Testing completed ===
echo Results are saved in the logs directory
echo.
echo Note: To see a summary of findings, review the SARIF files in the logs directory.

endlocal 