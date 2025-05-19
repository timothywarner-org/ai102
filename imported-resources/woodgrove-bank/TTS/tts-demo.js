/**
 * Azure AI Speech Service Text-to-Speech (TTS) Demo
 * 
 * This script demonstrates how to use the Azure AI Speech Service to convert text to speech.
 * It uses the Azure Speech SDK and supports managed identity or environment variables for secure authentication.
 * 
 * Prerequisites:
 * - Set the following environment variables:
 *   - AZURE_REGION: The Azure region of your Speech Service.
 * 
 * Usage:
 * - Run this script using Node.js to synthesize speech from text and save it as an audio file.
 * - The synthesized audio will be saved to the specified output file.
 * 
 * Author: Tim Warner (TechTrainerTim.com)
 * License: MIT License
 * Date: May 14, 2025
 */

const sdk = require('microsoft-cognitiveservices-speech-sdk');
const fs = require('fs');
const { DefaultAzureCredential } = require('@azure/identity');

// Function to fetch an access token using Azure Identity
async function getAccessToken() {
    try {
        const credential = new DefaultAzureCredential();
        return await credential.getToken("https://cognitiveservices.azure.com/.default");
    } catch (error) {
        console.error("Failed to fetch access token:", error);
        throw error;
    }
}

// Function to configure the Speech SDK
function configureSpeechSDK(token, region) {
    try {
        const speechConfig = sdk.SpeechConfig.fromAuthorizationToken(token, region);
        speechConfig.speechSynthesisVoiceName = "en-US-JennyNeural"; // Set the voice and language
        return speechConfig;
    } catch (error) {
        console.error("Failed to configure Speech SDK:", error);
        throw error;
    }
}

// Function to perform text-to-speech synthesis
function synthesizeText(synthesizer, text, outputFile) {
    synthesizer.speakTextAsync(
        text,
        result => {
            if (result.reason === sdk.ResultReason.SynthesizingAudioCompleted) {
                console.log(`Audio synthesized to file: ${outputFile}`);
            } else {
                console.error("Speech synthesis failed:", result.errorDetails);
            }
            synthesizer.close();
        },
        error => {
            console.error("Error during synthesis:", error);
            synthesizer.close();
        }
    );
}

// Function to perform SSML-based synthesis
function synthesizeSSML(synthesizer, ssmlText) {
    synthesizer.speakSsmlAsync(
        ssmlText,
        result => {
            if (result.reason === sdk.ResultReason.SynthesizingAudioCompleted) {
                console.log("SSML-based audio synthesized successfully.");
            } else {
                console.error("SSML synthesis failed:", result.errorDetails);
            }
            synthesizer.close();
        },
        error => {
            console.error("Error during SSML synthesis:", error);
            synthesizer.close();
        }
    );
}

// Main function to execute the script
(async function main() {
    try {
        // Fetch access token
        const tokenResponse = await getAccessToken();

        // Configure Speech SDK
        const speechConfig = configureSpeechSDK(tokenResponse.token, process.env.AZURE_REGION);

        // Create a synthesizer
        const audioFile = "welcome-audio.wav";
        const audioConfig = sdk.AudioConfig.fromAudioFileOutput(audioFile);
        const synthesizer = new sdk.SpeechSynthesizer(speechConfig, audioConfig);

        // Text-to-speech synthesis
        const text = "Hello, welcome to the Azure AI Speech Service demo!";
        synthesizeText(synthesizer, text, audioFile);

        // SSML-based synthesis
        const ssmlText = `
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
          <voice name="en-US-JennyNeural">
            <prosody rate="0.9" pitch="+5Hz" volume="loud">
              Welcome to the Azure AI Speech Service demo! This is an example of using SSML for customization.
            </prosody>
            <break time="500ms"/>
            <prosody rate="1.2" pitch="-2Hz">
              You can adjust pitch, rate, and volume to create natural and engaging speech.
            </prosody>
          </voice>
        </speak>`;
        synthesizeSSML(synthesizer, ssmlText);
    } catch (error) {
        console.error("An error occurred during the execution of the script:", error);
    }
})();