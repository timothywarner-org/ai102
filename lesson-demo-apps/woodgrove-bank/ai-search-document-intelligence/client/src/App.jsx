import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import SearchPage from './pages/SearchPage';
import UploadPage from './pages/UploadPage';
import ReportPage from './pages/ReportPage';

export default function App() {
  return (
    <Router>
      <header style={{ background: '#0a3d62', color: '#fff', padding: '1rem', marginBottom: '2rem' }}>
        <h1 style={{ margin: 0, fontSize: '2rem' }}>Woodgrove Bank: AI-Powered Hotel Search</h1>
        <nav style={{ marginTop: '1rem' }}>
          <Link to="/" style={{ color: '#fff', marginRight: '1rem' }}>Search</Link>
          <Link to="/upload" style={{ color: '#fff', marginRight: '1rem' }}>Upload Receipt</Link>
          <Link to="/report" style={{ color: '#fff' }}>Report</Link>
        </nav>
      </header>
      <main style={{ maxWidth: 800, margin: '0 auto' }}>
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/report" element={<ReportPage />} />
        </Routes>
      </main>
    </Router>
  );
}
