// Woodgrove Bank – Lesson 6: Woodgrove Asset Review (Batch Vision Demo)
require('dotenv').config();
const express = require('express');
const bodyParser = require('body-parser');
const multer = require('multer');
const axios = require('axios');
const crypto = require('crypto');
const path = require('path');
const os = require('os');
const { exec } = require('child_process');

const app = express();
const PORT = process.env.PORT || 3003;
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 5 * 1024 * 1024 } }); // 5MB max

// Demo mode sample Azure Blob Storage URLs
const DEMO_URLS = [
  'https://learnopenaicdn.blob.core.windows.net/vision-sample-images/landmark.jpg',
  'https://learnopenaicdn.blob.core.windows.net/vision-sample-images/receipt.jpg',
  'https://learnopenaicdn.blob.core.windows.net/vision-sample-images/woodgrove-logo.png'
];

// Idempotent startup: kill any process on PORT
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
app.use(express.static(path.join(__dirname, 'public')));

// Helper: Generate a correlation ID
function generateCorrelationId() {
  return crypto.randomBytes(8).toString('hex');
}

// Helper: Color for moderation severity
function severityColor(severity) {
  switch (severity) {
    case 0: return '#4caf50'; // Green
    case 1: return '#ffeb3b'; // Yellow
    case 2: return '#ff9800'; // Orange
    case 3: return '#f44336'; // Red
    default: return '#bdbdbd'; // Grey
  }
}

// Home page: input form
app.get('/', (req, res) => {
  res.send(`
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:2rem auto;padding:2rem;border-radius:12px;border:1px solid #e0e0e0;background:#f9f9f9;">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <h1 style="margin-bottom:0.2em;">Woodgrove Asset Review</h1>
          <p style="margin-top:0;font-size:1.1em;color:#1976d2;">Lesson 6: Batch Image Analysis (AI-102)</p>
        </div>
        <div style="width:56px;height:56px;background:#1976d2;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:1.5em;">WB</div>
      </div>
      <form method="POST" action="/analyze" enctype="multipart/form-data" style="margin-bottom:1.5em;">
        <label for="imageUrls" style="font-weight:bold;">Image URLs (one per line or comma-separated):</label><br>
        <textarea name="imageUrls" id="imageUrls" rows="3" cols="80" style="width:100%;padding:0.5em;border-radius:6px;border:1px solid #bdbdbd;font-size:1em;"></textarea><br>
        <button type="button" onclick="document.getElementById('imageUrls').value='${DEMO_URLS.join('\n')}'" style="margin:0.5em 0;background:#e0e0e0;color:#1976d2;padding:0.5em 1em;border:none;border-radius:6px;font-size:0.95em;cursor:pointer;">Demo Mode: Fill with Sample Azure Blob URLs</button><br>
        <label for="images" style="font-weight:bold;">Or upload images (multiple allowed, max 5MB each):</label><br>
        <input type="file" name="images" id="images" accept="image/*" multiple style="margin-bottom:1em;"><br>
        <button type="submit" style="background:#1976d2;color:#fff;padding:0.7em 1.5em;border:none;border-radius:6px;font-size:1em;cursor:pointer;">Analyze Images</button>
      </form>
      <p style="margin-top:2rem;font-size:0.9em;color:#888;">Powered by Azure AI Vision. Supports direct URLs (including Azure Blob Storage) and uploads. No files are stored.</p>
    </div>
  `);
});

// POST /analyze: handle batch analysis
app.post('/analyze', upload.array('images', 10), async (req, res) => {
  // Parse URLs
  let urls = [];
  if (req.body.imageUrls) {
    urls = req.body.imageUrls
      .split(/[\n,]+/)
      .map(u => u.trim())
      .filter(u => /^https?:\/\//i.test(u));
  }
  // Uploaded files
  const files = req.files || [];

  if (urls.length === 0 && files.length === 0) {
    return res.send('<p style="color:red;">Please provide at least one image URL or upload at least one image.</p><a href="/">Back</a>');
  }

  // Prepare all images for analysis
  const images = [
    ...urls.map(url => ({ type: 'url', value: url })),
    ...files.map(file => ({ type: 'upload', value: file }))
  ];

  // Analyze all images in parallel
  const results = await Promise.all(images.map(async (img) => {
    const correlationId = generateCorrelationId();
    let visionResp = {}, moderation = {}, error = null, thumbnail = null;
    try {
      // Prepare request
      let visionUrl = `${process.env.VISION_ENDPOINT}/vision/v3.2/analyze?visualFeatures=Tags,Objects,Adult,Description&details=Landmarks,Brands&language=en`;
      let ocrUrl = `${process.env.VISION_ENDPOINT}/vision/v3.2/ocr?language=unk&detectOrientation=true`;
      let headers = {
        'Ocp-Apim-Subscription-Key': process.env.VISION_KEY,
        'x-ms-correlation-id': correlationId
      };
      let data, ocrData;
      if (img.type === 'url') {
        data = { url: img.value };
        // Vision analysis
        visionResp = (await axios.post(visionUrl, data, { headers })).data;
        // OCR
        ocrData = (await axios.post(ocrUrl, data, { headers })).data;
        // Thumbnail
        thumbnail = img.value;
      } else {
        // Upload: send as binary
        headers['Content-Type'] = img.value.mimetype;
        visionResp = (await axios.post(visionUrl, img.value.buffer, { headers })).data;
        ocrData = (await axios.post(ocrUrl, img.value.buffer, { headers })).data;
        // Thumbnail: base64
        thumbnail = `data:${img.value.mimetype};base64,${img.value.buffer.toString('base64')}`;
      }
      // Moderation
      moderation = visionResp.adult || {};
      return {
        correlationId,
        thumbnail,
        tags: visionResp.tags || [],
        objects: visionResp.objects || [],
        ocr: ocrData || {},
        moderation,
        raw: { vision: visionResp, ocr: ocrData },
        error: null
      };
    } catch (err) {
      error = err.response?.data?.error?.message || err.message;
      return { correlationId, thumbnail, error };
    }
  }));

  // Render results
  res.send(`
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:1100px;margin:2rem auto;padding:2rem;border-radius:12px;border:1px solid #e0e0e0;background:#f9f9f9;">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <h1 style="margin-bottom:0.2em;">Woodgrove Asset Review – Results</h1>
          <p style="margin-top:0;font-size:1.1em;color:#1976d2;">Lesson 6: Batch Image Analysis (AI-102)</p>
        </div>
        <div style="width:56px;height:56px;background:#1976d2;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:1.5em;">WB</div>
      </div>
      <table style="width:100%;border-collapse:collapse;margin-top:2em;">
        <tr style="background:#f1f1f1;">
          <th>Thumbnail</th>
          <th>Tags</th>
          <th>Objects</th>
          <th>OCR Text</th>
          <th>Moderation</th>
          <th>Correlation ID</th>
          <th>Raw JSON</th>
        </tr>
        ${results.map(r => `
          <tr style="border-bottom:1px solid #e0e0e0;">
            <td><img src="${r.thumbnail || ''}" alt="thumb" style="max-width:120px;max-height:80px;border:1px solid #ccc;"></td>
            <td>${r.error ? '<span style="color:red;">Error</span>' : (r.tags.map(t => `<span style='background:#e3f2fd;color:#1976d2;padding:2px 6px;border-radius:4px;margin:1px;display:inline-block;'>${t.name} (${Math.round(t.confidence*100)}%)</span>`).join(' ') || '—')}</td>
            <td>${r.error ? '' : (r.objects.map(o => `<span style='background:#fff3e0;color:#e65100;padding:2px 6px;border-radius:4px;margin:1px;display:inline-block;'>${o.object} (${Math.round(o.confidence*100)}%)</span>`).join(' ') || '—')}</td>
            <td style="max-width:200px;overflow-x:auto;">${r.error ? '' : (r.ocr?.regions?.map(region => region.lines.map(line => line.words.map(w => w.text).join(' ')).join(' ')).join(' ') || '—')}</td>
            <td>${r.error ? '' : `<span style='background:${severityColor(r.moderation.adultScore > 0.5 ? 3 : r.moderation.racyScore > 0.5 ? 2 : 0)};color:#222;padding:2px 6px;border-radius:4px;'>Adult: ${r.moderation.isAdultContent ? 'Yes' : 'No'}<br>Racy: ${r.moderation.isRacyContent ? 'Yes' : 'No'}</span>`}</td>
            <td><code>${r.correlationId}</code></td>
            <td><details><summary>Show</summary><pre style="background:#222;color:#fff;padding:1em;overflow-x:auto;max-width:300px;max-height:200px;">${r.error ? r.error : JSON.stringify(r.raw, null, 2)}</pre></details></td>
          </tr>
        `).join('')}
      </table>
      <a href="/" style="display:inline-block;margin-top:2em;background:#1976d2;color:#fff;padding:0.7em 1.5em;border:none;border-radius:6px;font-size:1em;cursor:pointer;">Analyze More Images</a>
      <p style="margin-top:2rem;font-size:0.9em;color:#888;">Powered by Azure AI Vision. Supports direct URLs (including Azure Blob Storage) and uploads. No files are stored.</p>
    </div>
  `);
});

cleanupPort().then(() => {
  app.listen(PORT, () => {
    console.log(`\n🏦 Woodgrove Asset Review running at http://localhost:${PORT}\n`);
  });
}); 