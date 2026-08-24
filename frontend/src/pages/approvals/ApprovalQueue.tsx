import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { approvalsAPI, Approval } from '../../api/approvals';

const ApprovalQueue: React.FC = () => {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchApprovals = async () => {
      try {
        setLoading(true);
        const response = await approvalsAPI.getApprovals();
        setApprovals(response.data.items);
        setError(null);
      } catch (err: any) {
        console.error('Failed to fetch approvals:', err);
        setError('Failed to load approval queue');
      } finally {
        setLoading(false);
      }
    };

    fetchApprovals();
  }, []);

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'HIGH': return <span className="badge-red">{severity}</span>;
      case 'MEDIUM': return <span className="badge-yellow">{severity}</span>;
      case 'LOW': return <span className="badge-neutral">{severity}</span>;
      default: return <span className="badge-neutral">{severity}</span>;
    }
  };

  async function handleApprove(approvalId: string) {
    if (!window.confirm("Approve this recovery action?")) return;
    try {
      await approvalsAPI.approveApproval(approvalId);
      setApprovals(approvals.filter(approval => approval.approval_id !== approvalId));
    } catch (err: any) {
      console.error('Failed to approve:', err);
      alert('Failed to approve recovery: ' + (err.response?.data?.error?.message || err.message));
    }
  }

  async function handleReject(approvalId: string) {
    if (!window.confirm("Reject this recovery action?")) return;
    try {
      await approvalsAPI.rejectApproval(approvalId);
      setApprovals(approvals.filter(approval => approval.approval_id !== approvalId));
    } catch (err: any) {
      console.error('Failed to reject:', err);
      alert('Failed to reject recovery: ' + (err.response?.data?.error?.message || err.message));
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-500 font-medium flex items-center space-x-2">
          <svg className="animate-spin h-5 w-5 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          <span>Loading approval queue...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 p-4 rounded text-red-800">
        <h3 className="font-semibold">{error}</h3>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between pb-4 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Approval Queue</h1>
          <p className="text-sm text-slate-500 mt-1">Review and authorize pending automated recovery actions</p>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
          <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Pending Human Approvals</h2>
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-200 text-slate-700">{approvals.length} Requests</span>
        </div>
        
        {approvals.length === 0 ? (
          <div className="p-12 text-center text-slate-500 flex flex-col items-center">
            <svg className="w-12 h-12 text-slate-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
            <p className="font-medium">All caught up!</p>
            <p className="text-sm mt-1">No pending actions require human authorization.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Request</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Incident Context</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Severity</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Action Context</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Policy Engine</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Authorization</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {approvals.map((approval: Approval) => (
                  <tr key={approval.approval_id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="font-mono text-sm font-semibold text-slate-800">{approval.approval_id}</div>
                      <div className="text-xs text-slate-500 mt-0.5">{new Date(approval.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="text-sm font-mono font-medium text-slate-700">{approval.incident_id}</div>
                      <div className="text-xs text-slate-500 mt-0.5">Merchant: {approval.merchant_id}</div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {getSeverityBadge(approval.severity)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="text-sm font-bold text-slate-800">{approval.proposed_action}</div>
                      <div className="text-xs text-slate-500 mt-0.5 font-mono">₹{((approval.revenue_at_risk_paise || 0) / 100).toLocaleString()} at risk</div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="flex flex-wrap gap-1">
                        {approval.policy_reason_codes.map((code: string, i: number) => (
                          <span key={i} className="text-[10px] font-mono bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded border border-slate-200">{code}</span>
                        ))}
                      </div>
                      <div className="text-xs text-blue-600 mt-1 font-medium">Confidence: {((approval.confidence || 0) * 100).toFixed(1)}%</div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-right space-x-2">
                      <button
                        onClick={() => handleApprove(approval.approval_id)}
                        className="btn-primary py-1 px-3 text-xs"
                      >
                        Authorize
                      </button>
                      <button
                        onClick={() => handleReject(approval.approval_id)}
                        className="btn-danger py-1 px-3 text-xs"
                      >
                        Reject
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default ApprovalQueue;
