import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { supportAPI, SupportIncident } from '../../api/support';

const SupportIncidentConsole: React.FC = () => {
  const [incidents, setIncidents] = useState<SupportIncident[]>([]);
  const activeIncidents = incidents.filter(i => i.classification !== 'NORMAL');
  const normalIncidents = incidents.filter(i => i.classification === 'NORMAL');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchIncidents = async () => {
      try {
        setLoading(true);
        const response = await supportAPI.getIncidents();
        setIncidents(response.data.items);
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
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-500 font-medium flex items-center space-x-2">
          <svg className="animate-spin h-5 w-5 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
          <span>Loading support console...</span>
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

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'HIGH': return <span className="badge-red">{severity}</span>;
      case 'MEDIUM': return <span className="badge-yellow">{severity}</span>;
      case 'LOW': return <span className="badge-neutral">{severity}</span>;
      default: return <span className="badge-neutral">{severity}</span>;
    }
  };

  const getPolicyBadge = (status: string) => {
    switch (status) {
      case 'AUTO_APPROVED': return <span className="badge-green">{status}</span>;
      case 'HUMAN_APPROVAL': return <span className="badge-yellow">{status}</span>;
      case 'BLOCKED': return <span className="badge-red">{status}</span>;
      default: return <span className="badge-neutral">{status || 'NOT_APPLICABLE'}</span>;
    }
  };

  const getRecoveryBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED': return <span className="badge-green">{status}</span>;
      case 'PROCESSING': return <span className="badge-blue">{status}</span>;
      case 'FAILED': return <span className="badge-red">{status}</span>;
      default: return <span className="badge-neutral">{status || 'NOT_EXECUTED'}</span>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between pb-4 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Support Console</h1>
          <p className="text-sm text-slate-500 mt-1">Cross-merchant incident operations and investigation</p>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
          <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Active Incidents</h2>
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-200 text-slate-700">{activeIncidents.length} Records</span>
        </div>
        
        {activeIncidents.length === 0 ? (
          <div className="p-12 text-center text-slate-500 flex flex-col items-center">
            <svg className="w-12 h-12 text-slate-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            <p className="font-medium">No active incidents found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">ID & Time</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Merchant</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Severity</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Segment</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Impact</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Policy</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Recovery</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {activeIncidents.map((incident: SupportIncident) => (
                  <tr key={incident.incident_id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="font-mono text-sm font-semibold text-slate-800">{incident.incident_id}</div>
                      <div className="text-xs text-slate-500 mt-0.5">{new Date(incident.detection_timestamp).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="text-sm font-medium text-slate-700">{incident.merchant_id}</div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {getSeverityBadge(incident.severity)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-600">
                      <div className="flex gap-1 flex-col">
                        <span className="font-medium text-slate-800">{incident.affected_segment.payment_method}</span>
                        <span>{incident.affected_segment.bank}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className={`text-sm font-bold ${(((incident.success_rate_evidence?.current_success_rate || 0) - (incident.success_rate_evidence?.baseline_success_rate || 0)) * 100) < 0 ? 'text-red-600' : 'text-slate-700'}`}>
                        {(((incident.success_rate_evidence?.current_success_rate || 0) - (incident.success_rate_evidence?.baseline_success_rate || 0)) * 100).toFixed(1)} pp SR
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5 font-mono">₹{((incident.impact_evidence?.revenue_at_risk.paise || 0) / 100).toLocaleString()}</div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {getPolicyBadge(incident.policy_status)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {getRecoveryBadge(incident.recovery_status)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-right">
                      <Link
                        to={`/support/incidents/${incident.incident_id}`}
                        className="text-xs font-semibold text-blue-600 hover:text-blue-800 hover:underline px-2 py-1"
                      >
                        Inspect
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
          <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Rejected Degradations (Normal)</h2>
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-200 text-slate-700">{normalIncidents.length} Records</span>
        </div>
        
        {normalIncidents.length === 0 ? (
          <div className="p-12 text-center text-slate-500 flex flex-col items-center">
            <svg className="w-12 h-12 text-slate-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            <p className="font-medium">No rejected degradations found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">ID & Time</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Merchant</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Severity</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Segment</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Impact</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Policy</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">Recovery</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {normalIncidents.map((incident: SupportIncident) => (
                  <tr key={incident.incident_id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="font-mono text-sm font-semibold text-slate-800">{incident.incident_id}</div>
                      <div className="text-xs text-slate-500 mt-0.5">{new Date(incident.detection_timestamp).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="text-sm font-medium text-slate-700">{incident.merchant_id}</div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {getSeverityBadge(incident.severity)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-600">
                      <div className="flex gap-1 flex-col">
                        <span className="font-medium text-slate-800">{incident.affected_segment.payment_method}</span>
                        <span>{incident.affected_segment.bank}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className={`text-sm font-bold ${(((incident.success_rate_evidence?.current_success_rate || 0) - (incident.success_rate_evidence?.baseline_success_rate || 0)) * 100) < 0 ? 'text-red-600' : 'text-slate-700'}`}>
                        {(((incident.success_rate_evidence?.current_success_rate || 0) - (incident.success_rate_evidence?.baseline_success_rate || 0)) * 100).toFixed(1)} pp SR
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5 font-mono">₹{((incident.impact_evidence?.revenue_at_risk.paise || 0) / 100).toLocaleString()}</div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {getPolicyBadge(incident.policy_status)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {getRecoveryBadge(incident.recovery_status)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-right">
                      <Link
                        to={`/support/incidents/${incident.incident_id}`}
                        className="text-xs font-semibold text-blue-600 hover:text-blue-800 hover:underline px-2 py-1"
                      >
                        Inspect
                      </Link>
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

export default SupportIncidentConsole;
