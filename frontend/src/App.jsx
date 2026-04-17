import { Link, Route, Routes } from 'react-router-dom';
import HomePage from './pages/HomePage.jsx';
import MapPage from './pages/MapPage/MapPage.jsx';
import ClustersPage from './pages/ClustersPage/ClustersPage.jsx';
import ClusterDetailPage from './pages/ClusterDetailPage/ClusterDetailPage.jsx';
import TrackDetailsPage from './components/TrackDetails/TrackDetailsPage.jsx';

export default function App() {
  return (
    <div className="app">
      <header className="header">
        <Link to="/" className="logo">Music Trends Galaxy</Link>
        <nav className="nav">
          <Link to="/" className="nav-link">Home</Link>
          <Link to="/map" className="nav-link">Map</Link>
          <Link to="/clusters" className="nav-link">Clusters</Link>
        </nav>
      </header>
      <main className="main-content">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/clusters" element={<ClustersPage />} />
          <Route path="/clusters/:clusterCode" element={<ClusterDetailPage />} />
          <Route path="/track-details/:trackId" element={<TrackDetailsPage />} />
        </Routes>
      </main>
    </div>
  )
}