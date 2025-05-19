const express = require('express');
const fetch = require('node-fetch');
const bodyParser = require('body-parser');
const { exec } = require('child_process');
const os = require('os');

const app = express();
const PORT = 3001;

// Logic App URL from your deployed workflow trigger
// TODO: Replace with your actual Logic App HTTP trigger URL from Azure
const LOGIC_APP_URL = 'https://twai102logic1.azurewebsites.net:443/api/workflow1/triggers/When_a_HTTP_request_is_received/invoke?api-version=2022-05-01&sp=%2Ftriggers%2FWhen_a_HTTP_request_is_received%2Frun&sv=1.0&sig=wNwRlP_8tM0LDoTFJMUjfZxk91Vht9jlzvLbNa3TsVk';

// Function to kill processes on specific ports (3000 and 3001)
function cleanupPorts() {
  return new Promise((resolve) => {
    console.log('🔄 Checking for existing processes on ports 3000 and 3001...');
    
    // Different commands based on OS
    const isWindows = os.platform() === 'win32';
    
    if (isWindows) {
      // Windows command
      exec('netstat -ano | findstr :3000 :3001', (error, stdout) => {
        if (error || !stdout) {
          console.log('✅ No existing processes found on ports 3000/3001');
          return resolve();
        }
        
        // Extract PIDs
        const pidRegex = /LISTENING\s+(\d+)/g;
        const pids = new Set();
        let match;
        
        while ((match = pidRegex.exec(stdout)) !== null) {
          pids.add(match[1]);
        }
        
        if (pids.size === 0) {
          console.log('✅ No processes to kill');
          return resolve();
        }
        
        // Kill each PID
        pids.forEach(pid => {
          console.log(`🛑 Killing process ${pid}...`);
          exec(`taskkill /F /PID ${pid}`, (killError) => {
            if (killError) {
              console.log(`⚠️ Error killing process ${pid}: ${killError.message}`);
            } else {
              console.log(`✅ Successfully killed process ${pid}`);
            }
          });
        });
        
        // Give some time for processes to be killed
        setTimeout(resolve, 1000);
      });
    } else {
      // Linux/Mac command
      exec("lsof -i :3000,3001 | grep LISTEN | awk '{print $2}'", (error, stdout) => {
        if (error || !stdout) {
          console.log('✅ No existing processes found on ports 3000/3001');
          return resolve();
        }
        
        const pids = stdout.trim().split('\n');
        
        if (pids.length === 0 || (pids.length === 1 && !pids[0])) {
          console.log('✅ No processes to kill');
          return resolve();
        }
        
        // Kill each PID
        pids.forEach(pid => {
          console.log(`🛑 Killing process ${pid}...`);
          exec(`kill -9 ${pid}`, (killError) => {
            if (killError) {
              console.log(`⚠️ Error killing process ${pid}: ${killError.message}`);
            } else {
              console.log(`✅ Successfully killed process ${pid}`);
            }
          });
        });
        
        // Give some time for processes to be killed
        setTimeout(resolve, 1000);
      });
    }
  });
}

app.use(bodyParser.urlencoded({ extended: true }));

// Enhanced request logging middleware
app.use((req, res, next) => {
  const timestamp = new Date().toISOString();
  console.log(`\n📥 [${timestamp}] Incoming ${req.method} request to ${req.url}`);
  console.log(`🔍 Headers: ${JSON.stringify(req.headers)}`);
  
  if (req.method === 'POST') {
    console.log(`📦 Body: ${JSON.stringify(req.body)}`);
  }
  
  // Track response
  const originalSend = res.send;
  res.send = function(body) {
    console.log(`📤 [${new Date().toISOString()}] Response sent: ${body.substring(0, 100)}...`);
    return originalSend.call(this, body);
  };
  
  next();
});

app.get('/', (req, res) => {
  res.send(`
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:600px;margin:2rem auto;padding:2rem;border-radius:12px;border:1px solid #e0e0e0;background:#f9f9f9;">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <h1 style="margin-bottom:0.2em;">Woodgrove Bank – Content Review Portal</h1>
          <p style="margin-top:0;font-size:1.1em;color:#1976d2;">Lesson 4: Moderate Text Content (AI-102)</p>
        </div>
        <div style="width:56px;height:56px;background:#1976d2;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:1.5em;">WB</div>
      </div>
      <p>Please enter the internal message text that needs to be screened before release.</p>
      <form method="POST" action="/" style="margin-bottom:1.5em;">
        <label for="text" style="font-weight:bold;">Message Text:</label><br>
        <textarea name="text" id="text" rows="6" cols="60" required style="width:100%;padding:0.5em;border-radius:6px;border:1px solid #bdbdbd;font-size:1em;"></textarea><br><br>
        <button type="submit" style="background:#1976d2;color:#fff;padding:0.7em 1.5em;border:none;border-radius:6px;font-size:1em;cursor:pointer;">Submit for Review</button>
      </form>
      <p style="margin-top:2rem;font-size:0.9em;color:#888;">Powered by Azure AI Content Safety & Logic Apps</p>
    </div>
  `);
});

app.post('/', async (req, res) => {
  const { text } = req.body;
  console.log(`🔎 Processing content review request for text: "${text.substring(0, 50)}${text.length > 50 ? '...' : ''}"`);

  try {
    console.log(`🚀 Sending request to Logic App: ${LOGIC_APP_URL}`);
    console.time('logicAppRequest');
    
    const response = await fetch(LOGIC_APP_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    
    console.timeEnd('logicAppRequest');
    console.log(`📊 Logic App response status: ${response.status}`);

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`❌ Logic App error: ${errorText}`);
      return res.status(500).send(`
        <div style="font-family:Segoe UI,Arial,sans-serif;max-width:600px;margin:2rem auto;padding:2rem;border-radius:12px;border:1px solid #e0e0e0;background:#f9f9f9;">
          <h2 style="color:#ff0000;">❌ Submission Failed</h2>
          <p>Error code: ${response.status}</p>
          <p>Details: ${errorText}</p>
          <a href="/" style="background:#1976d2;color:#fff;padding:0.7em 1.5em;border:none;border-radius:6px;font-size:1em;cursor:pointer;">Try again</a>
        </div>
      `);
    }

    const responseBody = await response.text();
    console.log(`✅ Logic App success response: ${responseBody.substring(0, 200)}${responseBody.length > 200 ? '...' : ''}`);

    res.send(`
      <div style="font-family:Segoe UI,Arial,sans-serif;max-width:600px;margin:2rem auto;padding:2rem;border-radius:12px;border:1px solid #e0e0e0;background:#f9f9f9;">
        <h2 style="color:#008000;">✅ Message Submitted</h2>
        <p>Thank you. Your message has been forwarded to Azure AI Content Safety for moderation. You will receive a full report by email.</p>
        <a href="/" style="background:#1976d2;color:#fff;padding:0.7em 1.5em;border:none;border-radius:6px;font-size:1em;cursor:pointer;">Submit another</a>
      </div>
    `);
  } catch (err) {
    console.error(`💥 Request failed: ${err.stack || err.message}`);
    res.status(500).send(`
      <div style="font-family:Segoe UI,Arial,sans-serif;max-width:600px;margin:2rem auto;padding:2rem;border-radius:12px;border:1px solid #e0e0e0;background:#f9f9f9;">
        <h2 style="color:#ff0000;">❌ Internal Server Error</h2>
        <p>${err.message}</p>
        <a href="/" style="background:#1976d2;color:#fff;padding:0.7em 1.5em;border:none;border-radius:6px;font-size:1em;cursor:pointer;">Try again</a>
      </div>
    `);
  }
});

// Start server after cleaning up ports
cleanupPorts().then(() => {
  app.listen(PORT, () => {
    console.log(`
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  🏦 Woodgrove Bank Content Review Portal                       ║
║  🌐 Server running at http://localhost:${PORT}                     ║
║  🔒 Connected to Azure Logic App                               ║
║  📝 Log level: Verbose                                         ║
║                                                                ║
║  Ready to process content moderation requests                  ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
    `);
  });
});
