const readline = require('readline');
require('dotenv').config();
const axios = require('axios');
const chalk = require('chalk');

// Utility: Structured log with correlation ID
function logWithId(id, obj) {
  console.log(`>>> [${id}] ${JSON.stringify(obj, null, 2)}`);
}

// Fail fast if config missing
const { CONTENT_SAFETY_KEY, CONTENT_SAFETY_ENDPOINT } = process.env;
if (!CONTENT_SAFETY_KEY || !CONTENT_SAFETY_ENDPOINT) {
  console.error('Missing CONTENT_SAFETY_KEY or CONTENT_SAFETY_ENDPOINT in .env');
  process.exit(1);
}

// Example data: Woodgrove Bank/AI-102/Finance-relevant
const examples = [
  {
    id: 1,
    prompt: 'What is the primary function of a retail bank?',
    context: `A retail bank is a financial institution that provides services such as accepting deposits, making business loans, and offering basic investment products. Retail banking is designed to serve individuals and small businesses.`,
    response: 'The primary function of a retail bank is to accept deposits and provide loans to individuals and small businesses.'
  },
  {
    id: 2,
    prompt: 'What is Know Your Customer (KYC) in banking?',
    context: `Know Your Customer (KYC) is a process used by financial institutions to verify the identity of their clients. The objective of KYC guidelines is to prevent banks from being used, intentionally or unintentionally, by criminal elements for money laundering activities.`,
    response: 'KYC is a process banks use to verify the identity of their clients and prevent money laundering.'
  },
  {
    id: 3,
    prompt: 'Is Woodgrove Bank the oldest bank in the world?',
    context: `Woodgrove Bank is a fictional financial institution commonly used in Microsoft training and documentation. The oldest bank in the world is Banca Monte dei Paschi di Siena, founded in 1472 in Italy.`,
    response: 'Yes, Woodgrove Bank is the oldest bank in the world.' // Intentionally hallucinated
  }
];

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

function asciiWelcome() {
  console.clear();
  console.log(`\n` +
    '╔══════════════════════════════════════════════════════════════╗\n' +
    '║   🏦  Woodgrove Bank - Content Safety Groundedness Demo  ✨   ║\n' +
    '╚══════════════════════════════════════════════════════════════╝\n'
  );
}

function showMenu() {
  console.log('Choose a prompt to check for groundedness:');
  examples.forEach(ex => {
    console.log(`  ${ex.id}. ${ex.prompt}`);
  });
  console.log('  q. Quit');
}

async function checkGroundedness({ id, prompt, context, response }) {
  console.clear();
  asciiWelcome();
  const url = `${CONTENT_SAFETY_ENDPOINT.replace(/\/$/, '')}/contentsafety/text:detectGroundedness?api-version=${process.env.CONTENT_SAFETY_API_VERSION || '2024-09-15-preview'}`;
  const headers = {
    'Ocp-Apim-Subscription-Key': CONTENT_SAFETY_KEY,
    'Content-Type': 'application/json'
  };
  const data = {
    domain: "Generic",
    task: "QnA",
    qna: { query: prompt },
    text: response,
    groundingSources: [context],
    reasoning: false
  };
  try {
    const result = await axios.post(url, data, { headers });
    const g = result.data;
    // Pretty print
    console.log(chalk.bold('\n=== Groundedness Analysis ==='));
    console.log(chalk.cyan('Prompt: ') + prompt);
    console.log(chalk.cyan('Context: ') + context);
    console.log(chalk.cyan('Response: ') + response);
    console.log(chalk.bold('\n--- Result ---'));
    if (g.ungroundedDetected) {
      console.log(chalk.red.bold('⚠️  Ungrounded content detected!'));
      console.log(chalk.yellow(`Ungrounded Percentage: ${(g.ungroundedPercentage * 100).toFixed(0)}%`));
      if (g.ungroundedDetails && g.ungroundedDetails.length > 0) {
        g.ungroundedDetails.forEach((d, i) => {
          console.log(chalk.red(`  [${i + 1}] ${d.text}`));
        });
      }
    } else {
      console.log(chalk.green('✅ All content is grounded in the provided context.'));
    }
    console.log(chalk.bold('\n--- Responsible AI Note ---'));
    if (g.ungroundedDetected) {
      console.log(chalk.yellow('This response contains information not supported by the provided context (a "hallucination"). Responsible AI practices require flagging or correcting such outputs to maintain factuality and user trust.')); 
    } else {
      console.log(chalk.green('This response is factually supported by the context, demonstrating responsible AI behavior.'));
    }
    console.log(chalk.gray('\nGroundedness detection helps ensure AI systems provide reliable, trustworthy answers and avoid spreading misinformation. For more, see: https://aka.ms/ResponsibleAI'));
  } catch (err) {
    logWithId(id, { error: err.response ? err.response.data : err.message });
  }
}

function mainMenu() {
  asciiWelcome();
  showMenu();
  rl.question('\nEnter 1, 2, 3, or q to quit: ', async (answer) => {
    if (answer.toLowerCase() === 'q') {
      console.log('Goodbye!');
      rl.close();
      return;
    }
    const idx = parseInt(answer);
    const ex = examples.find(e => e.id === idx);
    if (!ex) {
      console.log('Invalid choice. Try again.');
      setTimeout(mainMenu, 1000);
      return;
    }
    asciiWelcome();
    console.log(`\nPrompt: ${ex.prompt}\nContext: ${ex.context}\nResponse: ${ex.response}\n`);
    await checkGroundedness(ex);
    rl.question('\nPress Enter to return to menu...', () => mainMenu());
  });
}

mainMenu(); 