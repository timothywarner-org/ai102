require('dotenv').config();
const { PredictionAPIClient } = require('@azure/cognitiveservices-customvision-prediction');
const { CognitiveServicesCredentials } = require('@azure/ms-rest-js');
const fs = require('fs');

const endpoint = process.env.CUSTOM_VISION_ENDPOINT;
const key = process.env.CUSTOM_VISION_PREDICTION_KEY;
const projectId = process.env.CUSTOM_VISION_PROJECT_ID;
const publishedName = process.env.CUSTOM_VISION_PUBLISHED_NAME;
const imagePath = process.argv[2];

if (!imagePath) {
  console.error('Usage: node app.js <imagePath>');
  process.exit(1);
}

async function main() {
  const creds = new CognitiveServicesCredentials(key);
  const client = new PredictionAPIClient(creds, endpoint);
  const image = fs.readFileSync(imagePath);
  const result = await client.classifyImage(projectId, publishedName, image);
  result.predictions.forEach(p => {
    console.log(`${p.tagName}: ${(p.probability * 100).toFixed(2)}%`);
  });
}

main().catch(err => console.error('Error:', err));
