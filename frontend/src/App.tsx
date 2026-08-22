import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/layout/Navbar';
// Merchant pages
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

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <main className="container mx-auto px-4 py-8">
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
            <Route path="/" element={<Navigate to="/merchant" replace />} />
            {/* Handle 404 */}
            <Route path="*" element={<div className="text-center py-12">404 - Page Not Found</div>} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;