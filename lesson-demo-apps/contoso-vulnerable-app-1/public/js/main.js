document.addEventListener('DOMContentLoaded', () => {
  // Calculate form
  const calculateForm = document.getElementById('calculate-form');
  if (calculateForm) {
    calculateForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const formula = document.getElementById('formula').value;
      
      try {
        const response = await fetch(`/calculate?formula=${encodeURIComponent(formula)}`);
        const data = await response.json();
        
        document.getElementById('result').textContent = data.result !== undefined ? 
          data.result : data.error;
      } catch (error) {
        document.getElementById('result').textContent = 'Error: ' + error.message;
      }
    });
  }
  
  // Generate token button
  const generateTokenBtn = document.getElementById('generate-token-btn');
  if (generateTokenBtn) {
    generateTokenBtn.addEventListener('click', async () => {
      try {
        const response = await fetch('/generate-token', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          }
        });
        const data = await response.json();
        
        document.getElementById('token-result').textContent = data.token;
      } catch (error) {
        document.getElementById('token-result').textContent = 'Error: ' + error.message;
      }
    });
  }
  
  // Redirect form
  const redirectForm = document.getElementById('redirect-form');
  if (redirectForm) {
    redirectForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const url = document.getElementById('redirect-url').value;
      window.location.href = `/redirect?url=${encodeURIComponent(url)}`;
    });
  }
}); 