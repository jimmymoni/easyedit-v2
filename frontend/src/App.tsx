import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import VideoEditorPage from './pages/VideoEditorPage';
import VideoTestPage from './pages/VideoTestPage';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<VideoEditorPage />} />
        <Route path="/video-test/:jobId" element={<VideoTestPage />} />
      </Routes>
    </Router>
  );
}

export default App;
