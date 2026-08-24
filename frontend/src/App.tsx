import RoleBasedRedirect from "./components/RoleBasedRedirect";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import Layout from './components/layout/Layout';
// Merchant pages
import Login from "./pages/Login";
import MerchantDashboard from './pages/merchant/MerchantDashboard';
import MerchantIncidentDetail from './pages/merchant/MerchantIncidentDetail';
// Support pages
import SupportIncidentConsole from './pages/support/SupportIncidentConsole';
import SupportIncidentDetail from './pages/support/SupportIncidentDetail';
import SupportEvidenceDetail from './pages/support/SupportEvidenceDetail';
import SupportAuditDetail from './pages/support/SupportAuditDetail';
// Approvals pages
import ApprovalQueue from './pages/approvals/ApprovalQueue';
import ApprovalDetail from './pages/approvals/ApprovalDetail';

// Wrapper to avoid Layout on Login page
const AppRoutes = () => {
  const location = useLocation();
  const isLogin = location.pathname === '/login';

  if (isLogin) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Layout>
      <Routes>
        {/* Merchant routes */}
        <Route path="/merchant" element={<MerchantDashboard />} />
        <Route path="/merchant/incidents/:incidentId" element={<MerchantIncidentDetail />} />

        {/* Support routes */}
        <Route path="/support" element={<SupportIncidentConsole />} />
        <Route path="/support/incidents/:incidentId" element={<SupportIncidentDetail />} />
        <Route path="/support/evidence/:incidentId" element={<SupportEvidenceDetail />} />
        <Route path="/support/audit/:incidentId" element={<SupportAuditDetail />} />

        {/* Approvals routes */}
        <Route path="/approvals" element={<ApprovalQueue />} />
        <Route path="/approvals/:approvalId" element={<ApprovalDetail />} />

        {/* Redirect root to merchant dashboard */}
        <Route path="/" element={<RoleBasedRedirect />} />
        {/* Handle 404 */}
        <Route path="*" element={<div className="text-center py-12 text-slate-500 font-medium">404 - Page Not Found</div>} />
      </Routes>
    </Layout>
  );
};

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

export default App;
