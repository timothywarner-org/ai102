# Globomantics Vulnerable App

A deliberately vulnerable Express.js application designed for testing and demonstrating CodeQL security queries. This repo demonstrates how a project can consume a centrally governed CodeQL query pack from an organization repository.

## ⚠️ WARNING

This application contains **INTENTIONAL SECURITY VULNERABILITIES** for educational purposes. **DO NOT** deploy in a production environment or expose to the internet.

## 🔍 Purpose & Architecture

This app serves as a test bed for the [Globomantics JavaScript Security Query Pack](https://github.com/timothywarner-org/globomantics-secure-scan), showcasing how CodeQL can identify common security issues in JavaScript applications.

### Enterprise Security Architecture

The project demonstrates a complete enterprise security scanning solution:

```
┌─────────────────────────┐      ┌─────────────────────────┐
│                         │      │                         │
│  Globomantics Secure    │      │  Vulnerable App Repo    │
│  Scan Repository        │◄─────┤  (This Repository)      │
│  (Central Query Pack)   │      │                         │
│                         │      │                         │
└─────────────────────────┘      └─────────────────────────┘
         ▲                                    │
         │                                    ▼
         │                        ┌─────────────────────────┐
         │                        │                         │
         └────────────────────────┤  GitHub Actions CI/CD   │
                                  │  CodeQL Workflow        │
                                  │                         │
                                  └─────────────────────────┘
```

1. **Centralized Security Governance**: Custom security queries maintained in a central repository
2. **Decentralized Implementation**: Individual application repositories reference the central query pack
3. **Automated Analysis**: GitHub Actions workflow runs scans on every PR, push to main, and weekly

## 🔐 Vulnerabilities

This application contains the following intentional vulnerabilities to demonstrate CodeQL capabilities:

### 1. Code Injection (CWE-94)
The `/calculate` endpoint uses `eval()` to execute user-provided JavaScript code without proper validation.

```javascript
// VULNERABILITY: Using eval with user input
app.get('/calculate', (req, res) => {
  const formula = req.query.formula;
  let result;
  
  try {
    result = eval(formula); // Vulnerable code!
    res.json({ result });
  } catch (error) {
    res.status(400).json({ error: 'Invalid formula' });
  }
});
```

**Exploitation**: `http://localhost:3000/calculate?formula=console.log(process.env);return+1`

**Mitigation**: Use a dedicated math expression parser library or sanitize and validate user inputs.

### 2. HTTP Header Injection (CWE-113)
The `/redirect` endpoint places user input directly into HTTP headers without sanitization.

```javascript
// VULNERABILITY: Using user input directly in headers
app.get('/redirect', (req, res) => {
  const redirectUrl = req.query.url;
  
  res.setHeader('Location', redirectUrl); // Vulnerable code!
  res.status(302).send('Redirecting...');
});
```

**Exploitation**: `http://localhost:3000/redirect?url=https://example.com%0D%0AX-Injected:malicious-value`

**Mitigation**: Validate URL format and sanitize inputs before including in headers.

### 3. Insecure Randomness (CWE-338)
The `/generate-token` endpoint uses `Math.random()` for security-sensitive operations like token generation.

```javascript
// VULNERABILITY: Using Math.random() for tokens
app.post('/generate-token', (req, res) => {
  const token = Math.random().toString(36).substring(2) + 
                Math.random().toString(36).substring(2); // Vulnerable code!
  res.json({ token });
});
```

**Exploitation**: Tokens generated with Math.random() are predictable and can be brute-forced.

**Mitigation**: Use `crypto.randomBytes()` or `crypto.randomUUID()` for cryptographically secure random values.

### 4. Information Exposure (CWE-200)
The error handler exposes sensitive stack traces to users.

```javascript
// VULNERABILITY: Exposing sensitive error details to clients
app.use((err, req, res, next) => {
  res.status(err.status || 500).json({
    message: err.message,
    stack: err.stack // Vulnerable code!
  });
});
```

**Mitigation**: Log detailed errors server-side but return generic error messages to clients.

### 5. Hard-coded Secrets (CWE-798)
The session configuration uses a hard-coded secret key.

```javascript
// VULNERABILITY: Weak session configuration
app.use(session({
  secret: 'globomantics-secret-key', // Vulnerable code!
  resave: false,
  saveUninitialized: true,
  cookie: { secure: false } // Also insecure
}));
```

**Mitigation**: Store secrets in environment variables or secure secret management solutions.

## 📋 Installation

```bash
# Clone the repository
git clone https://github.com/timothywarner-org/globomantics-vulnerable-app.git

# Change to the project directory
cd globomantics-vulnerable-app

# Install dependencies
npm install

# Start the application
npm start
```

## 🚀 Usage

The application runs on `http://localhost:3000` by default and provides an interactive web interface to test the vulnerabilities.

### Testing Vulnerabilities

| Vulnerability | Test URL/Method | Example Payload |
|---------------|----------------|----------------|
| Code Injection | `/calculate?formula=[payload]` | `2*3;console.log('Injected!')`|
| Header Injection | `/redirect?url=[payload]` | `https://example.com%0D%0AX-Injected:value` |
| Insecure Randomness | POST to `/generate-token` | N/A - observe token patterns |

## 🔎 CodeQL Analysis Setup

### GitHub Actions Workflow

This repository demonstrates two different methods for using custom CodeQL query packs:

#### Method 1: Direct Repository Reference

```yaml
- name: Initialize CodeQL
  uses: github/codeql-action/init@v2
  with:
    languages: javascript
    queries: timothywarner-org/globomantics-secure-scan@main
    packs: +security-extended,security-and-quality
```

This method directly references the query pack from an organization repository, which is useful for:
- Rapid development and testing of queries
- Transparent change tracking and versioning through Git
- Simplified pull request workflows for query improvements

#### Method 2: GitHub Container Registry (GHCR) Package

```yaml
- name: Initialize CodeQL
  uses: github/codeql-action/init@v2
  with:
    languages: javascript
    packs: +security-extended,security-and-quality,timothywarner-org/globomantics-secure-scan@1.0.0
```

This method uses published CodeQL packs from GitHub Container Registry, which provides:
- Immutable versioned packages
- Enhanced performance for large-scale deployments
- Separation between query development and consumption
- Centralized package distribution

You can manually trigger either approach using the workflow_dispatch inputs in GitHub Actions.

### Publishing CodeQL Packs to GHCR

To publish a CodeQL pack to GHCR, you can use:

```bash
# Authenticate with GitHub Container Registry
echo $GITHUB_TOKEN | codeql pack login --repository=timothywarner-org/globomantics-secure-scan

# Publish the pack
codeql pack publish
```

You can also install the published pack using:

```bash
# Download and install the pack
codeql pack download timothywarner-org/globomantics-secure-scan@1.0.0
```

For automated publishing, see the `publish-codeql-pack.sh` script in the globomantics-secure-scan repository.

### Custom Query Pack Structure

The `globomantics-secure-scan` repository contains:

```
globomantics-secure-scan/
├── queries/
│   └── javascript/
│       ├── detect-eval-use.ql          # Detects dangerous eval() usage
│       ├── http-header-injection.ql    # Finds header injection vulnerabilities
│       ├── insecure-randomness.ql      # Identifies insecure randomness
│       └── security-suite.qls          # Query suite that combines all queries
├── codeql-pack.yml                     # Pack configuration
└── qlpack.yml                          # Legacy pack configuration
```

### Local Testing

For local testing, use the provided scripts:

```bash
# On Linux/macOS
./test-codeql.sh

# On Windows
test-codeql.bat
```

These scripts:
1. Create a CodeQL database for the application
2. Run each query individually to detect specific vulnerabilities
3. Run the complete security suite
4. Generate SARIF files with the results

Example command:
```bash
codeql database analyze js-db ../globomantics-secure-scan/queries/javascript/detect-eval-use.ql --format=sarif-latest --output=logs/eval-results.sarif
```

## 📚 Learning Resources

### CodeQL Learning Path

1. **Basics**: [Introduction to CodeQL](https://codeql.github.com/docs/codeql-overview/)
2. **Query Language**: [Learning CodeQL](https://codeql.github.com/docs/writing-codeql-queries/)
3. **Advanced**: [Creating custom queries](https://codeql.github.com/docs/writing-codeql-queries/advanced-topics/)

### OWASP References

- [OWASP Top 10](https://owasp.org/Top10/)
- [OWASP JavaScript Security Guide](https://cheatsheetseries.owasp.org/cheatsheets/Nodejs_Security_Cheat_Sheet.html)

### GitHub Advanced Security

- [GitHub CodeQL Documentation](https://docs.github.com/en/code-security/code-scanning/automatically-scanning-your-code-for-vulnerabilities-and-errors/about-code-scanning-with-codeql)
- [Custom CodeQL Packs](https://docs.github.com/en/code-security/codeql-cli/using-the-codeql-cli/creating-and-working-with-codeql-packs)

## 🎓 Educational Purpose

This repository is part of the GitHub Enterprise Cloud training materials created by Tim Warner for Pluralsight. It showcases how organizations can leverage GitHub Advanced Security with custom CodeQL query packs to enhance their security posture.

The repository demonstrates real-world enterprise security scanning patterns:
- **Centralized Security Governance**: Security teams maintain queries in one place
- **Developer Empowerment**: Easy integration into CI/CD pipelines
- **Shift-Left Security**: Early vulnerability detection in the development process

## 📄 License

MIT

## 🤝 Contributing

Contributions to enhance the educational value of this project are welcome. Please submit PRs with:
- Additional vulnerabilities to demonstrate
- Improved documentation
- New CodeQL queries to detect other issues

## 🔗 Related Projects

- [Globomantics Secure Scan](https://github.com/timothywarner-org/globomantics-secure-scan) - The custom CodeQL query pack
- [OWASP NodeGoat](https://github.com/OWASP/NodeGoat) - Another vulnerable Node.js app for learning 