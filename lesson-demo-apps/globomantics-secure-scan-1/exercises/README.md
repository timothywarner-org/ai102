# CodeQL Exercises

This directory contains exercises for learning to write and use CodeQL queries. Use these with the Globomantics JavaScript Security Query Pack.

## Exercise 1: Run the Existing Queries

Practice running the pre-built queries against the example vulnerable application:

1. Create a CodeQL database:
   ```bash
   codeql database create my-example-db --language=javascript --source-root=.
   ```

2. Run the security suite:
   ```bash
   codeql database analyze my-example-db globomantics/javascript-security-queries:security-suite.qls --format=sarif-latest --output=suite-results.sarif
   ```

3. Examine the results in VS Code with the CodeQL extension or convert to a more readable format:
   ```bash
   codeql bqrs decode --format=csv suite-results.bqrs > suite-results.csv
   ```

## Exercise 2: Modify an Existing Query

Modify the `insecure-randomness.ql` query to include other insecure random number generators:

1. Copy the query to a new file: `my-insecure-randomness.ql`
2. Add additional patterns to detect (e.g., including `Math.floor(Math.random() * max)`)
3. Run your modified query against the database
4. Compare results with the original

## Exercise 3: Create a New Query

Create a new query to detect exposed secrets in JavaScript code:

1. Start with a template for a new query: `exposed-secrets.ql`
2. Define patterns for hardcoded credentials and secrets
3. Write the query logic to identify these patterns
4. Test your query against the example application
5. Add your query to the security suite

## Exercise 4: Automate with GitHub Actions

1. Create a GitHub repository for your JavaScript project
2. Set up a CodeQL workflow with your custom queries
3. Validate that CodeQL runs on push/pull requests
4. Review the security findings in the Security tab

## Resources

- [CodeQL Tutorial for JavaScript](https://codeql.github.com/docs/writing-codeql-queries/codeql-queries/)
- [Query Help for JavaScript](https://codeql.github.com/codeql-query-help/javascript/)
- [CodeQL Language Reference](https://codeql.github.com/docs/ql-language-reference/) 