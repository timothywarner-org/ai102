import React, { useState } from 'react';

export default function UploadPage() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);

  function handleFileChange(e) {
    setFile(e.target.files[0]);
  }

  function handleAnalyze() {
    // Mocked result for MVP
    setResult({
      hotelName: 'Stay-Kay City Hotel',
      date: '2024-06-01',
      amount: '$189.99',
      notes: 'This is a mocked analysis result.'
    });
  }

  return (
    <div>
      <h2>Upload Hotel Receipt</h2>
      <input type="file" onChange={handleFileChange} />
      <button onClick={handleAnalyze} disabled={!file} style={{ marginLeft: 8 }}>
        Analyze
      </button>
      {result && (
        <div style={{ marginTop: 24, border: '1px solid #ccc', borderRadius: 8, padding: 16 }}>
          <h3>Analysis Result</h3>
          <p><strong>Hotel Name:</strong> {result.hotelName}</p>
          <p><strong>Date:</strong> {result.date}</p>
          <p><strong>Amount:</strong> {result.amount}</p>
          <p>{result.notes}</p>
        </div>
      )}
    </div>
  );
} 