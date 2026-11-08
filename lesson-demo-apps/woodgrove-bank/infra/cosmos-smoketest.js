// Woodgrove Bank AI-102 Cosmos DB Smoke Test
// SHINE: Progress metering, robust error handling, and teaching comments

require('dotenv').config();
const { CosmosClient } = require('@azure/cosmos');

const endpoint = process.env.COSMOS_URI;
const key = process.env.COSMOS_KEY;
const databaseId = process.env.COSMOS_DB;
const containerId = process.env.COSMOS_CONTAINER;
const partitionKey = process.env.COSMOS_PARTITION_KEY;

const client = new CosmosClient({ endpoint, key });

function banner(msg) {
  console.log('\n' + '='.repeat(60));
  console.log('>>>', msg);
  console.log('='.repeat(60));
}

async function main() {
  const start = Date.now();
  try {
    banner('Connecting to Cosmos DB...');
    const { database } = await client.databases.createIfNotExists({ id: databaseId });
    banner('Ensuring container exists...');
    const { container } = await database.containers.createIfNotExists({
      id: containerId,
      partitionKey: { paths: [partitionKey] }
    });

    banner('Inserting sample Vision result document...');
    const item = {
      id: 'dog-20240601-001',
      filename: 'dog.jpg',
      url: 'https://techtrainertimstorage.blob.core.windows.net/demos/dog.jpg',
      uploadedBy: 'tim.warner',
      uploadDate: new Date().toISOString(),
      correlationId: 'demo-corr-1234',
      visionResult: {
        tags: [
          { name: 'dog', confidence: 0.99 },
          { name: 'animal', confidence: 0.95 }
        ],
        objects: [
          { object: 'dog', confidence: 0.98, rectangle: { x: 10, y: 20, w: 100, h: 80 } }
        ],
        description: {
          captions: [
            { text: 'A dog sitting on grass', confidence: 0.97 }
          ]
        }
      }
    };

    const { resource } = await container.items.upsert(item);
    console.log('✅ Inserted item:', resource);

    banner('Querying back by filename...');
    const { resources } = await container.items
      .query('SELECT * FROM c WHERE c.filename = @filename', { parameters: [{ name: '@filename', value: 'dog.jpg' }] })
      .fetchAll();
    console.log('🔎 Query result:', resources);

    banner('Smoke test completed successfully!');
    console.log(`Total time: ${(Date.now() - start) / 1000}s`);
  } catch (err) {
    banner('❌ ERROR');
    if (err.code === 401) {
      console.error('Authentication failed. Check your COSMOS_KEY and COSMOS_URI.');
    } else if (err.code === 'ENOTFOUND') {
      console.error('Network error. Check your COSMOS_URI and internet connection.');
    } else {
      console.error('Unexpected error:', err.message || err);
    }
    process.exit(1);
  }
}

main(); 