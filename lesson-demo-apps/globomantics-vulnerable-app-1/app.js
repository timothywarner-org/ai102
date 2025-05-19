/**
 * Globomantics Vulnerable App
 * 
 * IMPORTANT: This application contains INTENTIONAL SECURITY VULNERABILITIES
 * for educational purposes. DO NOT deploy in a production environment.
 */

// Import required modules
const express = require('express');
const path = require('path');
const fs = require('fs');
const cookieParser = require('cookie-parser');
const session = require('express-session');

// Initialize Express app
const app = express();

// VULNERABILITY: Weak session configuration
app.use(session({
  secret: 'globomantics-secret-key', // INSECURE: Hardcoded secret
  resave: false,
  saveUninitialized: true,
  cookie: { secure: false } // INSECURE: Not using secure cookies
}));

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));

// Create logs directory if it doesn't exist
const logsDir = path.join(__dirname, 'logs');
if (!fs.existsSync(logsDir)) {
  fs.mkdirSync(logsDir, { recursive: true });
}

// VULNERABILITY: Custom logging middleware with potential injection issue
app.use((req, res, next) => {
  const logEntry = `${new Date().toISOString()} - ${req.method} ${req.url} - ${req.ip}`;
  
  // VULNERABILITY: Unsafe file operations with unsanitized input
  const logFile = path.join(__dirname, 'logs', 'access.log');
  fs.appendFile(logFile, logEntry + '\n', (err) => {
    if (err) {
      console.error('Error writing to log file:', err);
    }
  });
  
  next();
});

// Basic routes
app.get('/', (req, res) => {
  const htmlContent = `
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Globomantics Vulnerable App</title>
      <link rel="stylesheet" href="/css/style.css">
    </head>
    <body>
      <div class="container">
        <h1>Globomantics Vulnerable App</h1>
        
        <div class="warning">
          <strong>WARNING:</strong> This application contains intentional security vulnerabilities for educational purposes.
          <strong>DO NOT</strong> deploy in a production environment.
        </div>
        
        <h2>Vulnerabilities Demo</h2>
        
        <div class="endpoint">
          <h3>1. Code Injection (eval)</h3>
          <p>This endpoint uses <code>eval()</code> to execute user-provided code:</p>
          <form id="calculate-form">
            <input type="text" id="formula" placeholder="Enter a formula (e.g., 2+2)" required>
            <button type="submit">Calculate</button>
          </form>
          <p>Result: <span id="result"></span></p>
          <p><strong>Try:</strong> <code>2+2</code> or <code>console.log('XSS'); 5</code></p>
        </div>
        
        <div class="endpoint">
          <h3>2. HTTP Header Injection</h3>
          <p>This endpoint places user input directly in HTTP headers:</p>
          <form id="redirect-form">
            <input type="text" id="redirect-url" placeholder="Enter a URL" value="https://example.com" required>
            <button type="submit">Redirect</button>
          </form>
          <p><strong>Try:</strong> <code>https://example.com%0D%0AX-Injected: malicious-value</code></p>
        </div>
        
        <div class="endpoint">
          <h3>3. Insecure Randomness</h3>
          <p>This endpoint uses <code>Math.random()</code> for token generation:</p>
          <button id="generate-token-btn">Generate Token</button>
          <p>Token: <span id="token-result"></span></p>
        </div>
      </div>
      
      <script src="/js/main.js"></script>
    </body>
    </html>
  `;
  
  res.send(htmlContent);
});

// VULNERABILITY: Dangerous eval endpoint
app.get('/calculate', (req, res) => {
  const formula = req.query.formula;
  let result;
  
  try {
    // VULNERABILITY: Using eval with user input
    result = eval(formula);
    res.json({ result });
  } catch (error) {
    res.status(400).json({ error: 'Invalid formula' });
  }
});

// VULNERABILITY: HTTP Header Injection
app.get('/redirect', (req, res) => {
  const redirectUrl = req.query.url;
  
  // VULNERABILITY: Using user input directly in headers
  res.setHeader('Location', redirectUrl);
  res.status(302).send('Redirecting...');
});

// VULNERABILITY: Insecure random token generation
app.post('/generate-token', (req, res) => {
  // VULNERABILITY: Using Math.random() for tokens
  const token = Math.random().toString(36).substring(2) + Math.random().toString(36).substring(2);
  res.json({ token });
});

// Error handler
app.use((err, req, res, next) => {
  // VULNERABILITY: Exposing sensitive error details to clients
  res.status(err.status || 500).json({
    message: err.message,
    stack: err.stack
  });
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
  console.log(`Open http://localhost:${PORT} in your browser to see the vulnerable app`);
});

module.exports = app; 