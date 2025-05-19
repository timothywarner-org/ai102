/**
 * API router for Globomantics Express Test App
 * Contains intentional security vulnerabilities
 */

const express = require('express');
const router = express.Router();
const multer = require('multer');
const jwt = require('jsonwebtoken');

// Configure file upload
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, 'public/uploads/');
  },
  filename: (req, file, cb) => {
    // VULNERABILITY: Using original filename without proper sanitization
    cb(null, file.originalname);
  }
});

const upload = multer({ storage: storage });

// VULNERABILITY: Weak token validation
const validateToken = (req, res, next) => {
  const token = req.headers['authorization'];
  
  if (!token) {
    return res.status(401).json({ message: 'No token provided' });
  }
  
  try {
    // VULNERABILITY: Not properly handling the Bearer prefix
    // Should be: const decoded = jwt.verify(token.split(' ')[1], process.env.JWT_SECRET);
    const decoded = jwt.verify(token, 'GLOBOMANTICS_JWT_SECRET_KEY');
    req.user = decoded;
    next();
  } catch (err) {
    return res.status(401).json({ message: 'Invalid token' });
  }
};

// API endpoints
router.get('/products', (req, res) => {
  // Simple mock data
  const products = [
    { id: 1, name: 'Product 1', price: 99.99 },
    { id: 2, name: 'Product 2', price: 149.99 },
    { id: 3, name: 'Product 3', price: 199.99 }
  ];
  
  res.json(products);
});

// VULNERABILITY: Insecure file upload
router.post('/upload', validateToken, upload.single('file'), (req, res) => {
  if (!req.file) {
    return res.status(400).json({ message: 'No file uploaded' });
  }
  
  // VULNERABILITY: Returning the path without checking file type or sanitizing filename
  res.json({
    message: 'File uploaded successfully',
    filename: req.file.originalname,
    path: `/uploads/${req.file.originalname}`
  });
});

// VULNERABILITY: Using setTimeout with string argument (eval-like)
router.post('/delayed-task', validateToken, (req, res) => {
  const { code, delay } = req.body;
  
  if (!code || !delay) {
    return res.status(400).json({ message: 'Code and delay parameters are required' });
  }
  
  // VULNERABILITY: Using setTimeout with string argument (similar to eval)
  setTimeout(code, parseInt(delay, 10));
  
  res.json({ message: 'Task scheduled' });
});

// VULNERABILITY: Prototype pollution
router.post('/config', validateToken, (req, res) => {
  // Get the update object from request body
  const updates = req.body;
  
  // VULNERABILITY: Recursively merging without checking for prototype properties
  const mergeObjects = (target, source) => {
    for (const key in source) {
      if (typeof source[key] === 'object' && source[key] !== null) {
        if (!target[key]) {
          target[key] = {};
        }
        mergeObjects(target[key], source[key]);
      } else {
        target[key] = source[key];
      }
    }
    return target;
  };
  
  // App configuration (would normally be in a separate file)
  const appConfig = {
    appName: 'Globomantics API',
    version: '1.0.0',
    settings: {
      cacheEnabled: true,
      logLevel: 'info'
    }
  };
  
  // VULNERABILITY: Merging user input directly into configuration
  const newConfig = mergeObjects(appConfig, updates);
  
  res.json({
    message: 'Configuration updated',
    config: newConfig
  });
});

// VULNERABILITY: Insecure direct object reference (IDOR)
router.get('/users/:id/profile', (req, res) => {
  const userId = req.params.id;
  
  // Mock user data
  const users = {
    '1': {
      id: 1,
      username: 'admin',
      email: 'admin@globomantics.com',
      role: 'admin',
      ssn: '123-45-6789' // Sensitive information
    },
    '2': {
      id: 2,
      username: 'user',
      email: 'user@globomantics.com',
      role: 'user',
      ssn: '987-65-4321' // Sensitive information
    }
  };
  
  // VULNERABILITY: No authorization check, directly using the ID parameter
  const user = users[userId];
  
  if (!user) {
    return res.status(404).json({ message: 'User not found' });
  }
  
  res.json(user);
});

module.exports = router; 