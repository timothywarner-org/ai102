// Woodgrove Bank – Lesson 6: Image Tagging & Object Detection Demo
require('dotenv').config();
const express = require('express');
const bodyParser = require('body-parser');
const path = require('path');
const axios = require('axios');
const crypto = require('crypto');
const fs = require('fs');
const { renderReport } = require('./reporting');
const chalk = require('chalk');
const multer = require('multer');
const { exec } = require('child_process');
const { execSync } = require('child_process');
const os = require('os');
const { CosmosClient } = require('@azure/cosmos');
const { BlobServiceClient } = require('@azure/storage-blob');

const app = express();
const PORT = process.env.PORT || 3003;

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 5 * 1024 * 1024 } }); // 5MB max

// Helper: Generate a correlation ID for each request
function generateCorrelationId() {
  return crypto.randomBytes(8).toString('hex');
}

// Helper: Color for confidence (0-1)
function confidenceColor(score) {
  if (score >= 0.85) return chalk.bgGreen.black(` ${score.toFixed(2)} `);
  if (score >= 0.5) return chalk.bgYellow.black(` ${score.toFixed(2)} `);
  return chalk.bgRed.white.bold(` ${score.toFixed(2)} `);
}

// Cross-platform console clear
function clearConsole() {
  try {
    if (process.platform === 'win32') {
      // Try Git Bash first
      if (process.env.SHELL && process.env.SHELL.includes('bash')) {
        execSync('clear', { stdio: 'inherit' });
      } else {
        execSync('cls', { stdio: 'inherit' });
      }
    } else {
      execSync('clear', { stdio: 'inherit' });
    }
  } catch {
    // Fallback: print newlines
    console.log('\n'.repeat(50));
  }
}

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

// Cosmos DB client setup (reads from .env)
const cosmosEndpoint = process.env.COSMOS_URI;
const cosmosKey = process.env.COSMOS_KEY;
const cosmosDb = process.env.COSMOS_DB;
const cosmosContainer = process.env.COSMOS_CONTAINER;
const cosmosPartitionKey = process.env.COSMOS_PARTITION_KEY;
let cosmosClient, cosmosDbRef, cosmosContainerRef;
if (cosmosEndpoint && cosmosKey && cosmosDb && cosmosContainer) {
  cosmosClient = new CosmosClient({ endpoint: cosmosEndpoint, key: cosmosKey });
  cosmosDbRef = cosmosClient.database(cosmosDb);
  cosmosContainerRef = cosmosDbRef.container(cosmosContainer);
}

app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json());
app.use(express.static(path.join(__dirname, 'public')));
// Serve branding assets for demo
app.use('/branding', express.static(path.join(__dirname, 'woodgrove-bank-demo-app/wwwroot/Company-branding')));

app.get('/', (req, res) => {
  res.send(`
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Woodgrove Bank – Image Tagging & Object Detection</title>
      <link rel="stylesheet" href="/branding/customcss.css">
      <link rel="icon" type="image/png" href="/branding/favicon.png">
      <!-- Microsoft Fonts: Segoe UI Variable, Segoe UI, fallback -->
      <link rel="stylesheet" href="https://static2.sharepointonline.com/files/fabric/assets/fonts/segoe-ui-variable/segoe-ui-variable.css">
      <!-- Prism.js for syntax highlighting -->
      <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-tomorrow.min.css">
      <style>
        body, button, input, select, textarea, h1, h2, h3, h4, h5, h6 {
          font-family: 'Segoe UI Variable', 'Segoe UI', 'Open Sans', 'Roboto', Arial, sans-serif;
        }
        .dropzone {
          border: 2px dashed #1976d2;
          border-radius: 12px;
          background: #f4f8fb;
          padding: 2em;
          text-align: center;
          color: #1976d2;
          font-size: 1.1em;
          margin-bottom: 1.5em;
          transition: background 0.2s, border-color 0.2s;
        }
        .dropzone.dragover {
          background: #e3f2fd;
          border-color: #0d47a1;
        }
        .dropzone input[type="file"] {
          display: none;
        }
      </style>
    </head>
    <body style="background:#f9f9f9;">
      <div class="ext-header" style="display:flex;align-items:center;justify-content:space-between;padding:1em 2em 1em 1em;border-radius:12px 12px 0 0;">
        <div style="display:flex;align-items:center;gap:1em;">
          <img src="/branding/headerlogo.png" alt="Woodgrove Bank Logo" class="ext-header-logo" style="height:48px;" />
          <span class="ext-title" style="font-size:1.6em;color:white;font-weight:bold;">Woodgrove Bank</span>
        </div>
        <div style="display:flex;align-items:center;gap:0.5em;">
          <img src="https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg" alt="Microsoft Logo" style="height:32px;" />
          <span style="color:white;font-size:1.1em;">Microsoft Azure AI</span>
        </div>
      </div>
      <div style="max-width:700px;margin:2rem auto;padding:2rem;border-radius:0 0 12px 12px;border:1px solid #e0e0e0;background:#fff;">
        <h1 style="margin-bottom:0.2em;">Image Tagging & Object Detection</h1>
        <p style="margin-top:0;font-size:1.1em;color:#1976d2;">Upload an image to analyze with Azure AI Vision (AI-102)</p>
        <form method="POST" action="/" enctype="multipart/form-data" id="uploadForm">
          <label for="imageFile" style="font-weight:bold;">Select an image (JPG, PNG, GIF, max 5MB):</label><br>
          <div class="dropzone" id="dropzone" tabindex="0" aria-label="Drag and drop an image file here or click to select">
            <span id="dropzone-text">Drag and drop an image here, or <b>click to select</b></span>
            <input type="file" name="imageFile" id="imageFile" accept="image/*" required />
          </div>
          <button type="submit" class="ext-button ext-primary" style="padding:0.7em 1.5em;font-size:1em;cursor:pointer;">Analyze Image</button>
        </form>
        <p style="margin-top:2rem;font-size:0.9em;color:#888;">Powered by <b>Microsoft Azure AI Vision</b></p>
      </div>
      <footer class="ext-footer" style="margin-top:2em;padding:1em 0;text-align:center;background:rgb(36,24,82);color:white;border-radius:0 0 12px 12px;">
        <span class="ext-footer-item">&copy; 2025 Woodgrove Bank | Powered by Microsoft Azure AI<br>
        Supporting Tim Warner's Microsoft Press Video Course AI-102, Lesson 6</span>
      </footer>
      <script>
        // Drag and drop logic
        const dropzone = document.getElementById('dropzone');
        const fileInput = document.getElementById('imageFile');
        dropzone.addEventListener('click', () => fileInput.click());
        dropzone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });
        dropzone.addEventListener('dragover', e => {
          e.preventDefault();
          dropzone.classList.add('dragover');
        });
        dropzone.addEventListener('dragleave', e => {
          e.preventDefault();
          dropzone.classList.remove('dragover');
        });
        dropzone.addEventListener('drop', e => {
          e.preventDefault();
          dropzone.classList.remove('dragover');
          if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            document.getElementById('dropzone-text').textContent = e.dataTransfer.files[0].name;
          }
        });
        fileInput.addEventListener('change', e => {
          if (fileInput.files && fileInput.files.length > 0) {
            document.getElementById('dropzone-text').textContent = fileInput.files[0].name;
          }
        });
      </script>
    </body>
    </html>
  `);
});

app.post('/', upload.single('imageFile'), async (req, res) => {
  const correlationId = generateCorrelationId();
  let imgBuffer, imagePreview;
  if (!req.file) {
    return res.send('<div style="color:red;">❌ No image uploaded. Please select an image file.</div>');
  }
  imgBuffer = req.file.buffer;
  imagePreview = `data:${req.file.mimetype};base64,${imgBuffer.toString('base64')}`;
  console.log(`[${correlationId}] Uploaded image: ${req.file.originalname} (${imgBuffer.length} bytes)`);
  // Call Vision API (analyze endpoint) with objects, tags, description
  const visionUrl = `${process.env.VISION_ENDPOINT}/vision/v3.2/analyze?visualFeatures=Objects,Tags,Description`;
  console.log(`[${correlationId}] Vision payload: [uploaded image buffer, ${imgBuffer.length} bytes]`);
  try {
    const visionResp = await axios.post(visionUrl, imgBuffer, {
      headers: {
        'Ocp-Apim-Subscription-Key': process.env.VISION_KEY,
        'Content-Type': req.file.mimetype,
        'x-ms-correlation-id': correlationId
      }
    });
    // Extract Vision results
    const v = visionResp.data;
    // === Enhanced Metadata Extraction for Filename and Cosmos DB ===
    function sanitize(str) {
      return (str || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    }
    const tagsArr = (v.tags || []).slice(0, 2).map(t => sanitize(t.name));
    const descriptionText = v.description && v.description.captions && v.description.captions[0]
      ? sanitize(v.description.captions[0].text)
      : '';
    const timestamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 15);
    const ext = req.file.originalname.split('.').pop();
    const parts = [...tagsArr, descriptionText, timestamp].filter(Boolean);
    const blobName = `${parts.join('-')}.${ext}`;
    // === Blob Storage Upload ===
    let blobUrl = null;
    try {
      const blobServiceClient = BlobServiceClient.fromConnectionString(process.env.AZURE_STORAGE_CONNECTION_STRING);
      const containerName = process.env.AZURE_STORAGE_BLOB_CONTAINER || 'uploads';
      const containerClient = blobServiceClient.getContainerClient(containerName);
      const blockBlobClient = containerClient.getBlockBlobClient(blobName);
      await blockBlobClient.uploadData(imgBuffer, {
        blobHTTPHeaders: { blobContentType: req.file.mimetype }
      });
      blobUrl = blockBlobClient.url;
      console.log(`[${correlationId}] ✅ Uploaded to Blob Storage: ${blobUrl}`);
    } catch (blobErr) {
      console.error(`[${correlationId}] ❌ Blob upload failed:`, blobErr.message || blobErr);
    }
    // === Cosmos DB Storage with Searchable Metadata ===
    if (cosmosContainerRef) {
      // Build a maximally searchable document
      const cosmosDoc = {
        id: `${blobName}-${Date.now()}`,
        filename: blobName,
        blobUrl,
        mimetype: req.file.mimetype,
        size: imgBuffer.length,
        uploadedBy: req.ip || 'unknown',
        uploadDate: new Date().toISOString(),
        correlationId,
        tags: v.tags || [],
        description: v.description && v.description.captions && v.description.captions[0]
          ? {
              text: v.description.captions[0].text,
              confidence: v.description.captions[0].confidence
            }
          : {},
        objects: v.objects || [],
        visionResult: v // Full Vision API result for reference
      };
      // Log the document structure for teaching/observability
      console.log(`[${correlationId}] Cosmos DB document:`, JSON.stringify(cosmosDoc, null, 2));
      try {
        await cosmosContainerRef.items.upsert(cosmosDoc);
        console.log(`[${correlationId}] ✅ Wrote analysis result to Cosmos DB: ${cosmosDoc.id}`);
      } catch (cosmosErr) {
        console.error(`[${correlationId}] ❌ Failed to write to Cosmos DB:`, cosmosErr.message || cosmosErr);
      }
    } else {
      console.warn(`[${correlationId}] Cosmos DB not configured. Skipping DB write.`);
    }
    // Pretty console output for teaching
    console.log('\n' + chalk.bold.bgBlue.white(' 🏷️  TAGS '.padEnd(30)));
    if (v.tags && v.tags.length > 0) {
      v.tags.forEach(tag => {
        console.log(`  ${chalk.bold(tag.name.padEnd(16))} Confidence: ${confidenceColor(tag.confidence)}`);
      });
    }
    console.log(chalk.bold.bgBlue.white(' 📦 OBJECTS '.padEnd(30)));
    if (v.objects && v.objects.length > 0) {
      v.objects.forEach(obj => {
        console.log(`  ${chalk.bold(obj.object.padEnd(16))} Confidence: ${confidenceColor(obj.confidence)}  Box: [${obj.rectangle.x},${obj.rectangle.y},${obj.rectangle.w},${obj.rectangle.h}]`);
      });
    }
    if (v.description && v.description.captions && v.description.captions.length > 0) {
      const cap = v.description.captions[0];
      console.log(`\n${chalk.bold('📝 Description:')} ${chalk.italic(cap.text)} ${chalk.gray(`(Confidence: ${(cap.confidence*100).toFixed(1)}%)`)}`);
    }
    // Microsoft-style banner
    console.log(chalk.bgWhite.blue.bold('\n==============================='));
    console.log(chalk.bgWhite.blue.bold(' Powered by Microsoft Azure AI '));
    console.log(chalk.bgWhite.blue.bold('===============================\n'));
    // Tim Warner course support banner
    console.log(chalk.bgCyan.black.bold(' Supporting Tim Warner\'s Microsoft Press Video Course: AI-102, Lesson 6: Analyze Images with Pre-Built Models '));
    // Web response: show preview, tags, objects, and summary table
    res.send(`
      <!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Woodgrove Bank – Image Tagging & Object Detection</title>
        <link rel="stylesheet" href="/branding/customcss.css">
        <link rel="icon" type="image/png" href="/branding/favicon.png">
        <!-- Microsoft Fonts: Segoe UI Variable, Segoe UI, fallback -->
        <link rel="stylesheet" href="https://static2.sharepointonline.com/files/fabric/assets/fonts/segoe-ui-variable/segoe-ui-variable.css">
        <!-- Prism.js for syntax highlighting -->
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-tomorrow.min.css">
        <style>
          body, button, input, select, textarea, h1, h2, h3, h4, h5, h6 {
            font-family: 'Segoe UI Variable', 'Segoe UI', 'Open Sans', 'Roboto', Arial, sans-serif;
          }
        </style>
      </head>
      <body style="background:#f9f9f9;">
        <div class="ext-header" style="display:flex;align-items:center;justify-content:space-between;padding:1em 2em 1em 1em;border-radius:12px 12px 0 0;">
          <div style="display:flex;align-items:center;gap:1em;">
            <img src="/branding/headerlogo.png" alt="Woodgrove Bank Logo" class="ext-header-logo" style="height:48px;" />
            <span class="ext-title" style="font-size:1.6em;color:white;font-weight:bold;">Woodgrove Bank</span>
          </div>
          <div style="display:flex;align-items:center;gap:0.5em;">
            <img src="https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg" alt="Microsoft Logo" style="height:32px;" />
            <span style="color:white;font-size:1.1em;">Microsoft Azure AI</span>
          </div>
        </div>
        <div style="max-width:900px;margin:2rem auto;padding:2rem;border-radius:0 0 12px 12px;border:1px solid #e0e0e0;background:#fff;">
          <h2 style="margin-bottom:0.2em;">Image Tagging & Object Detection</h2>
          <p style="margin-top:0;font-size:1.1em;color:#1976d2;">Results for: <b>${req.file.originalname}</b></p>
          <img src="${imagePreview}" alt="uploaded preview" style="max-width:100%;margin:1em 0;border-radius:8px;border:1px solid #ccc;" />
          <h3>Tags</h3>
          <ul>
            ${(v.tags || []).map(tag => `<li><b>${tag.name}</b> <span style=\"color:#888;\">(${(tag.confidence*100).toFixed(1)}%)</span></li>`).join('') || '<li>No tags detected.</li>'}
          </ul>
          <h3>Objects</h3>
          <ul>
            ${(v.objects || []).map(obj => `<li><b>${obj.object}</b> <span style=\"color:#888;\">(${(obj.confidence*100).toFixed(1)}%)</span> Box: [${obj.rectangle.x},${obj.rectangle.y},${obj.rectangle.w},${obj.rectangle.h}]</li>`).join('') || '<li>No objects detected.</li>'}
          </ul>
          <h3>Summary Table</h3>
          ${renderReport({ result: v, type: 'vision', lesson: 6 })}
          <details style="margin-top:2em;">
            <summary style="font-weight:bold;cursor:pointer;font-size:1.1em;color:#1976d2;">Show Raw JSON</summary>
            <div style="margin:1em 0;">
              <button id="copyJsonBtn" type="button" style="background:#f3f3f3;color:#1976d2;border:1px solid #1976d2;border-radius:6px;padding:0.4em 1em;font-size:0.95em;cursor:pointer;margin-bottom:0.5em;">Copy to Clipboard</button><br>
              <pre id="jsonBlock" class="language-json" style="background:#222;color:#fff;padding:1em;border-radius:8px;overflow-x:auto;font-size:0.95em;line-height:1.4;">${JSON.stringify(v, null, 2)}</pre>
            </div>
          </details>
          <div style="margin-top:2em;display:flex;align-items:center;gap:1em;">
            <a href="https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/" target="_blank" style="color:#1976d2;font-weight:bold;">Learn more about Azure AI Vision</a>
            <a href="https://www.microsoft.com/en-us/trust-center" target="_blank" title="Microsoft Trust Center" style="display:inline-flex;align-items:center;gap:0.5em;vertical-align:middle;">
              <img src="https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg" alt="Microsoft Logo" style="height:32px;vertical-align:middle;" />
              <span style="font-size:1em;color:#1976d2;">Trust Center</span>
            </a>
          </div>
          <form method="GET" action="/">
            <button type="submit" class="ext-button ext-secondary" style="padding:0.7em 1.5em;font-size:1em;cursor:pointer;margin-top:2em;">Analyze Another Image</button>
          </form>
        </div>
        <footer class="ext-footer" style="margin-top:2em;padding:1em 0;text-align:center;background:rgb(36,24,82);color:white;border-radius:0 0 12px 12px;">
          <span class="ext-footer-item">&copy; 2025 Woodgrove Bank | Powered by Microsoft Azure AI<br>
          Supporting Tim Warner's Microsoft Press Video Course AI-102, Lesson 6</span>
        </footer>
        <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-json.min.js"></script>
        <script>
          // Drag and drop logic
          const dropzone = document.getElementById('dropzone');
          const fileInput = document.getElementById('imageFile');
          dropzone.addEventListener('click', () => fileInput.click());
          dropzone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });
          dropzone.addEventListener('dragover', e => {
            e.preventDefault();
            dropzone.classList.add('dragover');
          });
          dropzone.addEventListener('dragleave', e => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
          });
          dropzone.addEventListener('drop', e => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
              fileInput.files = e.dataTransfer.files;
              document.getElementById('dropzone-text').textContent = e.dataTransfer.files[0].name;
            }
          });
          fileInput.addEventListener('change', e => {
            if (fileInput.files && fileInput.files.length > 0) {
              document.getElementById('dropzone-text').textContent = fileInput.files[0].name;
            }
          });
          // Copy JSON logic
          const copyBtn = document.getElementById('copyJsonBtn');
          if (copyBtn) {
            copyBtn.addEventListener('click', () => {
              const jsonBlock = document.getElementById('jsonBlock');
              if (navigator.clipboard) {
                navigator.clipboard.writeText(jsonBlock.textContent).then(() => {
                  copyBtn.textContent = 'Copied!';
                  setTimeout(() => { copyBtn.textContent = 'Copy to Clipboard'; }, 1200);
                });
              }
            });
          }
        </script>
      </body>
      </html>
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

clearConsole();
cleanupPort().then(() => {
  // ASCII, colorblind-friendly launch banner
  const url = `http://localhost:${PORT}`;
  const line = '='.repeat(60);
  const banner = [
    '',
    line,
    '  Woodgrove Bank Image Tagging & Object Detection',
    '',
    `  App running at: ${chalk.bold.underline.cyan(url)}`,
    '',
    `  ${chalk.green('Ready for uploads! Drag and drop or click to select an image.')}`,
    '',
    '  (Ctrl+C to stop)',
    line,
    ''
  ].join('\n');
  console.log(banner);
  app.listen(PORT, () => {});
}); 