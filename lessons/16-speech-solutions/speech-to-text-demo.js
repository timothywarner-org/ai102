/**
 * @file speech-to-text-demo.js
 * @description Azure AI Speech Service (Speech-to-Text) Demo for Woodgrove Bank
 * 
 * ========================================================================================
 * AZURE AI SPEECH SERVICE DEMO: Speech-to-Text for Banking Customer Service
 * ========================================================================================
 * 
 * This interactive console application demonstrates key capabilities of the 
 * Azure AI Speech service with a banking context:
 * 
 * 1. Speech-to-Text (STT) - Converts spoken audio to text, enabling voice commands and
 *    transcription for bank customer service interactions.
 * 
 * 2. Language Detection - Automatically identifies the language being spoken to properly
 *    route customers to appropriate service representatives.
 * 
 * KEY AZURE AI CONCEPTS DEMONSTRATED:
 * ----------------------------------
 * - Azure AI Speech Service SDK usage
 * - Real-time speech recognition
 * - Language identification from speech
 * - Continuous recognition with streaming audio
 * - Banking-specific terminology handling
 * - Intent recognition from spoken commands
 * 
 * DEVELOPMENT BEST PRACTICES:
 * --------------------------
 * - Environment variable management using dotenv
 * - Proper error handling for audio interactions
 * - Resource cleanup and connection management
 * - Clear visual presentation of AI service outputs
 * - Interactive user experience design
 * - Educational context for AI service capabilities
 * - Secure credential management (no hardcoded keys)
 * 
 * IMPLEMENTATION DETAILS:
 * ----------------------
 * - Uses the microsoft-cognitiveservices-speech-sdk package
 * - Configures SpeechConfig for API authentication
 * - Provides colorized output with chalk for educational clarity
 * - Handles microphone input for real-time speech recognition
 * - Demonstrates both one-time and continuous recognition scenarios
 * 
 * AZURE RESOURCE REQUIREMENTS:
 * ---------------------------
 * - Azure AI Speech resource (S0 tier or above)
 * - Speech service endpoint URL
 * - Speech service API key
 * 
 * RELATED AZURE AI SERVICES:
 * ------------------------
 * - Azure AI Language - For intent analysis of transcribed text
 * - Azure AI Content Safety - For monitoring inappropriate content
 * - Azure OpenAI Service - For advanced conversational AI
 * 
 * @author Tim Warner - Microsoft Press AI-102 Course
 * @see https://learn.microsoft.com/azure/ai-services/speech-service/
 * @see https://learn.microsoft.com/azure/ai-services/speech-service/speech-to-text
 * @see https://learn.microsoft.com/azure/ai-services/speech-service/language-identification
 */

// Required dependencies
const sdk = require("microsoft-cognitiveservices-speech-sdk");
const dotenv = require("dotenv");
const chalk = require("chalk");
const readline = require("readline");

// Load environment variables
dotenv.config();

// Create readline interface for user input
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

// Azure AI Speech service configuration
const speechKey = process.env.SPEECH_KEY || "YOUR_SPEECH_KEY";
const speechRegion = process.env.SPEECH_REGION || "eastus";

// Banking-specific phrases that might be encountered in customer service
const bankingPhrases = [
  "check my account balance",
  "transfer funds to savings",
  "report a lost card",
  "setup direct deposit",
  "what's my available credit",
  "reset my online banking password",
  "schedule a mortgage payment",
  "dispute a transaction",
  "activate my new credit card",
  "change my PIN number"
];

// Sample banking scenarios to test speech recognition
const bankingScenarios = [
  "Customer calling to check their account balance and recent transactions",
  "Customer needs to report a lost debit card and request a replacement",
  "Customer wants to transfer money between accounts and set up recurring transfers",
  "Customer seeking information about mortgage rates and application process",
  "Customer reporting a suspicious transaction and concerned about fraud"
];

// Sample audio files for testing without a microphone
const sampleAudioFiles = [
  {
    name: "Banking inquiry",
    path: "./samples/audio/banking.wav",
    description: "A simple query that can be analyzed for banking intent"
  },
  {
    name: "Healthcare conversation",
    path: "./samples/audio/healthcare.wav",
    description: "A healthcare conversation that demonstrates more complex recognition"
  }
];

/**
 * Performs one-time speech recognition from microphone
 */
async function recognizeSpeechOnce() {
  return new Promise((resolve, reject) => {
    // Configure speech recognition with Azure AI Speech service
    const speechConfig = sdk.SpeechConfig.fromSubscription(speechKey, speechRegion);
    speechConfig.speechRecognitionLanguage = "en-US";
    
    // Optional: Enable profanity filtering
    speechConfig.setProfanity(sdk.ProfanityOption.Masked);
    
    console.log(chalk.yellow("\n🎤 Please speak clearly into your microphone when prompted..."));
    console.log(chalk.gray("(Demo banking phrases you could try are shown below)"));
    
    // Display some example banking phrases the user could try
    bankingPhrases.slice(0, 5).forEach(phrase => {
      console.log(chalk.cyan(`  • "${phrase}"`));
    });
    
    // Create an audio config using default microphone
    const audioConfig = sdk.AudioConfig.fromDefaultMicrophoneInput();
    
    // Create speech recognizer
    const recognizer = new sdk.SpeechRecognizer(speechConfig, audioConfig);
    
    console.log(chalk.green.bold("\nListening... Speak now! 🎤"));
    console.log(chalk.gray("(Speak a banking-related query or command)"));
    
    // Start speech recognition
    recognizer.recognizeOnceAsync(
      (result) => {
        // Process speech recognition result
        if (result.reason === sdk.ResultReason.RecognizedSpeech) {
          console.log(chalk.green.bold("\n✅ Speech recognized:"));
          console.log(`  ${chalk.white.bold(result.text)}`);
          
          // Bank-specific response simulation
          simulateBankResponse(result.text);
        } 
        else if (result.reason === sdk.ResultReason.NoMatch) {
          console.log(chalk.red("\n❌ No speech could be recognized."));
          console.log(chalk.gray("  Try speaking more clearly or check your microphone."));
        } 
        else if (result.reason === sdk.ResultReason.Canceled) {
          const cancellation = sdk.CancellationDetails.fromResult(result);
          console.log(chalk.red(`\n❌ Speech recognition canceled: ${cancellation.reason}`));
          
          if (cancellation.reason === sdk.CancellationReason.Error) {
            console.log(chalk.red(`  Error details: ${cancellation.errorDetails}`));
            
            // Provide helpful troubleshooting based on error
            if (cancellation.errorDetails.includes("microphone")) {
              console.log(chalk.yellow("  💡 Troubleshooting: Check if your microphone is properly connected and enabled."));
            } else if (cancellation.errorDetails.includes("authorization")) {
              console.log(chalk.yellow("  💡 Troubleshooting: Verify your Azure AI Speech key and region are correct."));
            }
          }
        }
        
        // Clean up resources
        recognizer.close();
        resolve(result);
      },
      (err) => {
        console.log(chalk.red(`\n❌ ERROR: ${err}`));
        recognizer.close();
        reject(err);
      }
    );
  });
}

/**
 * Performs language identification from speech
 */
async function identifySpokenLanguage() {
  return new Promise((resolve, reject) => {
    // Configure speech recognition with language identification
    const speechConfig = sdk.SpeechConfig.fromSubscription(speechKey, speechRegion);
    
    // Create auto language detection config with the languages we want to identify
    // Common banking customer service languages
    const autoDetectConfig = sdk.AutoDetectSourceLanguageConfig.fromLanguages([
      "en-US", "es-ES", "fr-FR", "de-DE", "zh-CN"
    ]);
    
    // Display language options
    console.log(chalk.yellow("\n🌎 Language Detection - Speak in any of these languages:"));
    console.log(chalk.cyan("  • English (en-US)"));
    console.log(chalk.cyan("  • Spanish (es-ES)"));
    console.log(chalk.cyan("  • French (fr-FR)"));
    console.log(chalk.cyan("  • German (de-DE)"));
    console.log(chalk.cyan("  • Chinese (zh-CN)"));
    
    // Create an audio config using default microphone
    const audioConfig = sdk.AudioConfig.fromDefaultMicrophoneInput();
    
    // Create speech recognizer with language detection
    const recognizer = new sdk.SpeechRecognizer.FromConfig(
      speechConfig, 
      autoDetectConfig, 
      audioConfig
    );
    
    console.log(chalk.green.bold("\nListening... Speak in any supported language! 🎤"));
    
    // Start speech recognition
    recognizer.recognizeOnceAsync(
      (result) => {
        if (result.reason === sdk.ResultReason.RecognizedSpeech) {
          // Get the detected language
          let language = "Unknown";
          
          // Extract language from properties if available
          if (result.properties && 
              result.properties.getProperty(sdk.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult)) {
            language = result.properties.getProperty(sdk.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult);
          }
          
          console.log(chalk.green.bold("\n✅ Speech recognized:"));
          console.log(`  ${chalk.white.bold(result.text)}`);
          console.log(chalk.magenta(`  Detected language: ${language}`));
          
          // Simulate bank routing based on language
          simulateLanguageRouting(language);
        } 
        else if (result.reason === sdk.ResultReason.NoMatch) {
          console.log(chalk.red("\n❌ No speech could be recognized or language not supported."));
        } 
        else if (result.reason === sdk.ResultReason.Canceled) {
          const cancellation = sdk.CancellationDetails.fromResult(result);
          console.log(chalk.red(`\n❌ Speech recognition canceled: ${cancellation.reason}`));
          
          if (cancellation.reason === sdk.CancellationReason.Error) {
            console.log(chalk.red(`  Error details: ${cancellation.errorDetails}`));
          }
        }
        
        // Clean up resources
        recognizer.close();
        resolve(result);
      },
      (err) => {
        console.log(chalk.red(`\n❌ ERROR: ${err}`));
        recognizer.close();
        reject(err);
      }
    );
  });
}

/**
 * Simulates continuous speech recognition for bank customer service
 */
async function simulateBankingCall() {
  return new Promise((resolve, reject) => {
    // Select a random banking scenario
    const scenarioIndex = Math.floor(Math.random() * bankingScenarios.length);
    const scenario = bankingScenarios[scenarioIndex];
    
    console.log(chalk.yellow.bold("\n📞 Banking Call Simulation"));
    console.log(chalk.yellow("Scenario: ") + chalk.white(scenario));
    console.log(chalk.gray("This will continuously recognize speech until you say 'end call' or press Ctrl+C"));
    
    // Configure speech recognition
    const speechConfig = sdk.SpeechConfig.fromSubscription(speechKey, speechRegion);
    speechConfig.speechRecognitionLanguage = "en-US";
    
    // Create audio config from default microphone
    const audioConfig = sdk.AudioConfig.fromDefaultMicrophoneInput();
    
    // Create speech recognizer
    const recognizer = new sdk.SpeechRecognizer(speechConfig, audioConfig);
    
    // Prepare to receive recognition results
    recognizer.recognized = (s, e) => {
      if (e.result.reason === sdk.ResultReason.RecognizedSpeech) {
        const text = e.result.text;
        console.log(chalk.green.bold("\n✅ Customer said:"));
        console.log(`  ${chalk.white.bold(text)}`);
        
        // Check for end call command
        if (text.toLowerCase().includes("end call")) {
          console.log(chalk.yellow("\n📞 Call ended by customer"));
          recognizer.stopContinuousRecognitionAsync();
          resolve();
          return;
        }
        
        // Simulate bank representative response
        simulateBankResponse(text);
      }
    };
    
    recognizer.canceled = (s, e) => {
      if (e.reason === sdk.CancellationReason.Error) {
        console.log(chalk.red(`\n❌ ERROR: ${e.errorDetails}`));
      }
      
      console.log(chalk.yellow("\n📞 Call ended"));
      recognizer.stopContinuousRecognitionAsync();
      resolve();
    };
    
    recognizer.sessionStopped = (s, e) => {
      console.log(chalk.yellow("\n📞 Call session ended"));
      recognizer.stopContinuousRecognitionAsync();
      resolve();
    };
    
    // Start continuous recognition
    console.log(chalk.green.bold("\nListening... Speak as if you're on a call with Woodgrove Bank 🎤"));
    console.log(chalk.gray("(Say 'end call' to finish the simulation)"));
    
    recognizer.startContinuousRecognitionAsync(
      () => {
        // Successfully started
      },
      (err) => {
        console.log(chalk.red(`\n❌ ERROR starting recognition: ${err}`));
        reject(err);
      }
    );
  });
}

/**
 * Recognizes speech from an audio file
 * @param {string} audioFilePath - Path to the audio file
 */
async function recognizeSpeechFromFile(audioFilePath) {
  return new Promise((resolve, reject) => {
    // Configure speech recognition with Azure AI Speech service
    const speechConfig = sdk.SpeechConfig.fromSubscription(speechKey, speechRegion);
    speechConfig.speechRecognitionLanguage = "en-US";
    
    console.log(chalk.yellow(`\n🔊 Recognizing speech from file: ${audioFilePath}`));
    
    // Create audio config from the audio file
    const audioConfig = sdk.AudioConfig.fromWavFileInput(audioFilePath);
    
    // Create speech recognizer
    const recognizer = new sdk.SpeechRecognizer(speechConfig, audioConfig);
    
    console.log(chalk.gray("Processing audio file..."));
    
    // Start speech recognition
    recognizer.recognizeOnceAsync(
      (result) => {
        // Process speech recognition result
        if (result.reason === sdk.ResultReason.RecognizedSpeech) {
          console.log(chalk.green.bold("\n✅ Speech recognized from file:"));
          console.log(`  ${chalk.white.bold(result.text)}`);
          
          // Bank-specific response simulation
          simulateBankResponse(result.text);
        } 
        else if (result.reason === sdk.ResultReason.NoMatch) {
          console.log(chalk.red("\n❌ No speech could be recognized in the audio file."));
        } 
        else if (result.reason === sdk.ResultReason.Canceled) {
          const cancellation = sdk.CancellationDetails.fromResult(result);
          console.log(chalk.red(`\n❌ Speech recognition canceled: ${cancellation.reason}`));
          
          if (cancellation.reason === sdk.CancellationReason.Error) {
            console.log(chalk.red(`  Error details: ${cancellation.errorDetails}`));
          }
        }
        
        // Clean up resources
        recognizer.close();
        resolve(result);
      },
      (err) => {
        console.log(chalk.red(`\n❌ ERROR: ${err}`));
        recognizer.close();
        reject(err);
      }
    );
  });
}

/**
 * Simulates a banking response based on recognized text
 * @param {string} text - The recognized speech text
 */
function simulateBankResponse(text) {
  console.log(chalk.blue.bold("\n🏦 Woodgrove Bank Assistant:"));
  
  const lowerText = text.toLowerCase();
  
  // Check for common banking queries and provide appropriate responses
  if (lowerText.includes("balance") || lowerText.includes("account balance")) {
    console.log(chalk.blue("  Your current account balance is $4,325.67. Your available credit is $12,500."));
    console.log(chalk.blue("  Your last transaction was a deposit of $1,250.00 on August 15th."));
  }
  else if (lowerText.includes("transfer") || lowerText.includes("move money")) {
    console.log(chalk.blue("  I can help you transfer funds between your accounts."));
    console.log(chalk.blue("  You currently have a checking account ending in 4321 and a savings account ending in 8765."));
    console.log(chalk.blue("  How much would you like to transfer?"));
  }
  else if (lowerText.includes("lost") || lowerText.includes("stolen") || lowerText.includes("card")) {
    console.log(chalk.blue("  I'm sorry to hear about your card issue. I've placed a hold on your card ending in 4321."));
    console.log(chalk.blue("  A new card will be mailed to your address on file within 3-5 business days."));
    console.log(chalk.blue("  For security, please verify your identity with the last 4 digits of your SSN."));
  }
  else if (lowerText.includes("mortgage") || lowerText.includes("loan") || lowerText.includes("rate")) {
    console.log(chalk.blue("  Our current mortgage rates are as follows:"));
    console.log(chalk.blue("  • 30-year fixed: 3.85%"));
    console.log(chalk.blue("  • 15-year fixed: 3.05%"));
    console.log(chalk.blue("  • 5/1 ARM: 2.75%"));
    console.log(chalk.blue("  Would you like to speak with a mortgage specialist?"));
  }
  else if (lowerText.includes("fraud") || lowerText.includes("suspicious") || lowerText.includes("unauthorized")) {
    console.log(chalk.red("  ⚠️ I understand your concern about potential fraud. This is a priority for us."));
    console.log(chalk.blue("  I've flagged your account for our fraud department to review."));
    console.log(chalk.blue("  They will contact you within 24 hours. Is there a preferred contact method?"));
  }
  else if (lowerText.includes("password") || lowerText.includes("login") || lowerText.includes("reset")) {
    console.log(chalk.blue("  For security reasons, I cannot reset your password over this call."));
    console.log(chalk.blue("  Please visit our secure website at woodgrove.com/reset or use our mobile app."));
    console.log(chalk.blue("  You'll need your account number and the last 4 digits of your SSN."));
  }
  else {
    console.log(chalk.blue("  Thank you for contacting Woodgrove Bank customer service."));
    console.log(chalk.blue("  How else can I assist you with your banking needs today?"));
  }
  
  // Educational note about the AI service
  console.log(chalk.gray("\n  💡 This response was triggered based on key terms identified in your spoken text."));
  console.log(chalk.gray("     In a real banking system, this would be integrated with account data and security verification."));
}

/**
 * Simulates language-based call routing
 * @param {string} language - The detected language code
 */
function simulateLanguageRouting(language) {
  console.log(chalk.blue.bold("\n🏦 Woodgrove Bank Language Routing:"));
  
  switch (language) {
    case "en-US":
      console.log(chalk.blue("  Routing to English-speaking customer service team."));
      console.log(chalk.blue("  Thank you for calling Woodgrove Bank. How may we assist you today?"));
      break;
    case "es-ES":
      console.log(chalk.blue("  Redirigiendo al equipo de servicio al cliente de habla española."));
      console.log(chalk.blue("  Gracias por llamar a Woodgrove Bank. ¿Cómo podemos ayudarle hoy?"));
      break;
    case "fr-FR":
      console.log(chalk.blue("  Acheminement vers l'équipe du service client francophone."));
      console.log(chalk.blue("  Merci d'avoir appelé Woodgrove Bank. Comment pouvons-nous vous aider aujourd'hui?"));
      break;
    case "de-DE":
      console.log(chalk.blue("  Weiterleitung an das deutschsprachige Kundendienstteam."));
      console.log(chalk.blue("  Vielen Dank für Ihren Anruf bei der Woodgrove Bank. Wie können wir Ihnen heute helfen?"));
      break;
    case "zh-CN":
      console.log(chalk.blue("  正在转接至中文客户服务团队。"));
      console.log(chalk.blue("  感谢您致电Woodgrove银行。我们今天能为您提供什么帮助？"));
      break;
    default:
      console.log(chalk.yellow("  Unable to confidently determine language. Routing to multilingual team."));
      console.log(chalk.blue("  Thank you for calling Woodgrove Bank. Please hold while we connect you with an appropriate agent."));
  }
  
  // Educational note about the AI service
  console.log(chalk.gray("\n  💡 Azure AI Speech can identify over 100 languages and variants from speech input."));
  console.log(chalk.gray("     This enables organizations to provide a personalized experience from the first interaction."));
}

/**
 * Processes multiple audio files in batch mode
 */
async function processBatchAudioFiles() {
  console.log(chalk.yellow.bold("\n📊 Batch Processing Sample Audio Files"));
  console.log(chalk.gray("This simulates an enterprise scenario where multiple customer calls are processed together"));
  
  // Create progress tracker
  console.log(chalk.cyan("\nProcessing files:"));
  
  const results = [];
  
  // Process each file
  for (let i = 0; i < sampleAudioFiles.length; i++) {
    const file = sampleAudioFiles[i];
    console.log(chalk.cyan(`\n[${i+1}/${sampleAudioFiles.length}] Processing: ${file.name}`));
    
    try {
      // Configure speech recognition
      const speechConfig = sdk.SpeechConfig.fromSubscription(speechKey, speechRegion);
      speechConfig.speechRecognitionLanguage = "en-US";
      
      // Create audio config from the audio file
      const audioConfig = sdk.AudioConfig.fromWavFileInput(file.path);
      
      // Create speech recognizer
      const recognizer = new sdk.SpeechRecognizer(speechConfig, audioConfig);
      
      // Process the file
      const result = await new Promise((resolve, reject) => {
        recognizer.recognizeOnceAsync(
          (result) => {
            recognizer.close();
            resolve(result);
          },
          (err) => {
            recognizer.close();
            reject(err);
          }
        );
      });
      
      // Handle the result
      if (result.reason === sdk.ResultReason.RecognizedSpeech) {
        results.push({
          filename: file.name,
          recognized: true,
          text: result.text,
          errorDetails: null
        });
      } else if (result.reason === sdk.ResultReason.Canceled) {
        const cancellation = sdk.CancellationDetails.fromResult(result);
        results.push({
          filename: file.name,
          recognized: false,
          text: null,
          errorDetails: cancellation.errorDetails || "Recognition canceled"
        });
      } else {
        results.push({
          filename: file.name,
          recognized: false,
          text: null,
          errorDetails: "No speech recognized"
        });
      }
    } catch (error) {
      results.push({
        filename: file.name,
        recognized: false,
        text: null,
        errorDetails: error.message
      });
    }
  }
  
  // Display batch processing results in a table format
  console.log(chalk.yellow.bold("\n🔍 Batch Processing Results:"));
  console.log(chalk.cyan("──────────────────────────────────────────────────────────────────────────────"));
  console.log(chalk.cyan("│ File                     │ Status       │ Content                          │"));
  console.log(chalk.cyan("──────────────────────────────────────────────────────────────────────────────"));
  
  results.forEach(result => {
    const status = result.recognized 
      ? chalk.green("✓ Success") 
      : chalk.red("✗ Failed");
    
    const content = result.recognized
      ? result.text.substring(0, 30) + (result.text.length > 30 ? "..." : "")
      : result.errorDetails;
    
    console.log(`│ ${result.filename.padEnd(25)} │ ${status.padEnd(12)} │ ${content.padEnd(35)} │`);
  });
  
  console.log(chalk.cyan("──────────────────────────────────────────────────────────────────────────────"));
  
  // Educational note on enterprise batch processing
  console.log(chalk.gray("\n💡 In enterprise settings, batch processing can be used to:"));
  console.log(chalk.gray("  • Process recorded call center conversations for quality assurance"));
  console.log(chalk.gray("  • Analyze customer interactions for compliance monitoring"));
  console.log(chalk.gray("  • Generate transcriptions for multiple files without manual intervention"));
  console.log(chalk.gray("  • Create searchable archives of voice communications"));
  
  // Detailed analysis of each recognized file
  console.log(chalk.yellow.bold("\n📝 Detailed Analysis:"));
  
  for (const result of results) {
    if (result.recognized) {
      console.log(chalk.cyan(`\nFile: ${result.filename}`));
      console.log(chalk.white.bold(`Text: "${result.text}"`));
      
      // Simple analysis (in a real system, this would use Azure AI Language for intent detection)
      const text = result.text.toLowerCase();
      
      // Banking-specific terms detection
      const bankingTerms = [
        "account", "balance", "transfer", "deposit", "withdrawal", "loan", 
        "mortgage", "credit", "debit", "card", "bank", "money", "payment",
        "transaction", "interest", "fraud", "suspicious"
      ];
      
      const foundTerms = bankingTerms.filter(term => text.includes(term));
      
      if (foundTerms.length > 0) {
        console.log(chalk.magenta("Banking terms detected: ") + 
          chalk.white(foundTerms.join(", ")));
        
        // Simulate basic intent detection
        if (text.includes("balance")) {
          console.log(chalk.yellow("Likely intent: ") + chalk.white("Account Balance Inquiry"));
        } else if (text.includes("transfer")) {
          console.log(chalk.yellow("Likely intent: ") + chalk.white("Funds Transfer"));
        } else if (text.includes("fraud") || text.includes("suspicious")) {
          console.log(chalk.yellow("Likely intent: ") + chalk.white("Fraud Report - HIGH PRIORITY"));
        } else if (text.includes("mortgage") || text.includes("loan")) {
          console.log(chalk.yellow("Likely intent: ") + chalk.white("Loan/Mortgage Inquiry"));
        }
      } else {
        console.log(chalk.gray("No specific banking terms detected."));
      }
      
      // Simulate sentiment analysis
      // This is simplified - in a real app, you'd use Azure AI Language for this
      const positiveWords = ["thank", "good", "great", "excellent", "appreciate", "happy", "help"];
      const negativeWords = ["problem", "issue", "wrong", "bad", "terrible", "unhappy", "disappointed"];
      
      const positiveCount = positiveWords.filter(word => text.includes(word)).length;
      const negativeCount = negativeWords.filter(word => text.includes(word)).length;
      
      if (positiveCount > negativeCount) {
        console.log(chalk.green("Sentiment: Positive"));
      } else if (negativeCount > positiveCount) {
        console.log(chalk.red("Sentiment: Negative"));
      } else {
        console.log(chalk.blue("Sentiment: Neutral"));
      }
    }
  }
  
  console.log(chalk.cyan("\n📊 Summary: ") + 
    chalk.green(`${results.filter(r => r.recognized).length} successful`) + " / " + 
    chalk.red(`${results.filter(r => !r.recognized).length} failed`) + " transcriptions");
}

/**
 * Displays the main menu and handles user choices
 */
async function showMenu() {
  console.log(chalk.cyan.bold("\n===== Woodgrove Bank: Azure AI Speech Service Demo ====="));
  console.log(chalk.cyan("This demo showcases how Woodgrove Bank could use Azure AI Speech Service"));
  console.log(chalk.cyan("to enhance customer service experiences through speech recognition."));
  
  console.log(chalk.yellow.bold("\nChoose a demo option:"));
  console.log("1: Basic Speech-to-Text (speak a banking command)");
  console.log("2: Language Identification (speak in any supported language)");
  console.log("3: Simulate Banking Customer Service Call (continuous recognition)");
  console.log("4: Transcribe Sample Audio File (no microphone needed)");
  console.log("5: Batch Process Audio Files (enterprise scenario)");
  console.log("6: Exit");
  
  const answer = await new Promise((resolve) => {
    rl.question(chalk.green("Enter your choice (1-6): "), (choice) => {
      resolve(choice.trim());
    });
  });
  
  switch (answer) {
    case "1":
      try {
        await recognizeSpeechOnce();
      } catch (error) {
        console.error(chalk.red(`Error in speech recognition: ${error}`));
      }
      return showMenu();
    
    case "2":
      try {
        await identifySpokenLanguage();
      } catch (error) {
        console.error(chalk.red(`Error in language identification: ${error}`));
      }
      return showMenu();
    
    case "3":
      try {
        await simulateBankingCall();
      } catch (error) {
        console.error(chalk.red(`Error in banking call simulation: ${error}`));
      }
      return showMenu();
    
    case "4":
      // Show sample audio files menu
      console.log(chalk.yellow.bold("\nSample Audio Files:"));
      sampleAudioFiles.forEach((file, index) => {
        console.log(`${index + 1}: ${file.name} - ${file.description}`);
      });
      console.log(`${sampleAudioFiles.length + 1}: Back to main menu`);
      
      const fileChoice = await new Promise((resolve) => {
        rl.question(chalk.green(`Enter your choice (1-${sampleAudioFiles.length + 1}): `), (choice) => {
          resolve(choice.trim());
        });
      });
      
      const fileIndex = parseInt(fileChoice) - 1;
      
      if (fileIndex >= 0 && fileIndex < sampleAudioFiles.length) {
        try {
          await recognizeSpeechFromFile(sampleAudioFiles[fileIndex].path);
        } catch (error) {
          console.error(chalk.red(`Error in file speech recognition: ${error}`));
        }
      }
      
      return showMenu();
      
    case "5":
      try {
        await processBatchAudioFiles();
      } catch (error) {
        console.error(chalk.red(`Error in batch processing: ${error}`));
      }
      return showMenu();
    
    case "6":
      console.log(chalk.green.bold("\nThank you for using the Woodgrove Bank Azure AI Speech demo!"));
      console.log(chalk.green("Exiting program..."));
      rl.close();
      process.exit(0);
    
    default:
      console.log(chalk.red("\nInvalid choice. Please try again."));
      return showMenu();
  }
}

/**
 * Main program entry point
 */
async function main() {
  // Check if Speech key is configured
  if (speechKey === "YOUR_SPEECH_KEY") {
    console.log(chalk.red.bold("\n⚠️ ERROR: Speech key not configured!"));
    console.log(chalk.yellow("Please set your Azure AI Speech key in the .env file:"));
    console.log(chalk.cyan("SPEECH_KEY=your_speech_key_here"));
    console.log(chalk.cyan("SPEECH_REGION=your_region_here (e.g., eastus)"));
    
    console.log(chalk.yellow("\nTo create an Azure AI Speech resource:"));
    console.log(chalk.gray("1. Go to https://portal.azure.com/#create/Microsoft.CognitiveServicesSpeechServices"));
    console.log(chalk.gray("2. Create a new Speech service (S0 tier)"));
    console.log(chalk.gray("3. Copy the key and region to your .env file"));
    
    rl.close();
    process.exit(1);
  }
  
  // Display educational info about the service
  console.log(chalk.magenta.bold("\n===== Azure AI Speech Service Educational Context ====="));
  console.log(chalk.magenta("Azure AI Speech is a cloud-based service that provides speech processing capabilities:"));
  console.log(chalk.gray("• Speech-to-Text: Converts spoken language to text in real-time"));
  console.log(chalk.gray("• Text-to-Speech: Creates natural-sounding synthesized speech"));
  console.log(chalk.gray("• Speech Translation: Translates speech across 60+ languages"));
  console.log(chalk.gray("• Speaker Recognition: Identifies unique speakers in conversations"));
  console.log(chalk.gray("• Language Identification: Detects language being spoken"));
  
  console.log(chalk.magenta("\nBanking Use Cases:"));
  console.log(chalk.gray("• Customer authentication via voice biometrics"));
  console.log(chalk.gray("• Voice-controlled banking transactions"));
  console.log(chalk.gray("• Multilingual customer support"));
  console.log(chalk.gray("• Call center transcription and analysis"));
  
  console.log(chalk.magenta("\nExam Topic Focus Areas (AI-102):"));
  console.log(chalk.gray("• Creating/configuring Speech resources in Azure"));
  console.log(chalk.gray("• Speech SDK implementation in applications"));
  console.log(chalk.gray("• Continuous vs. one-time recognition patterns"));
  console.log(chalk.gray("• Language detection capabilities"));
  console.log(chalk.gray("• Recognition accuracy and performance factors"));
  
  // Start the demo menu
  await showMenu();
}

// Execute the main function
main().catch((error) => {
  console.error(chalk.red(`Unhandled error: ${error}`));
  process.exit(1);
}); 