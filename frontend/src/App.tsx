import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import MainPage from './pages/MainPage';
import GodModePage from './pages/GodModePage';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<MainPage />} />
        <Route path="/godmode/:jobId" element={<GodModePage />} />
      </Routes>
    </Router>
  );
}

export default App;
