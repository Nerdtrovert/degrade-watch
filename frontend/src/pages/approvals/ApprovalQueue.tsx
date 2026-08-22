import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { approvalsAPI, Approval } from '../api/approvals';

const ApprovalQueue: React.FC = () => {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchApprovals = async () => {
      try {
        setLoading(true);
        const response = await approvalsAPI.getApprovals();
        setApprovals(response.data);
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

  if (loading) {
    return <div className="text-center py-12">Loading...</div>;
  }

  if (error) {
    return <div className="text-center py-12 text-red-500">{error}</div>;
  }

  if (approvals.length === 0) {
    return <div className="text-center py-12">No pending approvals</div>;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Approval Queue</h1>

      <div className="bg-white p-4 rounded-lg shadow">
        <h2 className="text-xl font-bold mb-4">Pending Human Approvals</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Approval ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Incident ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Merchant ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Severity
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Revenue at Risk
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Affected Segment
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Proposed Action
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Policy Reason Codes
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Confidence
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created At
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {approvals.map((approval: Approval) => (
                <tr key={approval.approval_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">{approval.approval_id}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">{approval.incident_id}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">{approval.merchant_id}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      approval.severity === 'HIGH' ? 'bg-red-100 text-red-800' :
                      approval.severity === 'MEDIUM' ? 'bg-orange-100 text-orange-800' :
                      approval.severity === 'LOW' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-green-100 text-green-800'
                    }`}>
                      {approval.severity}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {(approval.revenue_at_risk_paise || 0) / 100} INR
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {approval.merchant_id === 'scenario_a_merchant' ? 'UPI|BANK_X|ANDROID|PHONEPE' : 'UPI|BANK_Y|IOS|GOOGLE_PAY'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">{approval.proposed_action}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {approval.policy_reason_codes.join(', ')}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {(approval.confidence || 0) * 100}%
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {new Date(approval.created_at).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right space-x-2">
                    <Link
                      to={`/approvals/${approval.approval_id}`}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      View
                    </Link>
                    <button
                      onClick={() => handleApprove(approval.approval_id)}
                      className="px-3 py-1 bg-green-500 text-white text-sm rounded hover:bg-green-600"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleReject(approval.approval_id)}
                      className="px-3 py-1 bg-red-500 text-white text-sm rounded hover:bg-red-600 ml-2"
                    >
                      Reject
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  // Handler functions
  async function handleApprove(approvalId: string) {
    try {
      await approvalsAPI.approveApproval(approvalId);
      // Update the local state to remove the approved approval
      setApprovals(approvals.filter(approval => approval.approval_id !== approvalId));
    } catch (err: any) {
      console.error('Failed to approve:', err);
      alert('Failed to approve recovery');
    }
  }

  async function handleReject(approvalId: string) {
    try {
      await approvalsAPI.rejectApproval(approvalId);
      // Update the local state to remove the rejected approval
      setApprovals(approvals.filter(approval => approval.approval_id !== approvalId));
    } catch (err: any) {
      console.error('Failed to reject:', err);
      alert('Failed to reject recovery');
    }
  }
};

export default ApprovalQueue;