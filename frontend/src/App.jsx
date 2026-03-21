import { Link, Route, Routes } from 'react-router-dom'
import MapPage from './pages/MapPage.jsx'
import HomePage from './pages/HomePage.jsx'
import DataPipelinePage from './pages/DataPipelinePage.jsx'

export default function App() {
  return (
    <div className="app">
      <header className="header">
        <Link to="/" className="brand">
          Music Trends Galaxy
        </Link>
        <nav>
          <Link to="/">Home</Link>
          <Link to="/map">Map</Link>
          <Link to="/pipeline">Pipeline</Link>
        </nav>
      </header>
      <main className="main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/pipeline" element={<DataPipelinePage />} />
        </Routes>
      </main>
    </div>
  )
}