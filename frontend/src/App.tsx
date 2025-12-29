import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import CodingPage from './pages/CodingPage';
import CoursesPage from './pages/CoursesPage';
import AdminDashboard from './pages/admin/AdminDashboard';
import CourseEditor from './pages/admin/CourseEditor';
import Login from './pages/Login';
import Signup from './pages/Signup';
import { AuthProvider } from './context/AuthContext';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/" element={<CoursesPage />} />
          <Route path="/course/:id" element={<CodingPage />} />
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/admin/courses/:id" element={<CourseEditor />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
