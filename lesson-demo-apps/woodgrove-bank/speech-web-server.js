/**
 * @file speech-web-server.js
 * @description Woodgrove Bank Speech-to-Text Web Server
 * 
 * This Express server provides a web interface for uploading audio files (MP3/WAV)
 * and transcribing them using Azure AI Speech Service. It demonstrates:
 * 
 * 1. MP3 to WAV conversion for Speech SDK compatibility
 * 2. File upload handling with multer
 * 3. Azure AI Speech SDK integration for transcription
 * 4. Simple banking-specific content analysis
 * 
 * KEY AZURE AI-102 EXAM CONCEPTS DEMONSTRATED:
 * ----------------------------------
 * - Azure AI Speech resource configuration and authentication
 * - Speech-to-Text API usage patterns and best practices
 * - Language detection and multilingual support
 * - Audio format requirements and preprocessing 
 * - Batch vs. real-time transcription approaches
 * - Integration patterns with other Azure AI services
 * 
 * @author Tim Warner - Microsoft Press AI-102 Course
 */

// Required dependencies
const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const { promisify } = require('util');
const ffmpeg = require('fluent-ffmpeg');
const ffmpegPath = require('ffmpeg-static');
const sdk = require('microsoft-cognitiveservices-speech-sdk');
const dotenv = require('dotenv');
const chalk = require('chalk');
const { exec } = require('child_process');

// Set ffmpeg path
ffmpeg.setFfmpegPath(ffmpegPath);

// Load environment variables
dotenv.config();

// Azure AI Speech service configuration
const speechKey = process.env.SPEECH_KEY || "YOUR_SPEECH_KEY";
const speechRegion = process.env.SPEECH_REGION || "eastus";

// Check if Speech key is configured
if (speechKey === "YOUR_SPEECH_KEY") {
  console.error(chalk.red.bold("\n⚠️ ERROR: Speech key not configured!"));
  console.error(chalk.yellow("Please set your Azure AI Speech key in the .env file:"));
  console.error(chalk.cyan("SPEECH_KEY=your_speech_key_here"));
  console.error(chalk.cyan("SPEECH_REGION=your_region_here (e.g., eastus)"));
  process.exit(1);
}

// Create Express app
const app = express();
const port = process.env.PORT || 3009;

// Kill any existing process on the same port (idempotent startup)
function killProcessOnPort(port) {
  return new Promise((resolve) => {
    // Different commands for Windows vs Unix-like
    const command = process.platform === 'win32'
      ? `FOR /F "tokens=5" %P IN ('netstat -ano ^| findstr :${port} ^| findstr LISTENING') DO (taskkill /F /PID %P)`
      : `lsof -i :${port} | grep LISTEN | awk '{print $2}' | xargs -r kill -9`;
    
    exec(command, (error) => {
      // Ignore errors, as they likely mean no process was running
      resolve();
    });
  });
}

// Set up storage for uploaded files
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, 'public/uploads/');
  },
  filename: (req, file, cb) => {
    // Generate unique filename with original extension
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    const ext = path.extname(file.originalname);
    cb(null, uniqueSuffix + ext);
  }
});

// File filter to only accept WAV and MP3 files
const fileFilter = (req, file, cb) => {
  if (file.mimetype === 'audio/wav' || file.mimetype === 'audio/mpeg') {
    cb(null, true);
  } else {
    cb(new Error('Only WAV and MP3 files are allowed'), false);
  }
};

// Configure multer
const upload = multer({ 
  storage: storage,
  limits: { fileSize: 10 * 1024 * 1024 }, // 10MB max file size
  fileFilter: fileFilter
});

// Serve static files
app.use(express.static('public'));

// Woodgrove Bank branding middleware
app.use((req, res, next) => {
  // Add Woodgrove Bank branding to all responses
  res.setHeader('X-Powered-By', 'Woodgrove Bank AI Services');
  next();
});

// Sample files for quick testing
const sampleFiles = [
  {
    name: "English Banking Conversation",
    path: "audio/english.mp3",
    language: "en-US",
    description: "Sample English banking conversation for testing Speech-to-Text capabilities",
    examTopics: ["Language detection", "Intent recognition", "Banking terminology extraction"]
  },
  {
    name: "Spanish Banking Conversation",
    path: "audio/spanish.mp3",
    language: "es-ES",
    description: "Sample Spanish banking conversation for testing multilingual capabilities",
    examTopics: ["Multilingual support", "Cross-language recognition", "Language-specific models"]
  }
];

// Banking-specific terms for analysis (AI-102 relevant - showing domain adaptation)
const bankingTerms = [
  "account", "balance", "transfer", "deposit", "withdrawal", "loan", 
  "mortgage", "credit", "debit", "card", "bank", "money", "payment",
  "transaction", "interest", "fraud", "suspicious"
];

// Home page route - render HTML interface
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Sample files listing endpoint
app.get('/api/samples', (req, res) => {
  res.json(sampleFiles);
});

// AI-102 exam topics endpoint (educational)
app.get('/api/exam-topics', (req, res) => {
  const examTopics = {
    speechService: [
      {
        topic: "Authentication Methods",
        description: "Different ways to authenticate with Azure AI Speech (subscription keys, tokens, managed identities)",
        docsUrl: "https://learn.microsoft.com/azure/ai-services/speech-service/overview#authentication"
      },
      {
        topic: "Audio Format Requirements",
        description: "Supported audio formats, sampling rates, and channels for optimal recognition",
        docsUrl: "https://learn.microsoft.com/azure/ai-services/speech-service/how-to-use-codec-compressed-audio-input-streams"
      },
      {
        topic: "Language Detection",
        description: "Automatically identify spoken languages in audio content",
        docsUrl: "https://learn.microsoft.com/azure/ai-services/speech-service/language-identification"
      },
      {
        topic: "Batch Transcription",
        description: "Transcribe large volumes of audio asynchronously",
        docsUrl: "https://learn.microsoft.com/azure/ai-services/speech-service/batch-transcription"
      },
      {
        topic: "Real-time Transcription",
        description: "Convert speech to text in real-time from microphones or streaming sources",
        docsUrl: "https://learn.microsoft.com/azure/ai-services/speech-service/get-started-speech-to-text"
      }
    ]
  };
  
  res.json(examTopics);
});

// Process sample file endpoint
app.get('/api/process-sample/:index', async (req, res) => {
  try {
    const index = parseInt(req.params.index);
    
    if (isNaN(index) || index < 0 || index >= sampleFiles.length) {
      return res.status(400).json({ error: 'Invalid sample file index' });
    }
    
    const file = sampleFiles[index];
    const filePath = path.join(__dirname, file.path);
    
    // Check if file exists
    if (!fs.existsSync(filePath)) {
      return res.status(404).json({ error: 'Sample file not found' });
    }
    
    const startTime = Date.now();
    
    // Process the audio file
    let wavFilePath = filePath;
    
    // For educational purposes - log the process steps
    console.log(chalk.cyan("AI-102 Process Flow:"));
    console.log(chalk.cyan("1. Validating audio file format"));
    
    // Convert MP3 to WAV if needed (educational - explaining why)
    if (path.extname(filePath).toLowerCase() === '.mp3') {
      console.log(chalk.cyan("2. Converting MP3 to WAV (Azure Speech SDK requires WAV format)"));
      wavFilePath = path.join(__dirname, 'public/uploads', path.basename(filePath, '.mp3') + '.wav');
      await convertMP3ToWAV(filePath, wavFilePath);
    } else {
      console.log(chalk.cyan("2. File is already in WAV format, proceeding directly"));
    }
    
    // Explain the recognition process
    console.log(chalk.cyan(`3. Initializing Azure AI Speech recognizer with language: ${file.language}`));
    console.log(chalk.cyan("4. Sending audio data to Azure AI Speech service"));
    
    // Recognize speech from the file
    const result = await recognizeSpeechFromFile(wavFilePath, file.language);
    
    console.log(chalk.cyan("5. Processing recognition results"));
    
    // Calculate processing time
    const processingTime = Date.now() - startTime;
    
    // Analyze the text for banking terms and intent
    const analysis = analyzeText(result.text);
    
    console.log(chalk.cyan("6. Performing post-processing analysis (banking terms, intent)"));
    
    // Clean up temporary WAV file if it was converted
    if (path.extname(filePath).toLowerCase() === '.mp3' && fs.existsSync(wavFilePath)) {
      fs.unlinkSync(wavFilePath);
      console.log(chalk.cyan("7. Cleaning up temporary files"));
    }
    
    // Return the results with educational context for AI-102
    return res.json({
      filename: file.name,
      text: result.text,
      language: file.language,
      bankingTerms: analysis.bankingTerms,
      intent: analysis.intent,
      sentiment: analysis.sentiment,
      processingTime,
      examTopics: file.examTopics,
      educationalNotes: [
        "The Azure AI Speech SDK requires explicit language specifications for optimal accuracy",
        "Converting MP3 to WAV format with 16kHz sample rate improves recognition quality",
        "Speech recognition can be combined with text analytics for comprehensive understanding",
        "In enterprise scenarios, this would integrate with custom speech models for domain-specific vocabulary"
      ]
    });
  } catch (error) {
    console.error('Error processing sample file:', error);
    return res.status(500).json({ error: error.message });
  }
});

// File upload endpoint
app.post('/upload', upload.single('audioFile'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }
    
    const uploadedFile = req.file;
    const startTime = Date.now();
    
    console.log(chalk.cyan(`Processing uploaded file: ${uploadedFile.originalname}`));
    
    // Log AI-102 relevant process steps
    console.log(chalk.cyan("\nAI-102: Demonstrating Speech-to-Text Workflow"));
    console.log(chalk.cyan("1. File received: validating mime type and size"));
    
    // Prepare for speech recognition
    let wavFilePath = uploadedFile.path;
    
    // Convert MP3 to WAV if needed (showing format requirements for exam)
    if (path.extname(uploadedFile.originalname).toLowerCase() === '.mp3') {
      console.log(chalk.cyan("2. Converting MP3 to WAV with 16kHz mono format (Azure Speech requirement)"));
      wavFilePath = path.join(
        path.dirname(uploadedFile.path),
        path.basename(uploadedFile.path, path.extname(uploadedFile.path)) + '.wav'
      );
      await convertMP3ToWAV(uploadedFile.path, wavFilePath);
    } else {
      console.log(chalk.cyan("2. File is already in WAV format, proceeding directly"));
    }
    
    // Detect language (showing language detection capabilities for exam)
    let language = "en-US"; // Default language
    
    if (uploadedFile.originalname.toLowerCase().includes('spanish') || 
        uploadedFile.originalname.toLowerCase().includes('español')) {
      language = "es-ES";
      console.log(chalk.cyan("3. Language detection: Spanish content identified from filename"));
    } else {
      console.log(chalk.cyan("3. Language detection: Defaulting to English (en-US)"));
      // In a real app, you would use language detection API
      console.log(chalk.gray("   AI-102 Note: Production apps should use automatic language detection"));
    }
    
    console.log(chalk.cyan("4. Creating SpeechConfig with subscription key and region"));
    console.log(chalk.cyan("5. Creating AudioConfig from file input"));
    console.log(chalk.cyan("6. Starting speech recognition process"));
    
    // Recognize speech from file
    const result = await recognizeSpeechFromFile(wavFilePath, language);
    
    // Calculate processing time
    const processingTime = Date.now() - startTime;
    
    // Analyze the text for banking terms and intent
    const analysis = analyzeText(result.text);
    
    console.log(chalk.cyan("7. Post-processing: Analyzing transcribed text for banking terminology"));
    console.log(chalk.green(`Successfully processed file. Text length: ${result.text.length} chars`));
    
    // Clean up files
    try {
      if (fs.existsSync(uploadedFile.path)) {
        fs.unlinkSync(uploadedFile.path);
      }
      
      if (wavFilePath !== uploadedFile.path && fs.existsSync(wavFilePath)) {
        fs.unlinkSync(wavFilePath);
      }
      console.log(chalk.cyan("8. Cleanup: Removing temporary files"));
    } catch (cleanupError) {
      console.error('Error cleaning up files:', cleanupError);
    }
    
    // Return the results with educational context
    return res.json({
      filename: uploadedFile.originalname,
      text: result.text,
      language,
      bankingTerms: analysis.bankingTerms,
      intent: analysis.intent,
      sentiment: analysis.sentiment,
      processingTime,
      educationalNotes: [
        "Audio preprocessing improves recognition accuracy (16kHz mono WAV format)",
        "Language selection affects model choice and recognition accuracy",
        "The Speech SDK handles streaming and batch processing differently",
        "For domain-specific terminology, custom models can be trained"
      ]
    });
  } catch (error) {
    console.error('Error processing uploaded file:', error);
    return res.status(500).json({ error: error.message });
  }
});

/**
 * Converts an MP3 file to WAV format for use with the Speech SDK
 * @param {string} inputPath - Path to the MP3 file
 * @param {string} outputPath - Path to save the WAV file
 * @returns {Promise<void>}
 */
function convertMP3ToWAV(inputPath, outputPath) {
  return new Promise((resolve, reject) => {
    ffmpeg(inputPath)
      .audioFrequency(16000) // 16 kHz sample rate works best with Speech service
      .audioChannels(1) // Mono audio
      .audioCodec('pcm_s16le') // PCM signed 16-bit little-endian
      .format('wav')
      .on('end', () => {
        console.log(chalk.green(`Successfully converted ${inputPath} to WAV format`));
        console.log(chalk.gray("AI-102 Note: Azure Speech SDK requires 16kHz sampling rate and PCM format"));
        resolve();
      })
      .on('error', (err) => {
        console.error(chalk.red('Error converting audio:', err));
        reject(err);
      })
      .save(outputPath);
  });
}

/**
 * Recognizes speech from an audio file
 * @param {string} audioFilePath - Path to the audio file (WAV format)
 * @param {string} language - Language code (e.g., en-US, es-ES)
 * @returns {Promise<object>} - Recognition result
 */
function recognizeSpeechFromFile(audioFilePath, language = "en-US") {
  return new Promise((resolve, reject) => {
    try {
      // Ensure the file exists and is readable
      if (!fs.existsSync(audioFilePath)) {
        console.log(chalk.red(`File not found: ${audioFilePath}`));
        return reject(new Error(`File not found: ${audioFilePath}`));
      }

      // Configure speech recognition
      const speechConfig = sdk.SpeechConfig.fromSubscription(speechKey, speechRegion);
      speechConfig.speechRecognitionLanguage = language;
      
      // AI-102 relevant - set output format
      speechConfig.outputFormat = sdk.OutputFormat.Detailed;
      
      // Create audio config from file path rather than direct input
      // This is more reliable than using fromWavFileInput which can have issues with certain WAV files
      const audioConfig = sdk.AudioConfig.fromWavFileInput(fs.readFileSync(audioFilePath));
      
      // Create speech recognizer
      const recognizer = new sdk.SpeechRecognizer(speechConfig, audioConfig);
      
      console.log(chalk.yellow(`Starting speech recognition for ${audioFilePath}`));
      console.log(chalk.gray("AI-102 Note: This demonstrates the one-time recognition pattern"));
      
      // Start speech recognition
      recognizer.recognizeOnceAsync(
        (result) => {
          if (result.reason === sdk.ResultReason.RecognizedSpeech) {
            console.log(chalk.green('Speech recognized successfully'));
            console.log(chalk.gray(`AI-102 Note: ResultReason.RecognizedSpeech indicates successful recognition`));
            recognizer.close();
            resolve({ 
              text: result.text,
              language
            });
          } else if (result.reason === sdk.ResultReason.NoMatch) {
            console.log(chalk.red('No speech could be recognized'));
            console.log(chalk.gray(`AI-102 Note: ResultReason.NoMatch means speech wasn't recognizable`));
            recognizer.close();
            reject(new Error('No speech could be recognized'));
          } else if (result.reason === sdk.ResultReason.Canceled) {
            const cancellation = sdk.CancellationDetails.fromResult(result);
            console.log(chalk.red(`Speech recognition canceled: ${cancellation.reason}`));
            
            if (cancellation.reason === sdk.CancellationReason.Error) {
              console.log(chalk.red(`Error details: ${cancellation.errorDetails}`));
              console.log(chalk.gray(`AI-102 Note: Error code ${cancellation.ErrorCode} - check Azure status`));
            }
            
            recognizer.close();
            reject(new Error(`Recognition canceled: ${cancellation.errorDetails || cancellation.reason}`));
          }
        },
        (err) => {
          console.log(chalk.red(`ERROR: ${err}`));
          recognizer.close();
          reject(err);
        }
      );
    } catch (error) {
      console.log(chalk.red(`Exception in recognizeSpeechFromFile: ${error.message}`));
      reject(error);
    }
  });
}

/**
 * Analyzes text for banking terms and intent
 * @param {string} text - The text to analyze
 * @returns {object} - Analysis results
 */
function analyzeText(text) {
  const lowerText = text.toLowerCase();
  
  // Find banking terms in the text
  const foundTerms = bankingTerms.filter(term => lowerText.includes(term));
  
  // Simple intent detection (in a real app, would use Azure AI Language)
  let intent = null;
  
  if (lowerText.includes('balance') || lowerText.includes('how much')) {
    intent = "Account Balance Inquiry";
  } else if (lowerText.includes('transfer') || lowerText.includes('send money')) {
    intent = "Funds Transfer";
  } else if (lowerText.includes('fraud') || lowerText.includes('suspicious')) {
    intent = "Fraud Report - HIGH PRIORITY";
  } else if (lowerText.includes('mortgage') || lowerText.includes('loan')) {
    intent = "Loan/Mortgage Inquiry";
  } else if (lowerText.includes('credit') || lowerText.includes('card')) {
    intent = "Credit Card Services";
  } else if (lowerText.includes('password') || lowerText.includes('login')) {
    intent = "Online Banking Support";
  }
  
  // Simple sentiment analysis
  // This is simplified - in a real app, you'd use Azure AI Language for this
  const positiveWords = ["thank", "good", "great", "excellent", "appreciate", "happy", "help"];
  const negativeWords = ["problem", "issue", "wrong", "bad", "terrible", "unhappy", "disappointed"];
  
  const positiveCount = positiveWords.filter(word => lowerText.includes(word)).length;
  const negativeCount = negativeWords.filter(word => lowerText.includes(word)).length;
  
  let sentiment = 'Neutral';
  if (positiveCount > negativeCount) {
    sentiment = 'Positive';
  } else if (negativeCount > positiveCount) {
    sentiment = 'Negative';
  }
  
  return {
    bankingTerms: foundTerms,
    intent,
    sentiment
  };
}

// Start the server after killing any existing process on the port
killProcessOnPort(port).then(() => {
  app.listen(port, () => {
    console.log(chalk.cyan.bold("\n===== Woodgrove Bank Speech-to-Text Web Server ====="));
    console.log(chalk.cyan(`Server running at http://localhost:${port}`));
    console.log(chalk.cyan("Ready to transcribe audio files!"));
    
    console.log(chalk.yellow("\nAI-102 Teaching Tips:"));
    console.log(chalk.gray("• Show students how to access Azure Speech Service in the portal"));
    console.log(chalk.gray("• Explain the differences between real-time and batch transcription"));
    console.log(chalk.gray("• Demonstrate how different languages are supported"));
    console.log(chalk.gray("• Point out the integration possibilities with Language Understanding"));
    console.log(chalk.gray("• Discuss audio format requirements (16kHz, mono, WAV) and why they matter"));
    console.log(chalk.gray("• Highlight enterprise use cases for custom speech models"));
    
    console.log(chalk.magenta("\nPress Ctrl+C to stop the server"));
  });
}); 