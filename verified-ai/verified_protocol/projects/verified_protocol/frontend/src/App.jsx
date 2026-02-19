import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar.jsx'
import SubmitPage from './pages/SubmitPage.jsx'
import RecordsPage from './pages/RecordsPage.jsx'
import VerifierPage from './pages/VerifierPage.jsx'

const API_BASE = 'http://localhost:8000'

function App() {
  return (
    <>
      <div className="bg-orbs" />
      <Navbar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<SubmitPage apiBase={API_BASE} />} />
          <Route path="/records" element={<RecordsPage apiBase={API_BASE} />} />
          <Route path="/verify" element={<VerifierPage apiBase={API_BASE} />} />
        </Routes>
      </main>
    </>
  )
}

export default App
