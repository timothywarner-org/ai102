/**
 * Users router for Globomantics Express Test App
 * Contains intentional security vulnerabilities
 */

const express = require('express');
const router = express.Router();
const jwt = require('jsonwebtoken');
const bcrypt = require('bcrypt');

// Mock user database (in a real app, this would be in a database)
const users = [
  {
    id: 1,
    username: 'admin',
    // VULNERABILITY: Hardcoded credentials
    password: '$2b$10$zGqH9BzUZA4y1n/JaQB0FeNMaRvC9WAZ4HbHb2JTOqlOIBwvX0JpS', // 'admin123'
    email: 'admin@globomantics.com',
    role: 'admin'
  },
  {
    id: 2,
    username: 'user',
    // VULNERABILITY: Hardcoded credentials
    password: '$2b$10$NXxOtKRjEUJq0T7Bnyq.LeEzE9WzRDh9LFEiXOBs2T6jlpRR7lJz.', // 'password123'
    email: 'user@globomantics.com',
    role: 'user'
  }
];

/* GET users listing. */
router.get('/', (req, res) => {
  // VULNERABILITY: No authentication check, exposing all users
  res.json(users.map(user => {
    // At least don't expose the password hashes
    const { password, ...userWithoutPassword } = user;
    return userWithoutPassword;
  }));
});

/* User login */
router.post('/login', (req, res) => {
  const { username, password } = req.body;
  
  // Find user
  const user = users.find(u => u.username === username);
  
  if (!user) {
    // VULNERABILITY: Information disclosure in error messages
    return res.status(400).json({ message: 'User not found' });
  }
  
  // Validate password
  bcrypt.compare(password, user.password, (err, result) => {
    if (err || !result) {
      // VULNERABILITY: Information disclosure in error messages
      return res.status(400).json({ message: 'Invalid password' });
    }
    
    // VULNERABILITY: Weak JWT configuration
    const token = jwt.sign(
      { id: user.id, username: user.username, role: user.role },
      // VULNERABILITY: Hardcoded secret
      'GLOBOMANTICS_JWT_SECRET_KEY', 
      { expiresIn: '24h' }
    );
    
    // VULNERABILITY: Insecure cookie settings
    res.cookie('auth_token', token, { 
      httpOnly: false,  // Should be true
      secure: false     // Should be true in production
    });
    
    res.json({
      message: 'Login successful',
      user: {
        id: user.id,
        username: user.username,
        email: user.email,
        role: user.role
      },
      token: token
    });
  });
});

/* VULNERABILITY: Insecure random password reset token */
router.post('/forgot-password', (req, res) => {
  const { email } = req.body;
  
  // Find user
  const user = users.find(u => u.email === email);
  
  if (!user) {
    return res.status(200).json({ message: 'If your email is registered, a reset link will be sent.' });
  }
  
  // VULNERABILITY: Using Math.random() for security token
  const resetToken = Math.random().toString(36).substring(2);
  
  // In a real app, would store the token and send an email
  // For demo purposes, just return it
  res.json({
    message: 'Reset token generated',
    // VULNERABILITY: Exposing the token in response
    token: resetToken,
    userId: user.id
  });
});

/* User registration */
router.post('/register', (req, res) => {
  const { username, password, email } = req.body;
  
  // VULNERABILITY: Weak password hashing (should use higher cost factor)
  bcrypt.hash(password, 5, (err, hash) => {
    if (err) {
      return res.status(500).json({ message: 'Error creating user' });
    }
    
    // Create new user
    const newUser = {
      id: users.length + 1,
      username,
      password: hash,
      email,
      role: 'user'
    };
    
    // Add to "database"
    users.push(newUser);
    
    res.status(201).json({
      message: 'User created successfully',
      user: {
        id: newUser.id,
        username: newUser.username,
        email: newUser.email
      }
    });
  });
});

module.exports = router; 