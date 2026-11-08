# Tim's Chat - An Educational Azure OpenAI Chat Application

A modern, educational chat application built with Node.js and Azure OpenAI, designed to help developers learn about AI integration, cloud development, and modern web practices.

## Features

- 🚀 **Pure Node.js Implementation** - Clean, modern JavaScript without framework complexity
- 🎨 **Microsoft Fluent Design** - Beautiful UI with Poppins font and JetBrains Mono for code
- 🔄 **Real-time Streaming** - See AI responses as they're generated
- ☁️ **Azure OpenAI Integration** - Enterprise-grade AI capabilities
- 🎯 **Educational Focus** - Learn while you chat

## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/tim-chat-front-end.git
   cd tim-chat-front-end
   ```

2. Create a `.env` file based on `.env.sample` with your Azure OpenAI credentials:
   ```env
   AZURE_OPENAI_API_KEY=your_key_here
   AZURE_OPENAI_ENDPOINT=your_endpoint_here
   AZURE_OPENAI_DEPLOYMENT=your_deployment_here
   ```

3. Start the application:
   ```bash
   # On Windows
   start.cmd

   # On Unix/Mac
   ./start.sh
   ```

4. Open http://localhost:50505 in your browser

## Architecture

- **Backend**: Node.js with Express
- **Frontend**: Vanilla JavaScript with modern ES6+ features
- **AI**: Azure OpenAI with streaming responses
- **Design**: Microsoft Fluent Design System
- **Fonts**: Poppins for UI, JetBrains Mono for code

## Roadmap - Educational Features

We're planning to add these educational features:

### 1. Interactive Learning Views
- Split-screen view showing chat alongside educational content
- Real-time JSON structure visualization
- Live API request/response monitoring
- Token usage tracking and visualization

### 2. Code Learning Tools
- Syntax highlighting for code snippets
- Interactive code playgrounds
- Version control visualization
- Best practices highlighting

### 3. Azure & Cloud Learning
- Azure service integration examples
- Cloud architecture visualization
- Cost estimation tools
- Security best practices demos

### 4. Developer Tools
- Network request inspector
- Performance monitoring
- Authentication flow visualization
- Error handling demonstrations

### 5. AI Learning Features
- Token counting and optimization tips
- Prompt engineering examples
- Model behavior analysis
- Response pattern learning

## Contributing

We welcome contributions! Here are some ways you can help:

1. 🐛 Report bugs
2. 💡 Suggest new features
3. 📚 Improve documentation
4. 🔧 Submit pull requests

## Development

The application uses a simple but powerful stack:

```javascript
// Backend (app.js)
- Express for the web server
- Azure OpenAI SDK for AI integration
- Streaming response handling
- Environment configuration

// Frontend (static/*)
- Vanilla JavaScript
- Microsoft Fluent Design
- Server-Sent Events for streaming
- Modern CSS with variables
```

## License

MIT License - See LICENSE file for details

## Acknowledgments

- Microsoft Azure OpenAI team
- Microsoft Fluent Design System
- The open-source community

---

Built with 💙 by Tim and the community 