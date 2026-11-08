/**
 * User model for Globomantics Express Test App
 * Contains intentional security vulnerabilities
 */

// This is a simple mock model file - in a real application,
// this would interact with a database using Mongoose or another ORM

// Dangerous operations that would be caught by CodeQL
const crypto = require('crypto');

// VULNERABILITY: Hardcoded cryptographic secret
const ENCRYPTION_KEY = "globomantics-super-secret-key-12345";

// User model with insecure methods
class User {
  constructor(data) {
    this.id = data.id;
    this.username = data.username;
    this.email = data.email;
    this.password = data.password; // In a real app, would never store plaintext passwords
    this.role = data.role || 'user';
    this.createdAt = data.createdAt || new Date();
  }
  
  // VULNERABILITY: Insecure password hashing function
  static hashPassword(password) {
    // Should use bcrypt, argon2, or another secure hashing algorithm
    return crypto.createHash('md5').update(password).digest('hex');
  }
  
  // VULNERABILITY: Insecure token generation using Math.random()
  static generateAuthToken(userId) {
    const token = Math.random().toString(36).substring(2) + Math.random().toString(36).substring(2);
    return token;
  }
  
  // VULNERABILITY: Insecure encryption function
  static encryptSensitiveData(data) {
    // Using a weak cipher with a hardcoded key and IV
    const cipher = crypto.createCipheriv('aes-128-cbc', 
      ENCRYPTION_KEY.substring(0, 16), 
      '1234567890123456'); // Hardcoded IV
    
    let encrypted = cipher.update(data, 'utf8', 'hex');
    encrypted += cipher.final('hex');
    return encrypted;
  }
  
  // VULNERABILITY: Insecure decryption function
  static decryptSensitiveData(encryptedData) {
    // Using a weak cipher with a hardcoded key and IV
    const decipher = crypto.createDecipheriv('aes-128-cbc', 
      ENCRYPTION_KEY.substring(0, 16), 
      '1234567890123456'); // Hardcoded IV
    
    let decrypted = decipher.update(encryptedData, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    return decrypted;
  }
  
  // VULNERABILITY: Insecure serialization method (could lead to prototype pollution)
  toJSON() {
    // Should clone object or use a custom serializer to prevent prototype pollution
    return {
      id: this.id,
      username: this.username,
      email: this.email,
      role: this.role,
      createdAt: this.createdAt
    };
  }
}

module.exports = User; 