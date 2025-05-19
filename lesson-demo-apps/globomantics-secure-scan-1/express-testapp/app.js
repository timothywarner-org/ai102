/**
 * Globomantics Express Test App
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
const dotenv = require('dotenv');

// Import routes
const indexRouter = require('./routes/index');
const usersRouter = require('./routes/users');
const adminRouter = require('./routes/admin');
const apiRouter = require('./routes/api');

// Load environment variables
dotenv.config();

// Initialize Express app
const app = express();

// VULNERABILITY: Weak session configuration
app.use(session({
  secret: 'globomantics-secret-key', // INSECURE: Hardcoded secret
  resave: false,
  saveUninitialized: true,
  cookie: { secure: false } // INSECURE: Not using secure cookies
}));

// View engine setup
app.set('views', path.join(__dirname, 'views'));
app.set('view engine', 'ejs');

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(express.static(path.join(__dirname, 'public')));

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

// Routes
app.use('/', indexRouter);
app.use('/users', usersRouter);
app.use('/admin', adminRouter);
app.use('/api', apiRouter);

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
});

module.exports = app; 