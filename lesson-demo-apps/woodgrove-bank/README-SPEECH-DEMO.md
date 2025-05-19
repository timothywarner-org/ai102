# Azure AI-102 Certification - Speech Services Demo
## Lesson 11: Implement Speech-to-Text Solutions

This repository contains a comprehensive Azure AI Speech Service demo for Woodgrove Bank showcasing Speech-to-Text capabilities for the AI-102 exam. The solution demonstrates practical banking industry applications of speech recognition technology.

## Overview

The Woodgrove Bank Speech-to-Text demo includes:

1. **Console Application (speech-to-text-demo.js)**
   - Real-time speech recognition with microphone input
   - Language identification (English, Spanish, French, German, Chinese)
   - Continuous recognition for simulated banking calls
   - Banking-specific content analysis
   - Educational AI-102 exam notes throughout the code

2. **Web Application (speech-web-server.js)**
   - Browser interface for uploading audio files (MP3/WAV)
   - Processing sample files (English/Spanish banking conversations)
   - MP3 to WAV conversion (16kHz mono format required by Azure Speech SDK)
   - Language detection and banking terminology analysis
   - Interactive results display with sentiment analysis

3. **Sample Audio Files**
   - English and Spanish MP3s from the audio folder
   - Banking and healthcare WAV files in samples/audio
   - Automatic processing with appropriate language models

4. **Key Implementation Features**
   - Port management (killing processes on port 3009)
   - Proper error handling and cleanup
   - Detailed educational comments highlighting AI-102 exam concepts
   - Tabbed user interface for file uploads or sample selection
   - Banking terminology recognition and intent detection

## Technical Architecture

- **Azure AI Speech Service**: Provides the core speech recognition capabilities
- **Express.js**: Powers the web server and API endpoints
- **ffmpeg**: Handles MP3 to WAV conversion for Speech SDK compatibility
- **multer**: Manages file uploads in the web interface
- **dotenv**: Securely stores Azure service credentials

## Getting Started

### Prerequisites
- Node.js 14.x or higher
- An Azure account with Speech service enabled
- Speech service API key and region

### Configuration
1. Clone the repository
2. Install dependencies: `npm install`
3. Create a `.env` file with your Azure Speech service credentials:
   ```
   SPEECH_KEY=your_speech_key
   SPEECH_REGION=your_region
   ```

### Running the Demo
- **Console Demo**: `npm run speech-demo`
- **Web Application**: `npm run speech-web`
- **Development Mode**: `npm run speech-web:dev` (with hot reloading)

## AI-102 Exam Concepts Demonstrated

This demo illustrates several key concepts from the AI-102 exam:

- **Speech SDK Integration**: Proper configuration and initialization
- **Authentication Methods**: Subscription key-based authentication
- **Language Detection**: Identifying spoken languages in audio
- **Audio Format Requirements**: Converting to required 16kHz mono WAV
- **Recognition Patterns**: Both one-time and continuous recognition
- **Error Handling**: Proper handling of recognition errors and cancellations
- **Post-Processing**: Analyzing transcribed text for intent and sentiment

## Educational Value

The implementation is designed with educational purposes in mind:
- Detailed comments explaining Azure AI concepts
- AI-102 exam-relevant notes throughout the code
- Visual highlighting of educational points in the UI
- Practical banking industry use case demonstration

## Banking-Specific Features

- Detection of banking terminology
- Intent classification for common banking queries
- Simulated customer service responses
- Multi-language support for diverse customer needs
- Sentiment analysis of customer interactions

## Learn More

For more information, visit:
- [Azure AI Speech Service Documentation](https://learn.microsoft.com/azure/ai-services/speech-service/)
- [Speech-to-Text Documentation](https://learn.microsoft.com/azure/ai-services/speech-service/speech-to-text)
- [Azure AI-102 Certification](https://learn.microsoft.com/certifications/exams/ai-102/)

## Author

Tim Warner - Microsoft Press AI-102 Course 