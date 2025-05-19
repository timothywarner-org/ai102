/**
 * Admin router for Globomantics Express Test App
 * Contains intentional security vulnerabilities
 */

const express = require('express');
const router = express.Router();
const path = require('path');
const fs = require('fs');
const { exec } = require('child_process');

// VULNERABILITY: Weak authentication middleware
const isAdmin = (req, res, next) => {
  // VULNERABILITY: Not properly validating the token
  const token = req.cookies.auth_token || req.headers['x-auth-token'];
  
  if (!token) {
    return res.status(401).json({ message: 'Authentication required' });
  }
  
  // VULNERABILITY: Just checking if user role contains 'admin', no proper validation
  // In a real app, would verify the JWT token
  if (req.session.user && req.session.user.role && req.session.user.role.includes('admin')) {
    next();
  } else {
    res.status(403).json({ message: 'Admin access required' });
  }
};

// Admin dashboard
router.get('/', isAdmin, (req, res) => {
  res.render('admin/dashboard', {
    title: 'Admin Dashboard',
    user: req.session.user
  });
});

// VULNERABILITY: Command injection in system operations
router.post('/system/ping', isAdmin, (req, res) => {
  const { host } = req.body;
  
  if (!host) {
    return res.status(400).json({ message: 'Host parameter is required' });
  }
  
  // VULNERABILITY: Command injection by passing unsanitized input to exec
  const command = `ping -c 4 ${host}`;
  
  exec(command, (error, stdout, stderr) => {
    if (error) {
      return res.status(500).json({ message: 'Error executing command', error: error.message });
    }
    
    res.json({
      command: command,
      output: stdout
    });
  });
});

// VULNERABILITY: Unsafe file operations
router.post('/logs/view', isAdmin, (req, res) => {
  const { logFile } = req.body;
  
  // VULNERABILITY: Path traversal - allowing user to specify any log file
  const logPath = path.join(__dirname, '../logs', logFile || 'app.log');
  
  fs.readFile(logPath, 'utf8', (err, data) => {
    if (err) {
      return res.status(500).json({ message: 'Error reading log file', error: err.message });
    }
    
    // VULNERABILITY: Not properly sanitizing log data for XSS
    res.send(`
      <h1>Log File: ${logFile}</h1>
      <pre>${data}</pre>
    `);
  });
});

// VULNERABILITY: SQL Injection (simulated)
router.get('/users/search', isAdmin, (req, res) => {
  const { query } = req.query;
  
  if (!query) {
    return res.status(400).json({ message: 'Query parameter is required' });
  }
  
  // VULNERABILITY: String concatenation in "SQL" query
  // This is a simulated SQL injection as we're not actually connecting to a database
  // But the pattern of string concatenation would lead to SQL injection in a real app
  const sqlQuery = `SELECT * FROM users WHERE username LIKE '%${query}%' OR email LIKE '%${query}%'`;
  
  // In a real app, this would execute the query against a database
  // Here we're just simulating the behavior
  console.log('Executing query:', sqlQuery);
  
  // Simulate database results
  const results = [
    { id: 1, username: 'admin', email: 'admin@globomantics.com', role: 'admin' },
    { id: 2, username: 'user', email: 'user@globomantics.com', role: 'user' }
  ].filter(user => 
    user.username.includes(query) || user.email.includes(query)
  );
  
  res.json({
    query: sqlQuery,
    results: results
  });
});

module.exports = router; 