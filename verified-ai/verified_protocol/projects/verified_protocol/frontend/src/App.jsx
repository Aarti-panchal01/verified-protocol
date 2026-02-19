import { Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import SubmitPage from './pages/SubmitPage';
import DashboardPage from './pages/RecordsPage';
import VerifierPage from './pages/VerifierPage';
import ExplorerPage from './pages/ExplorerPage';

export default function App() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<SubmitPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/verifier" element={<VerifierPage />} />
        <Route path="/explorer" element={<ExplorerPage />} />
      </Routes>
    </>
  );
}
