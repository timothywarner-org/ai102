// reporting.js - Woodgrove Bank reusable reporting module

const propertyMaps = {
  'vision': [
    {
      name: 'Tag Name',
      path: 'tags[0].name',
      description: 'What the model detected in the image.',
      range: 'String (object/concept)',
      doc: 'https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview'
    },
    {
      name: 'Tag Confidence',
      path: 'tags[0].confidence',
      description: 'Model confidence in the tag.',
      range: '0.0–1.0 (higher = more confident)',
      doc: 'https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview'
    },
    {
      name: 'Object Name',
      path: 'objects[0].object',
      description: 'Detected object in the image.',
      range: 'String',
      doc: 'https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-object-detection'
    },
    {
      name: 'Object Confidence',
      path: 'objects[0].confidence',
      description: 'Model confidence in the object.',
      range: '0.0–1.0',
      doc: 'https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-object-detection'
    },
    {
      name: 'Adult Score',
      path: 'adult.adultScore',
      description: 'Probability of adult content.',
      range: '0.0–1.0 (0=safe, 1=unsafe)',
      doc: 'https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/how-to/vision-api-image-moderation'
    },
    {
      name: 'Is Adult Content',
      path: 'adult.isAdultContent',
      description: 'Adult content detected?',
      range: 'true/false',
      doc: 'https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/how-to/vision-api-image-moderation'
    },
    {
      name: 'OCR Text',
      path: 'ocrText',
      description: 'Extracted text from the image.',
      range: 'String',
      doc: 'https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/how-to/ocr'
    }
  ],
  'document-intelligence': [
    {
      name: 'Key-Value Pairs',
      path: 'keyValuePairs',
      description: 'Extracted fields and values from the document.',
      range: 'Array of {key, value}',
      doc: 'https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-key-value-pairs'
    },
    {
      name: 'Tables',
      path: 'tables',
      description: 'Extracted tables from the document.',
      range: 'Array of tables (rows, columns, cells)',
      doc: 'https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-tables'
    },
    {
      name: 'Document Type',
      path: 'docType',
      description: 'Type of document detected (e.g., invoice, receipt).',
      range: 'String',
      doc: 'https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-document-types'
    },
    {
      name: 'Confidence',
      path: 'confidence',
      description: 'Model confidence in extraction.',
      range: '0.0–1.0',
      doc: 'https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-confidence-scores'
    }
  ]
};

// Helper to get nested property by path (e.g., 'tags[0].name')
function getProp(obj, path) {
  try {
    return path.split('.').reduce((acc, part) => {
      if (!acc) return undefined;
      const match = part.match(/(\w+)\[(\d+)\]/);
      if (match) {
        return acc[match[1]] && acc[match[1]][parseInt(match[2], 10)];
      }
      return acc[part];
    }, obj);
  } catch {
    return undefined;
  }
}

function renderReport({ result, type, lesson }) {
  const props = propertyMaps[type] || [];
  // Special handling for OCR text in Vision
  let ocrText = '';
  if (type === 'vision' && result.ocr) {
    ocrText = (result.ocr.regions || [])
      .map(region => region.lines.map(line => line.words.map(w => w.text).join(' ')).join(' ')).join('\n');
  }
  // Build table rows
  const rows = props.map(p => {
    let value = getProp(result, p.path);
    if (p.path === 'ocrText') value = ocrText;
    // Format confidence values as percentage with two decimals
    if ((p.name === 'Tag Confidence' || p.name === 'Object Confidence') && typeof value === 'number') {
      value = (value * 100).toFixed(2) + '%';
    }
    if (Array.isArray(value)) value = JSON.stringify(value, null, 2);
    if (typeof value === 'object' && value !== null) value = JSON.stringify(value);
    if (value === undefined) value = '<span style="color:#888;">—</span>';
    return `<tr>
      <td style="font-weight:bold;">${p.name}</td>
      <td>${value}</td>
      <td>${p.description}</td>
      <td>${p.range}</td>
      <td><a href="${p.doc}" target="_blank">Docs</a></td>
    </tr>`;
  }).join('');

  // Woodgrove-branded, accessible, colorblind-friendly HTML
  return `
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:900px;margin:2rem auto;padding:2rem;border-radius:12px;border:1px solid #e0e0e0;background:#f9f9f9;">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <div>
          <h2 style="margin-bottom:0.2em;">Woodgrove Bank – Lesson ${lesson}: ${type === 'vision' ? 'Image Analysis' : 'Document Analysis'} Reporting</h2>
          <p style="margin-top:0;font-size:1.1em;color:#1976d2;">Most Common Properties (AI-102 Exam & Real-World)</p>
        </div>
        <div style="width:56px;height:56px;background:#1976d2;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:1.5em;">WB</div>
      </div>
      <p style="margin-top:1em;">This table summarizes the most important properties returned by Azure AI ${type === 'vision' ? 'Vision' : 'Document Intelligence'}. These are the fields you'll see most often on the AI-102 exam and in real-world projects.</p>
      <table style="width:100%;border-collapse:collapse;margin-top:1em;">
        <tr style="background:#f1f1f1;">
          <th>Property</th>
          <th>Value</th>
          <th>Description</th>
          <th>Typical Range</th>
          <th>Docs</th>
        </tr>
        ${rows}
      </table>
      <p style="margin-top:2em;font-size:0.95em;color:#888;">Learn more: <a href="${type === 'vision' ? 'https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview' : 'https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/overview'}" target="_blank">Azure AI ${type === 'vision' ? 'Vision' : 'Document Intelligence'} Docs</a></p>
    </div>
  `;
}

module.exports = { renderReport }; 