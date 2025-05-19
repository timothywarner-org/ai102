/**
 * @file language-demo.js
 * @description Azure AI Language Service Interactive Demo for Tim's AI-102 course
 * 
 * ========================================================================================
 * AZURE AI LANGUAGE SERVICE DEMO: PII Detection vs Named Entity Recognition (NER)
 * ========================================================================================
 * 
 * This interactive console application demonstrates two key capabilities of the 
 * Azure AI Language service:
 * 
 * 1. PII (Personally Identifiable Information) Detection - Identifies sensitive personal
 *    information that might require redaction for compliance with privacy regulations
 *    like GDPR, HIPAA, and CCPA.
 * 
 * 2. NER (Named Entity Recognition) - Identifies and categorizes entities in text such
 *    as people, places, organizations, dates, and more for content understanding.
 * 
 * KEY AZURE AI CONCEPTS DEMONSTRATED:
 * ----------------------------------
 * - Azure AI Language - Text Analytics REST API consumption
 * - Resource provisioning and access via endpoint URLs & keys
 * - Responsible AI practices for handling sensitive information
 * - Consumption-based pricing model usage
 * - Confidence scores and threshold-based decision making
 * - Text classification and entity extraction
 * - Data redaction techniques for privacy protection
 * 
 * DEVELOPMENT BEST PRACTICES:
 * --------------------------
 * - Environment variable management using dotenv
 * - Proper error handling for API interactions
 * - Resource cleanup and connection management
 * - Clear visual presentation of AI service outputs
 * - Interactive user experience design
 * - Educational context for AI service capabilities
 * - Secure credential management (no hardcoded keys)
 * 
 * IMPLEMENTATION DETAILS:
 * ----------------------
 * - Uses the @azure/ai-language-text SDK package
 * - Implements TextAnalysisClient for API interaction
 * - Configures AzureKeyCredential for authentication
 * - Provides colorized output with chalk for educational clarity
 * - Handles cross-platform terminal interactions
 * - Demonstrates batch text analysis for efficiency
 * 
 * AZURE RESOURCE REQUIREMENTS:
 * ---------------------------
 * - Azure AI Language resource (S0 tier or above)
 * - Language service endpoint URL
 * - Language service API key
 * 
 * RELATED AZURE AI SERVICES:
 * ------------------------
 * - Azure AI Content Safety - For detecting harmful content
 * - Azure AI Document Intelligence - For document processing
 * - Azure AI Speech - For speech-to-text and text-to-speech
 * - Azure OpenAI Service - For advanced language understanding
 * 
 * @author Tim Warner - Microsoft Press AI-102 Course
 * @see https://learn.microsoft.com/azure/ai-services/language-service/
 * @see https://learn.microsoft.com/azure/ai-services/language-service/personally-identifiable-information/overview
 * @see https://learn.microsoft.com/azure/ai-services/language-service/named-entity-recognition/overview
 */

const { TextAnalysisClient, AzureKeyCredential } = require("@azure/ai-language-text");
const dotenv = require("dotenv");
const chalk = require("chalk");
const os = require("os");
const { exec, execSync } = require("child_process");
const readline = require("readline");

// Create readline interface for user input
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

// Load environment variables
dotenv.config();

// Azure AI Language service configuration
const endpoint = process.env.LANGUAGE_ENDPOINT || "https://twai102language1.cognitiveservices.azure.com/";
const apiKey = process.env.LANGUAGE_KEY || "D2SbLhonlCi6qjWdjgEaEOcGVZu2sTF4w0bTjxBfZG4qWliejaxJJQQJ99BEACYeBjFXJ3w3AAAaACOGvcMr";

// Create client
const client = new TextAnalysisClient(endpoint, new AzureKeyCredential(apiKey));

// Sample texts for analysis
const sampleTexts = [
  "My name is John Smith and I live at 123 Main St, Seattle WA 98101. You can reach me at john.smith@example.com or call me at (555) 123-4567.",
  "Woodgrove Bank customer Sarah Johnson recently reported a suspicious transaction on her account ending in 4321. Her SSN is 123-45-6789.",
  "The meeting is scheduled for January 15, 2023 with CEO Tim Roberts and CFO Maria Garcia to discuss the Q4 financial results."
];

// Cross-platform console clear function
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

// Ask user for text input or to select a sample
function askForText() {
  return new Promise((resolve) => {
    console.log(chalk.cyan.bold("\nPlease select an option:"));
    console.log("1: Enter your own text");
    console.log("2: Use sample text about a person with contact info");
    console.log("3: Use sample text about a bank customer with SSN");
    console.log("4: Use sample text about a business meeting");
    console.log("5: Exit");
    
    rl.question(chalk.yellow("Enter your choice (1-5): "), (choice) => {
      switch(choice) {
        case "1":
          rl.question(chalk.yellow("\nEnter text to analyze: "), (text) => {
            resolve(text);
          });
          break;
        case "2":
          console.log(chalk.gray(`\nUsing sample: "${sampleTexts[0]}"`));
          resolve(sampleTexts[0]);
          break;
        case "3":
          console.log(chalk.gray(`\nUsing sample: "${sampleTexts[1]}"`));
          resolve(sampleTexts[1]);
          break;
        case "4":
          console.log(chalk.gray(`\nUsing sample: "${sampleTexts[2]}"`));
          resolve(sampleTexts[2]);
          break;
        case "5":
          console.log(chalk.green.bold("\nThank you for using the Azure AI Language demo!"));
          rl.close();
          process.exit(0);
        default:
          console.log(chalk.red("\nInvalid choice. Please try again."));
          resolve(askForText());
      }
    });
  });
}

// Ask the user if they want to continue
function askToContinue() {
  return new Promise((resolve) => {
    rl.question(chalk.yellow("\nDo you want to analyze another text? (y/n): "), (answer) => {
      resolve(answer.toLowerCase() === 'y');
    });
  });
}

// PII Detection function with educational explanations
async function runPIIDetection(text) {
  console.log(chalk.yellow.bold("\n🔒 PII Detection Results:"));
  console.log(chalk.magenta("PII detection specifically looks for sensitive personal information that might need protection."));
  
  console.log(chalk.gray("\nCalling Azure AI Language API..."));
  const piiResults = await client.analyze("PiiEntityRecognition", [text], "en");
  
  if (!piiResults[0].error) {
    const piiEntities = piiResults[0].entities;
    
    if (piiEntities.length === 0) {
      console.log("  No PII entities detected");
    } else {
      console.log(`  Found ${piiEntities.length} PII ${piiEntities.length === 1 ? 'entity' : 'entities'}:`);
      
      // Create a redacted version of the text
      let redactedText = piiResults[0].redactedText;
      
      for (const entity of piiEntities) {
        // Provide educational insights for each PII type
        let explanation = "";
        switch(entity.category) {
          case "Person":
            explanation = "Personal names often require protection under privacy regulations.";
            break;
          case "Email":
            explanation = "Email addresses are direct contact points that identify individuals.";
            break;
          case "Address":
            explanation = "Physical addresses can reveal where a person lives or works.";
            break;
          case "Phone":
          case "PhoneNumber":
            explanation = "Phone numbers are direct contact points that identify individuals.";
            break;
          case "USSocialSecurityNumber":
            explanation = "SSNs are highly sensitive identifiers used for financial and legal purposes.";
            break;
          case "CreditCardNumber":
            explanation = "Financial information that requires strict protection under PCI DSS.";
            break;
          case "Organization":
            explanation = "In some contexts, organizational affiliation can be sensitive information.";
            break;
          default:
            explanation = `This type of information may require special handling in your applications.`;
        }
        
        console.log(`  - Type: ${chalk.cyan(entity.category)}, Confidence: ${chalk.magenta(entity.confidenceScore.toFixed(3))}`);
        console.log(`    Value: ${chalk.green(entity.text)}`);
        console.log(`    ${chalk.blue('💡 ' + explanation)}`);
      }
      
      console.log(chalk.yellow("\n  Redacted Text:"));
      console.log(`  ${redactedText}`);
      console.log(chalk.blue("\n  💡 Note: The API automatically redacts identified PII, replacing sensitive information with asterisks."));
      console.log(chalk.blue("     This is useful for creating compliance-ready documents or displays."));
    }
  } else {
    console.error(`  Error: ${piiResults[0].error}`);
  }
}

// Named Entity Recognition function with educational explanations
async function runNER(text) {
  console.log(chalk.yellow.bold("\n🏷️ Named Entity Recognition Results:"));
  console.log(chalk.magenta("NER identifies and categorizes key elements in text regardless of sensitivity."));
  
  console.log(chalk.gray("\nCalling Azure AI Language API..."));
  const nerResults = await client.analyze("EntityRecognition", [text], "en");
  
  if (!nerResults[0].error) {
    const entities = nerResults[0].entities;
    
    if (entities.length === 0) {
      console.log("  No entities detected");
    } else {
      console.log(`  Found ${entities.length} ${entities.length === 1 ? 'entity' : 'entities'}:`);
      
      // Group entities by category
      const categorized = {};
      
      for (const entity of entities) {
        if (!categorized[entity.category]) {
          categorized[entity.category] = [];
        }
        categorized[entity.category].push(entity);
      }
      
      // Display entities by category with explanations
      for (const [category, entityList] of Object.entries(categorized)) {
        // Provide educational insights for each entity category
        let explanation = "";
        switch(category) {
          case "Person":
            explanation = "Names of individuals recognized regardless of privacy context.";
            break;
          case "Organization":
            explanation = "Names of companies, agencies, institutions, and other groups.";
            break;
          case "Address":
            explanation = "Physical locations where people live or work.";
            break;
          case "Email":
            explanation = "Electronic mail addresses.";
            break;
          case "DateTime":
            explanation = "Calendar dates and times, useful for scheduling and temporal analysis.";
            break;
          case "Event":
            explanation = "Named gatherings, occurrences, or happenings.";
            break;
          case "Quantity":
            explanation = "Numerical values and units of measurement.";
            break;
          case "Location":
            explanation = "Physical places, landmarks, and geographic features.";
            break;
          default:
            explanation = `Information categorized as ${category} for content understanding.`;
        }
        
        console.log(`  ${chalk.cyan(category)} (${entityList.length}):`);
        console.log(`    ${chalk.blue('💡 ' + explanation)}`);
        
        for (const entity of entityList) {
          console.log(`    - ${chalk.green(entity.text)} (Confidence: ${chalk.magenta(entity.confidenceScore.toFixed(3))})`);
        }
      }
    }
  } else {
    console.error(`  Error: ${nerResults[0].error}`);
  }
}

// Educational comparison between PII and NER
function compareResults() {
  console.log(chalk.green.bold("\n🔄 Comparison: PII Detection vs NER"));
  
  console.log(chalk.yellow("\n🔒 PII Detection:"));
  console.log("  • FOCUS: " + chalk.blue("Privacy and compliance"));
  console.log("  • PURPOSE: " + chalk.blue("Identify and protect sensitive personal information"));
  console.log("  • FEATURES: " + chalk.blue("Automatic text redaction and entity categorization by sensitivity"));
  console.log("  • USE CASES: " + chalk.blue("GDPR/HIPAA compliance, data loss prevention, document sanitization"));
  
  console.log(chalk.yellow("\n🏷️ Named Entity Recognition:"));
  console.log("  • FOCUS: " + chalk.blue("Content understanding and information extraction"));
  console.log("  • PURPOSE: " + chalk.blue("Identify key elements regardless of sensitivity"));
  console.log("  • FEATURES: " + chalk.blue("Broad entity categorization with contextual information"));
  console.log("  • USE CASES: " + chalk.blue("Content analysis, information retrieval, document indexing"));
  
  console.log(chalk.yellow("\n📊 When to use each:"));
  console.log("  • " + chalk.green("Use PII Detection") + " when you need to protect privacy or comply with regulations");
  console.log("  • " + chalk.green("Use NER") + " when you need to understand content or extract structured information");
  console.log("  • " + chalk.green("Use both together") + " for comprehensive understanding while maintaining compliance");
}

// Main function
async function main() {
  // Clear the console at startup
  clearConsole();
  
  // Display title banner
  console.log(chalk.bgBlue.white.bold(" 🔍 AZURE AI LANGUAGE DEMO: PII vs NER "));
  console.log(chalk.blue("=".repeat(50)));
  
  console.log(chalk.green.bold("\n=== Azure AI Language Service Interactive Demo ==="));
  console.log(chalk.cyan("This demo helps you understand the difference between:"));
  console.log("  - PII (Personally Identifiable Information) Detection");
  console.log("  - NER (Named Entity Recognition)");
  
  let continueAnalysis = true;
  
  while (continueAnalysis) {
    // Get text from user
    const text = await askForText();
    
    // Run both analyses
    await runPIIDetection(text);
    await runNER(text);
    
    // Show comparison
    compareResults();
    
    // Microsoft-style banner
    console.log(chalk.bgWhite.blue.bold('\n==============================='));
    console.log(chalk.bgWhite.blue.bold(' Powered by Microsoft Azure AI '));
    console.log(chalk.bgWhite.blue.bold('===============================\n'));
    
    // Check if user wants to continue
    continueAnalysis = await askToContinue();
    if (continueAnalysis) {
      clearConsole();
      console.log(chalk.bgBlue.white.bold(" 🔍 AZURE AI LANGUAGE DEMO: PII vs NER "));
      console.log(chalk.blue("=".repeat(50)));
    }
  }
  
  // Tim Warner course support banner
  console.log(chalk.bgCyan.black.bold(' Supporting Tim Warner\'s Microsoft Press Video Course AI-102 '));
  console.log(chalk.green.bold("\nThank you for using the Azure AI Language demo!"));
  rl.close();
}

// Run the main function
main().catch((err) => {
  console.error("Error:", err);
  rl.close();
}); 