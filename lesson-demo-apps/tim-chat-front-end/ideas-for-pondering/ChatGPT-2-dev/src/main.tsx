import { StrictMode } from 'react';
import ReactDOM from 'react-dom/client';

// import Routes from './routes';
import App from './App';
import './base.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>
);
