/**
 * Index router for Globomantics Express Test App
 * Contains intentional security vulnerabilities
 */

const express = require('express');
const router = express.Router();
const fs = require('fs');
const path = require('path');

/* GET home page. */
router.get('/', (req, res) => {
  res.render('index', { 
    title: 'Globomantics Security Test App',
    user: req.session.user || null
  });
});

/* VULNERABILITY: Using Function constructor (equivalent to eval) */
router.post('/process-template', (req, res) => {
  const template = req.body.template;
  const data = req.body.data ? JSON.parse(req.body.data) : {};
  
  try {
    // VULNERABILITY: Using Function constructor with user input
    const templateFn = new Function('data', `
      return \`${template}\`;
    `);
    
    const result = templateFn(data);
    res.send(result);
  } catch (error) {
    res.status(400).send('Error processing template');
  }
});

/* VULNERABILITY: Path traversal in file access */
router.get('/download', (req, res) => {
  const filename = req.query.file;
  
  // VULNERABILITY: Unsanitized file path
  const filePath = path.join(__dirname, '../public/downloads', filename);
  
  fs.readFile(filePath, (err, data) => {
    if (err) {
      return res.status(404).send('File not found');
    }
    
    res.setHeader('Content-Type', 'application/octet-stream');
    res.setHeader('Content-Disposition', `attachment; filename=${filename}`);
    res.send(data);
  });
});

/* VULNERABILITY: HTML injection / XSS */
router.get('/search', (req, res) => {
  const query = req.query.q || '';
  
  // Simulate search results
  const results = [
    { title: 'Result 1', description: 'Description for Result 1' },
    { title: 'Result 2', description: 'Description for Result 2' }
  ];
  
  // VULNERABILITY: Rendering unsanitized user input
  res.render('search', { 
    title: 'Search Results',
    query: query,
    results: results
  });
});

module.exports = router; 