# Azure AI Speech Service Text-to-Speech (TTS) Demo

**Part of Tim Warner's Microsoft Press video training course "Exam AI-102: Designing and Implementing a Microsoft Azure AI Solution"**

**Lesson 12: Deploy Text-to-Speech Solutions**

## Overview

This script demonstrates how to use the Azure AI Speech Service to convert text to speech (TTS). It showcases two approaches:

1. **Plain Text-to-Speech**: Converts plain text into audio.

2. **SSML-based Speech Synthesis**: Uses Speech Synthesis Markup Language (SSML) for advanced customization, such as adjusting pitch, rate, volume, and adding pauses.

The script is designed to align with the objectives of the AI-102 certification and the Azure AI Engineer job role by demonstrating:

- Integration with Azure Cognitive Services.

- Secure authentication using managed identity.

- Advanced speech synthesis techniques with SSML.

- Modular and maintainable code structure.

## Prerequisites

1. **Azure Speech Service**: Ensure you have an Azure Speech Service resource created in your Azure subscription.

2. **Environment Variables**:

   - `AZURE_REGION`: The Azure region of your Speech Service (e.g., `eastus`).

3. **Node.js**: Install Node.js from [Node.js official website](https://nodejs.org/).

4. **Dependencies**: Install the required Node.js packages:

   ```bash
   npm install microsoft-cognitiveservices-speech-sdk @azure/identity
   ```

## How the Code Works

### Authentication

The script uses the Azure Identity library to fetch an access token for a managed identity. This token is passed to the Azure Speech SDK for secure authentication. This approach avoids hardcoding credentials and aligns with Azure best practices.

### Speech Synthesis

1. **Plain Text-to-Speech**:

   - Converts a simple text string into an audio file.

   - Demonstrates basic usage of the Azure Speech SDK.

2. **SSML-based Speech Synthesis**:

   - Uses SSML to customize the speech output.

   - Adjusts parameters like pitch, rate, and volume for a more natural and engaging speech experience.

### Modular Structure

The script is divided into functions for better readability and maintainability:

- `getAccessToken()`: Fetches an access token using Azure Identity.

- `configureSpeechSDK()`: Configures the Azure Speech SDK with the access token and region.

- `synthesizeText()`: Performs plain text-to-speech synthesis.

- `synthesizeSSML()`: Performs SSML-based speech synthesis.

### Error Handling

The script includes robust error handling for all asynchronous operations, ensuring that issues are logged and handled gracefully.

## How It Supports AI-102 and the Azure AI Engineer Role

1. **AI-102 Certification Objectives**:

   - Demonstrates integration with Azure Cognitive Services.

   - Implements secure authentication using managed identity.

   - Showcases advanced speech synthesis techniques with SSML.

2. **Azure AI Engineer Job Role**:

   - Highlights best practices for working with Azure Cognitive Services.

   - Emphasizes secure and maintainable code design.

   - Demonstrates the ability to customize and optimize AI solutions for real-world applications.

## Running the Script

1. Navigate to the `TTS` folder:

   ```bash
   cd TTS
   ```

2. Run the script:

   ```bash
   node tts-demo.js
   ```

3. Verify the output:

   - The plain text-to-speech audio will be saved as `welcome-audio.wav`.

   - The SSML-based audio will also be synthesized and logged in the console.

## Troubleshooting

- Ensure the environment variables are correctly set.

- Verify that the managed identity has the necessary permissions to access the Azure Speech Service.

- Check for any errors in the console output and address them as needed.

## Additional Resources

- [Azure Speech Service Documentation](https://learn.microsoft.com/azure/cognitive-services/speech-service/)

- [AI-102 Certification Guide](https://learn.microsoft.com/certifications/exams/ai-102)

- [Azure AI Engineer Job Role Overview](https://learn.microsoft.com/azure/architecture/roles/ai-engineer/)
