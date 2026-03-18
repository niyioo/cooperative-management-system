import { HashRouter as Router, Routes, Route, Navigate, Link } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './routes/ProtectedRoute';

// Layouts & Auth
import Login from './pages/Login';
import DashboardLayout from './layouts/DashboardLayout';

// Dashboard Pages
import AdminDashboard from './pages/dashboard/AdminDashboard';
import Members from './pages/dashboard/Members';
import Savings from './pages/dashboard/Savings';
import Loans from './pages/dashboard/Loans';
import Shares from './pages/dashboard/Shares';
import Contributions from './pages/dashboard/Contributions';
import FinanceLedger from './pages/finance/FinanceLedger';
import Settings from './pages/dashboard/Settings';
import Notifications from './pages/dashboard/Notifications';

const Unauthorized = () => (
  <div className="flex h-screen items-center justify-center bg-slate-50">
    <div className="text-center">
      <h1 className="text-4xl font-bold text-slate-900 mb-2">403</h1>
      <p className="text-slate-600 mb-4">You do not have permission to access this page.</p>
      {/* Replaced standard <a> tag with React Router's <Link> for Hash compatibility */}
      <Link to="/dashboard" className="text-blue-600 hover:underline">Return to Dashboard</Link>
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
              <Route path="members" element={<Members />} />
              <Route path="savings" element={<Savings />} />
              <Route path="loans" element={<Loans />} />
              <Route path="shares" element={<Shares />} />
              <Route path="contributions" element={<Contributions />} />
              <Route path="finance" element={<FinanceLedger />} />
              <Route path="settings" element={<Settings />} />
              <Route path="notifications" element={<Notifications />} />
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