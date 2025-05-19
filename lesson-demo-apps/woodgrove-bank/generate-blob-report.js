// generate-blob-report.js
// Generates a simple HTML report of all blob URIs in your Azure 'demos' container

const { BlobServiceClient } = require('@azure/storage-blob');
const fs = require('fs');
require('dotenv').config();

const account = process.env.AZURE_STORAGE_ACCOUNT || 'techtrainertimstorage';
const containerName = process.env.AZURE_STORAGE_CONTAINER || 'demos';

const connectionString = 'DefaultEndpointsProtocol=https;AccountName=techtrainertimstorage;AccountKey=0dPG1eOlIj7cl1H8wJa8v3JR7kFgxBaRXX26xyu///LBDrCZ8uRN/pU9JA9w8z5GeLAhoHnwzPnM+AStdeaMCQ==;EndpointSuffix=core.windows.net';

const blobServiceClient = BlobServiceClient.fromConnectionString(connectionString);

async function main() {
  const containerClient = blobServiceClient.getContainerClient(containerName);
  let links = [];
  for await (const blob of containerClient.listBlobsFlat()) {
    const url = `https://${account}.blob.core.windows.net/${containerName}/${blob.name}`;
    links.push(url);
  }

  // Generate HTML
  const html = `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Azure Blob Demo Files</title>
  <style>
    body { font-family: Segoe UI, Arial, sans-serif; margin: 2em; }
    h1 { color: #1976d2; }
    ul { line-height: 1.7; }
    a { color: #1976d2; }
  </style>
</head>
<body>
  <h1>Azure Blob Demo Files</h1>
  <ul>
    ${links.map(url => `<li><a href="${url}" target="_blank">${url}</a></li>`).join('\n    ')}
  </ul>
  <p style="color:#888;">Generated for Woodgrove Bank AI-102 Demo</p>
</body>
</html>
  `.trim();

  fs.writeFileSync('blob-report.html', html, 'utf8');
  console.log('HTML report generated: blob-report.html');
}

main().catch(err => {
  console.error('Error:', err.message);
}); 