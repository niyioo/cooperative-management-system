import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './routes/ProtectedRoute';

import Login from './pages/Login';
import DashboardLayout from './layouts/DashboardLayout';
import AdminDashboard from './pages/dashboard/AdminDashboard';

// A simple unauthorized fallback component
const Unauthorized = () => (
  <div className="flex h-screen items-center justify-center bg-slate-50">
    <div className="text-center">
      <h1 className="text-4xl font-bold text-slate-900 mb-2">403</h1>
      <p className="text-slate-600 mb-4">You don't have permission to access this page.</p>
      <a href="/dashboard" className="text-blue-600 hover:underline">Return to Dashboard</a>
    </div>
  </div>
);

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/unauthorized" element={<Unauthorized />} />

          {/* Protected Dashboard Routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<DashboardLayout />}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<AdminDashboard />} />
            </Route>
          </Route>

          {/* Catch all */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;