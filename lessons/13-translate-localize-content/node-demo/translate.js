require('dotenv').config();
const { Translator } = require('@azure-rest/ai-translation-text');
const { AzureKeyCredential } = require('@azure/core-auth');

const endpoint = process.env.TRANSLATOR_ENDPOINT;
const key = process.env.TRANSLATOR_KEY;

const client = Translator(endpoint, new AzureKeyCredential(key));
const text = process.argv[2] || 'Hello world';

async function main() {
  const result = await client.path('/translate').post({
    queryParameters: { 'to': 'fr' },
    body: [{ Text: text }],
    headers: { 'Content-Type': 'application/json' }
  });
  console.log(JSON.stringify(result.body, null, 2));
}

main().catch(console.error);
