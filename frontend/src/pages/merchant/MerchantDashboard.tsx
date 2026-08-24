import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { merchantAPI, MerchantOverview, MerchantIncident } from '../../api/merchant';

const MerchantDashboard: React.FC = () => {
  const [overview, setOverview] = useState<MerchantOverview | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [backendError, setBackendError] = useState<string | null>(null);

  useEffect(() => {
    const fetchOverview = async () => {
      try {
        setLoading(true);
        const response = await merchantAPI.getOverview();
        setOverview(response.data);
        setError(null);
      } catch (err: any) {
        console.error('Failed to fetch merchant overview:', err);
        setError('Failed to load dashboard data');
        if (err.response?.data?.error?.message) {
          setBackendError(err.response.data.error.message);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchOverview();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-500 font-medium flex items-center space-x-2">
          <svg className="animate-spin h-5 w-5 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>Loading payment health...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 p-4 rounded text-red-800">
        <h3 className="font-semibold">{error}</h3>
        {backendError && <p className="text-sm mt-1 opacity-90">{backendError}</p>}
      </div>
    );
  }

  if (!overview) {
    return <div className="text-center py-12 text-slate-500">No data available</div>;
  }

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'HIGH':
        return <span className="badge-red">{severity}</span>;
      case 'MEDIUM':
        return <span className="badge-yellow">{severity}</span>;
      case 'LOW':
        return <span className="badge-neutral">{severity}</span>;
      default:
        return <span className="badge-neutral">{severity}</span>;
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between pb-4 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Merchant Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">Real-time payment health and incident response</p>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-sm font-medium text-slate-600">Payment System Status:</span>
          {overview.active_incidents > 0 ? (
            <span className="badge-yellow flex items-center"><span className="w-2 h-2 rounded-full bg-amber-500 mr-1.5"></span>DEGRADED</span>
          ) : (
            <span className="badge-green flex items-center"><span className="w-2 h-2 rounded-full bg-emerald-500 mr-1.5"></span>HEALTHY</span>
          )}
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card p-4 flex flex-col justify-between">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Total Incidents</h3>
          <p className="text-3xl font-bold text-slate-900">{overview.total_incidents}</p>
        </div>
        <div className="card p-4 flex flex-col justify-between border-l-4 border-l-amber-400">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Active Incidents</h3>
          <p className="text-3xl font-bold text-slate-900">{overview.active_incidents}</p>
        </div>
        <div className="card p-4 flex flex-col justify-between">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Success Rate Change</h3>
          <p className={`text-3xl font-bold ${overview.overall_success_rate_change >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
            {overview.overall_success_rate_change > 0 ? '+' : ''}{overview.overall_success_rate_change.toFixed(1)} pp
          </p>
        </div>
        <div className="card p-4 flex flex-col justify-between">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Revenue at Risk</h3>
          <p className="text-3xl font-bold text-slate-900 font-mono">₹{(overview.total_revenue_at_risk_paise / 100).toLocaleString()}</p>
        </div>
      </div>

      {/* Recent Incidents */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 bg-slate-50">
          <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Active & Recent Incidents</h2>
        </div>
        
        {overview.recent_incidents.length === 0 ? (
          <div className="p-12 text-center text-slate-500 flex flex-col items-center">
            <svg className="w-12 h-12 text-slate-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            <p className="font-medium">No active incidents</p>
            <p className="text-sm mt-1">Payment infrastructure is operating normally.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-200">
            {overview.recent_incidents.map((incident: MerchantIncident) => {
              const srChange = ((incident.success_rate_evidence?.current_success_rate || 0) - (incident.success_rate_evidence?.baseline_success_rate || 0)) * 100;
              
              return (
                <div key={incident.incident_id} className="p-5 hover:bg-slate-50 transition-colors flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center space-x-3">
                      <Link to={`/merchant/incidents/${incident.incident_id}`} className="font-mono text-sm font-bold text-blue-600 hover:underline">
                        {incident.incident_id}
                      </Link>
                      {getSeverityBadge(incident.severity)}
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${
                        incident.status === 'DETECTED' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                        incident.status === 'RESOLVED' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                        'bg-slate-100 text-slate-700 border-slate-200'
                      }`}>
                        {incident.status}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs font-medium text-slate-600">
                      {incident.affected_segment.payment_method && <span className="bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">{incident.affected_segment.payment_method}</span>}
                      {incident.affected_segment.bank && <span className="bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">{incident.affected_segment.bank}</span>}
                      {incident.affected_segment.device && <span className="bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">{incident.affected_segment.device}</span>}
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-6 shrink-0">
                    <div className="text-right hidden sm:block">
                      <div className="text-xs text-slate-500 font-semibold uppercase tracking-wider mb-1">Impact</div>
                      <div className={`text-sm font-bold ${srChange < 0 ? 'text-red-600' : 'text-slate-700'}`}>
                        {srChange.toFixed(1)} pp SR
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-slate-500 font-semibold uppercase tracking-wider mb-1">Detected</div>
                      <div className="text-sm text-slate-700 font-medium tabular-nums">
                        {new Date(incident.detection_timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        <span className="text-slate-400 ml-1 block sm:inline text-xs">{new Date(incident.detection_timestamp).toLocaleDateString()}</span>
                      </div>
                    </div>
                    <Link
                      to={`/merchant/incidents/${incident.incident_id}`}
                      className="btn-secondary whitespace-nowrap"
                    >
                      Investigate
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default MerchantDashboard;
