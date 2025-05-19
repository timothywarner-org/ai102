import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import { OpenAIClient, AzureKeyCredential } from '@azure/openai';
import path from 'path';
import { fileURLToPath } from 'url';
import { exec } from 'child_process';
import { promisify } from 'util';
import fs from 'fs';

const execAsync = promisify(exec);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const port = process.env.PORT || 3000;

// Port killing routine
async function killPort(port) {
    try {
        const platform = process.platform;
        let command;
        
        if (platform === 'win32') {
            command = `netstat -ano | findstr :${port} | findstr LISTENING`;
            const { stdout } = await execAsync(command);
            if (stdout) {
                const pid = stdout.split(' ').filter(Boolean).pop();
                if (pid) {
                    await execAsync(`taskkill /F /PID ${pid}`);
                    console.log(`🔥 Killed process on port ${port} (PID: ${pid})`);
                }
            }
        } else {
            command = `lsof -i :${port} -t`;
            const { stdout } = await execAsync(command);
            if (stdout) {
                const pid = stdout.trim();
                await execAsync(`kill -9 ${pid}`);
                console.log(`🔥 Killed process on port ${port} (PID: ${pid})`);
            }
        }
    } catch (error) {
        if (!error.message.includes('no process found') && 
            !error.message.includes('not found')) {
            console.log(`ℹ️ No process found on port ${port}`);
        }
    }
}

// Initialize OpenAI client
function initOpenAIClient() {
    try {
        if (!process.env.AZURE_OPENAI_ENDPOINT || !process.env.AZURE_OPENAI_KEY) {
            throw new Error('Missing OpenAI credentials in .env file');
        }
        return new OpenAIClient(
            process.env.AZURE_OPENAI_ENDPOINT,
            new AzureKeyCredential(process.env.AZURE_OPENAI_KEY)
        );
    } catch (error) {
        console.error('Failed to initialize OpenAI client:', error);
        throw error;
    }
}

// Initialize server with port killing
async function startServer() {
    try {
        // Kill existing port usage
        await killPort(port);
        console.log(`🧹 Port ${port} is clear`);

        // Initialize OpenAI
        const openai = initOpenAIClient();
        console.log('✨ OpenAI client initialized');

        const app = express();

        // Middleware
        app.use(cors());
        app.use(express.json());
        
        // Serve static files - note the order matters!
        app.use('/static', express.static(path.join(__dirname, 'static')));
        app.use(express.static(path.join(__dirname, 'static')));

        // Routes
        app.get('/', (req, res) => {
            res.sendFile(path.join(__dirname, 'static', 'index.html'));
        });

        app.get('/frontend_settings', (req, res) => {
            res.json({
                auth_enabled: false,
                ui: {
                    title: process.env.UI_TITLE || 'Tim\'s Chat',
                    logo: process.env.UI_LOGO || '/static/assets/ttt-logo.png',
                    chat_logo: process.env.UI_CHAT_LOGO || process.env.UI_LOGO || '/static/assets/ttt-logo.png',
                    chat_title: process.env.UI_CHAT_TITLE || 'Learn Azure OpenAI',
                    chat_description: process.env.UI_CHAT_DESCRIPTION || 'Ask me anything about Azure OpenAI and cloud development!',
                    show_share_button: false,
                    show_chat_history_button: false
                }
            });
        });

        // Chat endpoint with streaming
        app.post('/conversation', async (req, res) => {
            try {
                const { messages } = req.body;
                console.log('📨 Received chat request:', { 
                    messageCount: messages?.length,
                    lastMessage: messages?.[messages.length - 1]
                });
                
                // Set up SSE for streaming
                res.setHeader('Content-Type', 'text/event-stream');
                res.setHeader('Cache-Control', 'no-cache');
                res.setHeader('Connection', 'keep-alive');

                // Stream the chat completion
                const stream = await openai.streamChatCompletions(
                    process.env.AZURE_OPENAI_MODEL,
                    messages,
                    { 
                        temperature: 0.7,
                        max_tokens: 800
                    }
                );

                // Send each chunk to the client
                for await (const chunk of stream) {
                    if (chunk.choices[0]?.delta?.content) {
                        res.write(`data: ${JSON.stringify({
                            choices: [{
                                delta: { content: chunk.choices[0].delta.content }
                            }]
                        })}\n\n`);
                    }
                }
                res.end();
            } catch (error) {
                console.error('❌ Chat error:', error);
                if (!res.headersSent) {
                    res.status(500).json({ 
                        error: 'Chat completion failed',
                        details: error.message 
                    });
                }
            }
        });

        // Health check
        app.get('/health', (req, res) => {
            res.json({ 
                status: 'ok', 
                time: new Date().toISOString(),
                platform: process.platform,
                node_version: process.version,
                openai_endpoint: process.env.AZURE_OPENAI_ENDPOINT,
                model: process.env.AZURE_OPENAI_MODEL
            });
        });

        // Debug route to list static files
        app.get('/debug/files', (req, res) => {
            const staticPath = path.join(__dirname, 'static');
            const files = [];
            function walkDir(dir, prefix = '') {
                const items = fs.readdirSync(dir);
                items.forEach(item => {
                    const fullPath = path.join(dir, item);
                    const stat = fs.statSync(fullPath);
                    if (stat.isDirectory()) {
                        walkDir(fullPath, path.join(prefix, item));
                    } else {
                        files.push(path.join(prefix, item));
                    }
                });
            }
            walkDir(staticPath);
            res.json({ files });
        });

        // Start listening
        app.listen(port, () => {
            console.log(`
🚀 Chat server is running!

📡 Server Info:
   - Platform: ${process.platform}
   - Node Version: ${process.version}
   - Port: ${port}
   - OpenAI Model: ${process.env.AZURE_OPENAI_MODEL}

🔗 URLs:
   - Main Chat: http://localhost:${port}
   - Health Check: http://localhost:${port}/health
   - Debug Files: http://localhost:${port}/debug/files

💡 Tips:
   - Use Ctrl+C to stop the server
   - Check /health for system status
   - Check /debug/files to see available static files
   - Watch the console for real-time chat logs
            `);
        });

    } catch (error) {
        console.error('Failed to start server:', error);
        process.exit(1);
    }
}

// Handle graceful shutdown
process.on('SIGINT', async () => {
    console.log('\n👋 Shutting down gracefully...');
    await killPort(port);
    process.exit(0);
});

// Enhanced error handling
process.on('uncaughtException', (err) => {
    console.error('🚨 Uncaught Exception:', err);
});

process.on('unhandledRejection', (err) => {
    console.error('🚨 Unhandled Rejection:', err);
});

// Start the server
startServer(); 