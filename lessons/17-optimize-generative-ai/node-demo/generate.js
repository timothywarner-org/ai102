require('dotenv').config();
const { OpenAIClient, AzureKeyCredential } = require('@azure/openai');

const endpoint = process.env.AZURE_OPENAI_ENDPOINT;
const key = process.env.AZURE_OPENAI_KEY;
const deployment = process.env.AZURE_OPENAI_DEPLOYMENT;

const client = new OpenAIClient(endpoint, new AzureKeyCredential(key));
const prompt = process.argv.slice(2).join(' ') || 'Tell me a joke.';

async function main() {
  const result = await client.getCompletions(deployment, prompt, { temperature: 0.2 });
  console.log(result.choices[0].text.trim());
}

main().catch(console.error);
