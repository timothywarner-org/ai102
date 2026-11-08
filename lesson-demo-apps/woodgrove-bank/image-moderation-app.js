// Woodgrove Bank – Lesson 5: Moderate Image Content
require('dotenv').config();
const express = require('express');
const bodyParser = require('body-parser');
const { exec } = require('child_process');
const os = require('os');
const path = require('path');
const axios = require('axios');
const crypto = require('crypto');
const multer = require('multer');
const fs = require('fs');
const { renderReport } = require('./reporting');
const chalk = require('chalk');

const app = express();
const PORT = process.env.PORT || 3002;

const upload = multer({ storage: multer.memoryStorage() });

// Max file size for Content Safety API (4MB)
const MAX_FILE_SIZE = 4 * 1024 * 1024;

// Function to kill processes on the app port (idempotent startup)
function cleanupPort() {
  return new Promise((resolve) => {
    console.log(`🔄 Checking for existing processes on port ${PORT}...`);
    const isWindows = os.platform() === 'win32';
    if (isWindows) {
      exec(`netstat -ano | findstr :${PORT}`, (error, stdout) => {
        if (error || !stdout) {
          console.log(`✅ No existing processes found on port ${PORT}`);
          return resolve();
        }
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
        setTimeout(resolve, 1000);
      });
    } else {
      exec(`lsof -i :${PORT} | grep LISTEN | awk '{print $2}'`, (error, stdout) => {
        if (error || !stdout) {
          console.log(`✅ No existing processes found on port ${PORT}`);
          return resolve();
        }
        const pids = stdout.trim().split('\n');
        if (pids.length === 0 || (pids.length === 1 && !pids[0])) {
          console.log('✅ No processes to kill');
          return resolve();
        }
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
        setTimeout(resolve, 1000);
      });
    }
  });
}

app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json());
app.use(express.static(path.join(__dirname, 'public')));

app.get('/', (req, res) => {
  res.send(`
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:700px;margin:2rem auto;padding:2rem;border-radius:12px;border:1px solid #e0e0e0;background:#f9f9f9;">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <h1 style="margin-bottom:0.2em;">Woodgrove Bank – Image Content Review Portal</h1>
          <p style="margin-top:0;font-size:1.1em;color:#1976d2;">Lesson 5: Moderate Image Content (AI-102)</p>
        </div>
        <div style="width:56px;height:56px;background:#1976d2;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:1.5em;">WB</div>
      </div>
      <p>For demo: Moderating <code>objects.jpg</code> from the project root every time. (Form is disabled until this works!)</p>
      <form method="POST" action="/" style="margin-bottom:1.5em;">
        <button type="submit" style="background:#1976d2;color:#fff;padding:0.7em 1.5em;border:none;border-radius:6px;font-size:1em;cursor:pointer;">Moderate objects.jpg</button>
      </form>
      <p style="margin-top:2rem;font-size:0.9em;color:#888;">Powered by Azure AI Content Safety & Vision APIs</p>
    </div>
  `);
});

// Helper: Generate a correlation ID for each moderation request
function generateCorrelationId() {
  return crypto.randomBytes(8).toString('hex');
}

// Helper: Color for severity (0-3)
function severityColor(severity) {
  switch (severity) {
    case 0: return '#4caf50'; // Green
    case 1: return '#ffeb3b'; // Yellow
    case 2: return '#ff9800'; // Orange
    case 3: return '#f44336'; // Red
    default: return '#bdbdbd'; // Grey
  }
}

// Helper: Validate base64 string (simple check)
function isValidBase64(str) {
  // Should only contain base64 chars and be non-empty
  return typeof str === 'string' && str.length > 0 && /^[A-Za-z0-9+/=]+$/.test(str);
}

app.post('/', async (req, res) => {
  const correlationId = generateCorrelationId();
  let imgBuffer, imagePreview;
  try {
    const imgPath = path.join(__dirname, 'objects.jpg');
    if (!fs.existsSync(imgPath)) {
      return res.send('<div style="color:red;">❌ objects.jpg not found in project root.</div>');
    }
    imgBuffer = fs.readFileSync(imgPath);
    if (!imgBuffer || imgBuffer.length === 0) {
      return res.send('<div style="color:red;">❌ objects.jpg is empty or could not be read.</div>');
    }
    imagePreview = `data:image/jpeg;base64,${imgBuffer.toString('base64')}`;
    // Log file size and first 100 chars of buffer as base64
    const base64Image = imgBuffer.toString('base64');
    console.log(`[${correlationId}] objects.jpg size: ${imgBuffer.length} bytes`);
    console.log(`[${correlationId}] base64 (first 100 chars): ${base64Image.slice(0, 100)}...`);
  } catch (e) {
    return res.send('<div style="color:red;">❌ Could not read objects.jpg from project root.<br>' + e.message + '</div>');
  }

  // Only call Vision API (analyze endpoint) with tags, description, adult
  const visionUrl = `${process.env.VISION_ENDPOINT}/vision/v3.2/analyze?visualFeatures=Tags,Description,Adult`;
  console.log(`[${correlationId}] Vision payload: [raw image buffer, ${imgBuffer.length} bytes]`);

  try {
    const visionResp = await axios.post(visionUrl, imgBuffer, {
      headers: {
        'Ocp-Apim-Subscription-Key': process.env.VISION_KEY,
        'Content-Type': 'application/octet-stream',
        'x-ms-correlation-id': correlationId
      }
    });

    // Extract Vision results
    const v = visionResp.data;
    const adult = v.adult || {};
    // Pretty console output with emoji and table
    function emojiBool(val, yes, no) { return val ? yes : no; }
    function colorScore(score) {
      if (score >= 0.85) return chalk.bgRed.white.bold(` ${score.toFixed(2)} `);
      if (score >= 0.5) return chalk.bgYellow.black(` ${score.toFixed(2)} `);
      return chalk.bgGreen.black(` ${score.toFixed(2)} `);
    }
    console.log('\n' + chalk.bold.bgBlue.white(' 🖼️  VISION ANALYSIS REPORT '.padEnd(50)));
    // Description
    if (v.description && v.description.captions && v.description.captions.length > 0) {
      const cap = v.description.captions[0];
      console.log(`\n${chalk.bold('📝 Description:')} ${chalk.italic(cap.text)} ${chalk.gray(`(Confidence: ${(cap.confidence*100).toFixed(1)}%)`)}`);
    }
    // Tags table
    if (v.tags && v.tags.length > 0) {
      console.log(`\n${chalk.bold('🏷️ Tags:')}`);
      const tagRows = v.tags.slice(0, 8).map(t => [t.name, `${(t.confidence*100).toFixed(1)}%`]);
      const tagTable = [
        [chalk.underline('Tag'), chalk.underline('Confidence')],
        ...tagRows
      ];
      tagTable.forEach(row => console.log(row.map(cell => cell.padEnd(16)).join(' ')));
      if (v.tags.length > 8) console.log(chalk.gray(`...and ${v.tags.length - 8} more`));
    }
    // Adult/racy content
    if (v.adult) {
      console.log(`\n${chalk.bold('🔞 Content Moderation:')}`);
      console.log(`  ${emojiBool(v.adult.isAdultContent, '🚫', '✅')} Adult: ${v.adult.isAdultContent ? chalk.red.bold('Yes') : chalk.green('No')}  (Score: ${colorScore(v.adult.adultScore)})`);
      console.log(`  ${emojiBool(v.adult.isRacyContent, '⚠️', '✅')} Racy:  ${v.adult.isRacyContent ? chalk.yellow.bold('Yes') : chalk.green('No')}  (Score: ${colorScore(v.adult.racyScore)})`);
      if (typeof v.adult.goreScore === 'number') {
        console.log(`  ${emojiBool(v.adult.isGoryContent, '💉', '✅')} Gore:  ${v.adult.isGoryContent ? chalk.red.bold('Yes') : chalk.green('No')}  (Score: ${colorScore(v.adult.goreScore)})`);
      }
    }
    console.log(chalk.bold.bgBlue.white('='.repeat(50)) + '\n');

    // Web response: friendly thank you page
    res.send(`
      <div style="font-family:Segoe UI,Arial,sans-serif;max-width:700px;margin:2rem auto;padding:2rem;border-radius:12px;border:1px solid #e0e0e0;background:#f9f9f9;">
        <h2 style="color:#1976d2;">Thank you, message sent!</h2>
        <p>Your image was analyzed by Azure AI Vision. Check the server console for results.</p>
        <form method="GET" action="/">
          <button type="submit" style="background:#1976d2;color:#fff;padding:0.7em 1.5em;border:none;border-radius:6px;font-size:1em;cursor:pointer;">Restart</button>
        </form>
      </div>
    `);
  } catch (err) {
    console.error(`[${correlationId}] ❌ Vision analysis failed:`, err.response?.data || err.message);
    res.send(`
      <div style="font-family:Segoe UI,Arial,sans-serif;max-width:700px;margin:2rem auto;padding:2rem;border-radius:12px;border:1px solid #e0e0e0;background:#f9f9f9;">
        <h2 style="color:#ff0000;">❌ Vision Analysis Failed</h2>
        <p>${err.response?.data?.error?.message || err.message}</p>
        <a href="/" style="background:#1976d2;color:#fff;padding:0.7em 1.5em;border:none;border-radius:6px;font-size:1em;cursor:pointer;">Try again</a>
      </div>
    `);
  }
});

cleanupPort().then(() => {
  app.listen(PORT, () => {
    console.log(`\n🏦 Woodgrove Bank Image Moderation Portal running at http://localhost:${PORT}\n`);
  });
}); 