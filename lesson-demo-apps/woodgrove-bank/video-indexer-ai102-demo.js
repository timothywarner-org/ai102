/**
 * AI-102 Azure Video Indexer Demo
 * 
 * This script demonstrates how to use Azure Video Indexer to analyze a local video file.
 * 
 * LEGAL NOTICE:
 * The video analyzed is:
 *   "SampleVideo_1280x720_1mb" available at https://archive.org/details/SampleVideo1280x7201mb
 * This video is used strictly for educational and demonstration purposes.
 * 
 * References:
 * - https://learn.microsoft.com/en-us/azure/azure-video-indexer/video-indexer-use-apis
 * - https://github.com/Azure-Samples/azure-video-indexer-samples
 */

require('dotenv').config();
const axios = require('axios');
const cliProgress = require('cli-progress'); // For progress metering
const chalk = require('chalk');
const fs = require('fs');
const FormData = require('form-data');

// --- Config ---
const REGION = process.env.VIDEO_INDEXER_REGION || 'eastus';
const ACCOUNT_ID = process.env.VIDEO_INDEXER_ACCOUNT_ID;
const ACCESS_TOKEN = process.env.VIDEO_INDEXER_ACCESS_TOKEN;
const API_BASE = 'https://api.videoindexer.ai';
const VIDEO_FILE_PATH = './video/SampleVideo_1280x720_1mb.mp4'; // Local file path

// Validate environment variables
if (!REGION || !ACCOUNT_ID || !ACCESS_TOKEN) {
  console.error(chalk.red('[ERROR] Missing required configuration. Please check your environment variables.'));
  process.exit(1);
}

// --- Helper: Sleep ---
const sleep = ms => new Promise(res => setTimeout(res, ms));

// --- Step 1: Upload Video by File ---
async function uploadVideoByFile(accountId, accessToken, filePath) {
  console.log(chalk.blueBright('\n[INFO] Uploading local video file for analysis...'));
  const url = `${API_BASE}/${REGION}/Accounts/${accountId}/Videos?accessToken=${accessToken}`;
  const formData = new FormData();
  formData.append('file', fs.createReadStream(filePath));
  formData.append('name', 'AI-102 Local File Demo');
  formData.append('description', 'Demo for AI-102 using a local video file.');
  formData.append('privacy', 'Private');
  formData.append('language', 'English');

  try {
    const res = await axios.post(url, formData, {
      headers: formData.getHeaders(),
    });
    return res.data.id;
  } catch (err) {
    console.error(chalk.red('[ERROR] Failed to upload video:'), err.response?.data || err.message);
    throw err;
  }
}

// --- Step 2: Poll for Indexing Status ---
async function pollForIndexing(accountId, accessToken, videoId) {
  const url = `${API_BASE}/${REGION}/Accounts/${accountId}/Videos/${videoId}/Index?accessToken=${accessToken}`;
  let state = 'Uploaded';
  const bar = new cliProgress.SingleBar({
    format: 'Indexing Progress |' + chalk.cyan('{bar}') + '| {percentage}% | {state}',
    barCompleteChar: '\u2588',
    barIncompleteChar: '\u2591',
    hideCursor: true,
  });
  bar.start(100, 0, { state });

  while (state !== 'Processed' && state !== 'Failed') {
    try {
      const res = await axios.get(url);
      state = res.data.state;
      const progress = res.data.progress || 0;
      bar.update(progress, { state });
      if (state === 'Failed') {
        bar.stop();
        throw new Error('Video indexing failed.');
      }
      await sleep(10000); // Poll every 10 seconds
    } catch (err) {
      console.error(chalk.red('[ERROR] Failed to poll indexing status:'), err.response?.data || err.message);
      throw err;
    }
  }
  bar.update(100, { state: 'Processed' });
  bar.stop();
  return true;
}

// --- Step 3: Fetch and Display Insights ---
async function getVideoInsights(accountId, accessToken, videoId) {
  const url = `${API_BASE}/${REGION}/Accounts/${accountId}/Videos/${videoId}/Index?accessToken=${accessToken}`;
  const res = await axios.get(url);
  return res.data;
}

function printInsights(insights) {
  console.log(chalk.green('\n[RESULT] Video Insights Summary:'));
  if (insights.summarizedInsights) {
    const { faces, brands, namedLocations, namedPeople, topics } = insights.summarizedInsights;
    console.log(chalk.yellow('Faces:'), faces?.map(f => f.name).join(', ') || 'None');
    console.log(chalk.yellow('Brands:'), brands?.map(b => b.name).join(', ') || 'None');
    console.log(chalk.yellow('Locations:'), namedLocations?.map(l => l.name).join(', ') || 'None');
    console.log(chalk.yellow('People:'), namedPeople?.map(p => p.name).join(', ') || 'None');
    console.log(chalk.yellow('Topics:'), topics?.map(t => t.name).join(', ') || 'None');
  }
  if (insights.videos?.[0]?.insights?.transcript) {
    console.log(chalk.cyan('\nTranscript (first 5 lines):'));
    insights.videos[0].insights.transcript.slice(0, 5).forEach(line =>
      console.log(`- [${line.time}] ${line.text}`)
    );
  }
}

// --- Main ---
(async () => {
  try {
    console.log(chalk.magenta.bold('\n=== AI-102 Azure Video Indexer Demo ==='));
    console.log(chalk.magenta('Analyzing local video file for educational purposes.'));
    console.log(chalk.magenta('Video File Path:'), VIDEO_FILE_PATH);

    // Step 1: Upload
    const videoId = await uploadVideoByFile(ACCOUNT_ID, ACCESS_TOKEN, VIDEO_FILE_PATH);
    console.log(chalk.blueBright('[INFO] Video uploaded. Video ID:'), videoId);

    // Step 2: Poll for Indexing
    await pollForIndexing(ACCOUNT_ID, ACCESS_TOKEN, videoId);

    // Step 3: Fetch Insights
    const insights = await getVideoInsights(ACCOUNT_ID, ACCESS_TOKEN, videoId);
    printInsights(insights);

    console.log(chalk.green.bold('\n[COMPLETE] Video analysis finished. See above for summary.'));
    console.log(chalk.gray('For more details, see the Azure Portal or Video Indexer web UI.'));
  } catch (err) {
    console.error(chalk.red('[ERROR]'), err.response?.data || err.message);
  }
})();