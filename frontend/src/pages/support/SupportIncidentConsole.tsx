import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { supportAPI, SupportIncident } from '../../api/support';

const SupportIncidentConsole: React.FC = () => {
  const [incidents, setIncidents] = useState<SupportIncident[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchIncidents = async () => {
      try {
        setLoading(true);
        const response = await supportAPI.getIncidents();
        setIncidents(response.data);
        setError(null);
      } catch (err: any) {
        console.error('Failed to fetch support incidents:', err);
        setError('Failed to load incidents');
      } finally {
        setLoading(false);
      }
    };

    fetchIncidents();
  }, []);

  if (loading) {
    return <div className="text-center py-12">Loading...</div>;
  }

  if (error) {
    return <div className="text-center py-12 text-red-500">{error}</div>;
  }

  if (incidents.length === 0) {
    return <div className="text-center py-12">No incidents found</div>;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Support / Operations Console</h1>

      <div className="bg-white p-4 rounded-lg shadow">
        <h2 className="text-xl font-bold mb-4">Active Incidents</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Incident ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Timestamp
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Merchant ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Severity
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Classification
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Affected Segment
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Success Rate Change
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Revenue at Risk
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Policy Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Recovery Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {incidents.map((incident: SupportIncident) => (
                <tr key={incident.incident_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">{incident.incident_id}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">{new Date(incident.detection_timestamp).toLocaleString()}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">{incident.merchant_id}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      incident.severity === 'HIGH' ? 'bg-red-100 text-red-800' :
                      incident.severity === 'MEDIUM' ? 'bg-orange-100 text-orange-800' :
                      incident.severity === 'LOW' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-green-100 text-green-800'
                    }`}>
                      {incident.severity}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      incident.classification === 'INCIDENT' ? 'bg-red-100 text-red-800' :
                      incident.classification === 'NORMAL' ? 'bg-green-100 text-green-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {incident.classification}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {incident.affected_segment.payment_method} | {incident.affected_segment.bank} | {incident.affected_segment.device}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {((incident.success_rate_evidence?.current_success_rate || 0) - (incident.success_rate_evidence?.baseline_success_rate || 0)) * 100}% points
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {(incident.impact_evidence?.revenue_at_risk.paise || 0) / 100} INR
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      incident.policy_status === 'AUTO_APPROVED' ? 'bg-green-100 text-green-800' :
                      incident.policy_status === 'HUMAN_APPROVAL' ? 'bg-yellow-100 text-yellow-800' :
                      incident.policy_status === 'BLOCKED' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {incident.policy_status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      incident.recovery_status === 'COMPLETED' ? 'bg-green-100 text-green-800' :
                      incident.recovery_status === 'PROCESSING' ? 'bg-blue-100 text-blue-800' :
                      incident.recovery_status === 'PENDING' ? 'bg-yellow-100 text-yellow-800' :
                      incident.recovery_status === 'FAILED' ? 'bg-red-100 text-red-800' :
                      incident.recovery_status === 'CANCELLED' ? 'bg-gray-100 text-gray-800' :
                      incident.recovery_status === 'NOT_AUTHORIZED' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {incident.recovery_status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-right space-x-2">
                    <Link
                      to={`/support/incidents/${incident.incident_id}`}
                      className="text-blue-600 hover:text-blue-800"
                    >
                      View
                    </Link>
                    <Link
                      to={`/support/evidence/${incident.incident_id}`}
                      className="text-green-600 hover:text-green-800"
                    >
                      Evidence
                    </Link>
                    <Link
                      to={`/support/audit/${incident.incident_id}`}
                      className="text-purple-600 hover:text-purple-800"
                    >
                      Audit
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default SupportIncidentConsole;