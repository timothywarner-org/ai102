/**
 * Globomantics Express Test App - Frontend JavaScript
 * Contains intentional security vulnerabilities
 */

// Main application code
document.addEventListener('DOMContentLoaded', function() {
  console.log('Globomantics application initialized');
  
  // Initialize UI components
  initializeUI();
  
  // Set up event handlers
  setupEventHandlers();
});

// VULNERABILITY: Insecure storage of sensitive information
function saveUserCredentials() {
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  
  if (username && password) {
    // VULNERABILITY: Storing passwords in localStorage
    localStorage.setItem('savedUsername', username);
    localStorage.setItem('savedPassword', password); // Should NEVER store passwords in localStorage
    
    console.log('Credentials saved');
  }
}

// VULNERABILITY: Unsafe use of innerHTML leading to XSS
function displaySearchResults(results) {
  const resultsContainer = document.getElementById('searchResults');
  
  if (results && results.length > 0) {
    let html = '<h2>Search Results</h2><ul>';
    
    results.forEach(result => {
      // VULNERABILITY: Direct use of innerHTML without sanitization
      html += `<li><strong>${result.title}</strong>: ${result.description}</li>`;
    });
    
    html += '</ul>';
    resultsContainer.innerHTML = html; // XSS vulnerability
  } else {
    resultsContainer.innerHTML = '<p>No results found</p>';
  }
}

// VULNERABILITY: Evaluating dynamic code
function executeCustomCode(code) {
  if (code) {
    try {
      // VULNERABILITY: Using eval to execute user-provided code
      eval(code);
    } catch (error) {
      console.error('Error executing code:', error);
    }
  }
}

// VULNERABILITY: Using global variables 
window.authToken = null;

// VULNERABILITY: Insecure login function using global variables
function login(username, password) {
  fetch('/users/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ username, password })
  })
  .then(response => response.json())
  .then(data => {
    if (data.token) {
      // VULNERABILITY: Storing auth token in a global variable
      window.authToken = data.token;
      
      // Update UI
      document.getElementById('loginStatus').textContent = `Logged in as ${data.user.username}`;
    }
  })
  .catch(error => {
    console.error('Login error:', error);
  });
}

// VULNERABILITY: Including credentials in AJAX requests
function loadUserProfile(userId) {
  // VULNERABILITY: Including credentials in request and not checking authorization
  fetch(`/api/users/${userId}/profile`, {
    credentials: 'include' // Should check if current user is authorized
  })
  .then(response => response.json())
  .then(data => {
    displayUserProfile(data);
  })
  .catch(error => {
    console.error('Error loading profile:', error);
  });
}

// UI initialization 
function initializeUI() {
  // Check for saved credentials
  const savedUsername = localStorage.getItem('savedUsername');
  if (savedUsername) {
    const usernameField = document.getElementById('username');
    if (usernameField) {
      usernameField.value = savedUsername;
    }
    
    // VULNERABILITY: Auto-filling password from storage
    const savedPassword = localStorage.getItem('savedPassword');
    if (savedPassword) {
      const passwordField = document.getElementById('password');
      if (passwordField) {
        passwordField.value = savedPassword;
      }
    }
  }
}

// Set up event handlers
function setupEventHandlers() {
  // Login form submission
  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', function(event) {
      event.preventDefault();
      
      const username = document.getElementById('username').value;
      const password = document.getElementById('password').value;
      
      if (document.getElementById('rememberMe').checked) {
        saveUserCredentials();
      }
      
      login(username, password);
    });
  }
  
  // Execute custom code button
  const execButton = document.getElementById('executeCode');
  if (execButton) {
    execButton.addEventListener('click', function() {
      const codeInput = document.getElementById('customCode');
      executeCustomCode(codeInput.value);
    });
  }
}

// VULNERABILITY: Exposed sensitive function
function calculateHash(input) {
  // Simple hash function for demonstration
  let hash = 0;
  for (let i = 0; i < input.length; i++) {
    const char = input.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return hash;
} 