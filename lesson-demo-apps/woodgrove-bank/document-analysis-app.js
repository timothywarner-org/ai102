// Woodgrove Bank – Lesson 7: Document Analysis (OCR + Form Recognizer)
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
const PORT = process.env.PORT || 3004;
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 10 * 1024 * 1024 } }); // 10MB max

// Demo mode sample public document URL (Azure sample invoice)
const DEMO_URL = 'https://raw.githubusercontent.com/Azure-Samples/azure-ai-services-samples/main/samples/sample-forms/invoice/sample-invoice.pdf';

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

// Home page: input form
app.get('/', (req, res) => {
  res.send(`
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:2rem auto;padding:2rem;border-radius:12px;border:1px solid #e0e0e0;background:#f9f9f9;">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <h1 style="margin-bottom:0.2em;">Woodgrove Document Analyzer</h1>
          <p style="margin-top:0;font-size:1.1em;color:#1976d2;">Lesson 7: Document Analysis (AI-102)</p>
        </div>
        <div style="width:56px;height:56px;background:#1976d2;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:1.5em;">WB</div>
      </div>
      <form method="POST" action="/analyze" enctype="multipart/form-data" style="margin-bottom:1.5em;">
        <label for="docUrl" style="font-weight:bold;">Document URL (PDF or image):</label><br>
        <input type="url" name="docUrl" id="docUrl" style="width:100%;padding:0.5em;border-radius:6px;border:1px solid #bdbdbd;font-size:1em;" placeholder="https://..."><br>
        <button type="button" onclick="document.getElementById('docUrl').value='${DEMO_URL}'" style="margin:0.5em 0;background:#e0e0e0;color:#1976d2;padding:0.5em 1em;border:none;border-radius:6px;font-size:0.95em;cursor:pointer;">Demo Mode: Fill with Sample Invoice URL</button><br>
        <label for="docFile" style="font-weight:bold;">Or upload a document (PDF/image, max 10MB):</label><br>
        <input type="file" name="docFile" id="docFile" accept="application/pdf,image/*" style="margin-bottom:1em;"><br>
        <button type="submit" style="background:#1976d2;color:#fff;padding:0.7em 1.5em;border:none;border-radius:6px;font-size:1em;cursor:pointer;">Analyze Document</button>
      </form>
      <p style="margin-top:2rem;font-size:0.9em;color:#888;">Powered by Azure Form Recognizer & Vision OCR. Supports direct URLs and uploads. No files are stored.</p>
    </div>
  `);
});

// POST /analyze: handle document analysis
app.post('/analyze', upload.single('docFile'), async (req, res) => {
  const correlationId = generateCorrelationId();
  let docUrl = req.body.docUrl && req.body.docUrl.trim();
  let file = req.file;
  let error = null, result = null, raw = null, tables = [], fields = [];

  if (!docUrl && !file) {
    return res.send('<p style="color:red;">Please provide a document URL or upload a document.</p><a href="/">Back</a>');
  }

  try {
    // Prepare Form Recognizer request
    const endpoint = process.env.FORM_RECOGNIZER_ENDPOINT;
    const key = process.env.FORM_RECOGNIZER_KEY;
    const model = 'prebuilt-document';
    const url = `${endpoint}/formrecognizer/documentModels/${model}:analyze?api-version=2023-07-31-preview`;
    let headers = {
      'Ocp-Apim-Subscription-Key': key,
      'x-ms-correlation-id': correlationId
    };
    let analyzeResp;
    if (docUrl) {
      headers['Content-Type'] = 'application/json';
      analyzeResp = await axios.post(url, { urlSource: docUrl }, { headers });
    } else {
      headers['Content-Type'] = file.mimetype;
      analyzeResp = await axios.post(url, file.buffer, { headers });
    }
    // Operation-Location for polling
    const opLocation = analyzeResp.headers['operation-location'];
    let pollResp, tries = 0;
    do {
      await new Promise(r => setTimeout(r, 1500));
      pollResp = await axios.get(opLocation, { headers: { 'Ocp-Apim-Subscription-Key': key } });
      tries++;
    } while (pollResp.data.status === 'running' && tries < 15);
    if (pollResp.data.status !== 'succeeded') throw new Error('Analysis did not complete in time.');
    raw = pollResp.data;
    // Extract fields
    const doc = raw.analyzeResult;
    if (doc.keyValuePairs) {
      fields = doc.keyValuePairs.map(kv => ({
        key: kv.key.content,
        value: kv.value?.content || ''
      }));
    }
    if (doc.tables) {
      tables = doc.tables.map(table => ({
        rows: table.cells.reduce((acc, cell) => {
          acc[cell.rowIndex] = acc[cell.rowIndex] || [];
          acc[cell.rowIndex][cell.columnIndex] = cell.content;
          return acc;
        }, [])
      }));
    }
    result = { fields, tables };
  } catch (err) {
    error = err.response?.data?.error?.message || err.message;
    // Fallback: try Vision OCR for images
    if (file && file.mimetype.startsWith('image/')) {
      try {
        const visionUrl = `${process.env.VISION_ENDPOINT}/vision/v3.2/ocr?language=unk&detectOrientation=true`;
        const headers = {
          'Ocp-Apim-Subscription-Key': process.env.VISION_KEY,
          'Content-Type': file.mimetype,
          'x-ms-correlation-id': correlationId
        };
        const ocrResp = await axios.post(visionUrl, file.buffer, { headers });
        raw = ocrResp.data;
        // Extract text
        let text = '';
        if (raw.regions) {
          text = raw.regions.map(region => region.lines.map(line => line.words.map(w => w.text).join(' ')).join(' ')).join('\n');
        }
        result = { fields: [{ key: 'Extracted Text', value: text }], tables: [] };
        error = null;
      } catch (ocrErr) {
        error += ' | OCR fallback failed: ' + (ocrErr.response?.data?.error?.message || ocrErr.message);
      }
    }
  }

  // Render results
  res.send(`
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:1000px;margin:2rem auto;padding:2rem;border-radius:12px;border:1px solid #e0e0e0;background:#f9f9f9;">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <h1 style="margin-bottom:0.2em;">Woodgrove Document Analyzer – Results</h1>
          <p style="margin-top:0;font-size:1.1em;color:#1976d2;">Lesson 7: Document Analysis (AI-102)</p>
        </div>
        <div style="width:56px;height:56px;background:#1976d2;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:1.5em;">WB</div>
      </div>
      <div style="margin-top:2em;">
        <h2>Extracted Fields</h2>
        ${error ? `<div style='color:red;font-weight:bold;'>${error}</div>` : ''}
        <table style="width:100%;border-collapse:collapse;">
          <tr style="background:#f1f1f1;"><th>Field</th><th>Value</th></tr>
          ${(result?.fields || []).map(f => `<tr><td style='font-weight:bold;'>${f.key}</td><td>${f.value}</td></tr>`).join('') || '<tr><td colspan=2>—</td></tr>'}
        </table>
      </div>
      ${result?.tables?.length ? `
      <div style="margin-top:2em;">
        <h2>Extracted Tables</h2>
        ${result.tables.map((t, i) => `
          <h3>Table ${i + 1}</h3>
          <table style="width:100%;border-collapse:collapse;">
            ${t.rows.map(row => `<tr>${row.map(cell => `<td style='border:1px solid #ccc;padding:2px 6px;'>${cell || ''}</td>`).join('')}</tr>`).join('')}
          </table>
        `).join('')}
      </div>
      ` : ''}
      <div style="margin-top:2em;">
        <details><summary>Show Raw JSON (for advanced learners)</summary>
          <pre style="background:#222;color:#fff;padding:1em;overflow-x:auto;max-width:900px;max-height:300px;">${raw ? JSON.stringify(raw, null, 2) : '—'}</pre>
        </details>
      </div>
      <div style="margin-top:2em;">
        <b>Correlation ID:</b> <code>${correlationId}</code>
      </div>
      <a href="/" style="display:inline-block;margin-top:2em;background:#1976d2;color:#fff;padding:0.7em 1.5em;border:none;border-radius:6px;font-size:1em;cursor:pointer;">Analyze Another Document</a>
      <p style="margin-top:2rem;font-size:0.9em;color:#888;">Powered by Azure Form Recognizer & Vision OCR. Supports direct URLs and uploads. No files are stored.</p>
    </div>
  `);
});

cleanupPort().then(() => {
  app.listen(PORT, () => {
    console.log(`\n🏦 Woodgrove Document Analyzer running at http://localhost:${PORT}\n`);
  });
}); 