# Woodgrove Bank Receipt Analyzer Demo

A simple, professional demo application for Azure AI-102 certification that showcases Document Intelligence (formerly Form Recognizer) with receipt analysis.

## Features

- Clean, modern UI with Woodgrove Bank branding
- Drag & drop receipt upload
- Auto-loading demo receipt
- Real-time receipt analysis
- Tabular results display

## Quick Start

```bash
cd doc-intel
npm install
npm start
```

The app runs on http://localhost:5000 with unified frontend and backend.

## Demo Setup

1. Create a `.env` file with your Azure credentials:
```
DOC_INTEL_ENDPOINT=your-endpoint.cognitiveservices.azure.com
DOC_INTEL_KEY=your-key
MODEL_ID=prebuilt-receipt
```

2. Place a `receipt.jpg` in the uploads folder for auto-demo
3. Start the server with `npm start`

## AI-102 Exam Tips

### Document Intelligence
- **Key Fields**: MerchantName, TransactionDate, Total, Subtotal, Tax, Items
- **Response Format**: 
  - `analyzeResult.documents[0].fields`
  - Each field has `content`, `confidence`, and `boundingRegions`
- **API Version**: 2023-07-31
- **Model ID**: Always use `prebuilt-receipt` for receipts

### Best Practices
- Always handle asynchronous analysis with proper polling
- Check confidence scores for field reliability
- Implement proper error handling
- Use proper regional endpoints

### Live Demo Tips
- Port 5000 is automatically freed using kill-port
- Demo receipt auto-loads if present
- Error messages are user-friendly
- Clean UI suitable for presentations

## Resources
- [Azure Document Intelligence Documentation](https://learn.microsoft.com/azure/ai-services/document-intelligence/)
- [Receipt Model Documentation](https://learn.microsoft.com/azure/ai-services/document-intelligence/prebuilt/receipt) 