import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { merchantAPI, MerchantOverview, MerchantIncident } from '../api/merchant';

const MerchantDashboard: React.FC = () => {
  const [overview, setOverview] = useState<MerchantOverview | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

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
      } finally {
        setLoading(false);
      }
    };

    fetchOverview();
  }, []);

  if (loading) {
    return <div className="text-center py-12">Loading...</div>;
  }

  if (error) {
    return <div className="text-center py-12 text-red-500">{error}</div>;
  }

  if (!overview) {
    return <div className="text-center py-12">No data available</div>;
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Merchant Dashboard</h1>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-white p-4 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500">Total Incidents</h3>
          <p className="text-2xl font-bold">{overview.total_incidents}</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500">Active Incidents</h3>
          <p className="text-2xl font-bold">{overview.active_incidents}</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500">Success Rate Change</h3>
          <p className={`text-2xl font-bold ${overview.overall_success_rate_change >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {overview.overall_success_rate_change.toFixed(2)}%
          </p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500">Revenue at Risk</h3>
          <p className="text-2xl font-bold">{overview.total_revenue_at_risk_paise / 100} INR</p>
        </div>
      </div>

      {/* Recent Incidents */}
      <div className="bg-white p-4 rounded-lg shadow">
        <h2 className="text-xl font-bold mb-4">Recent Incidents</h2>
        {overview.recent_incidents.length === 0 ? (
          <p className="text-center py-4 text-gray-500">No recent incidents</p>
        ) : (
          <div className="space-y-3">
            {overview.recent_incidents.map((incident: MerchantIncident) => (
              <div key={incident.incident_id} className="border-b pb-3 last:border-b-0">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-medium">{incident.incident_id}</h3>
                    <p className="text-sm text-gray-500">
                      {new Date(incident.detection_timestamp).toLocaleString()}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      incident.severity === 'HIGH' ? 'bg-red-100 text-red-800' :
                      incident.severity === 'MEDIUM' ? 'bg-orange-100 text-orange-800' :
                      'bg-yellow-100 text-yellow-800'
                    }`}>
                      {incident.severity}
                    </span>
                    <Link
                      to={`/merchant/incidents/${incident.incident_id}`}
                      className="mt-2 block text-sm text-blue-600 hover:text-blue-800"
                    >
                      View Incident
                    </Link>
                  </div>
                </div>
                <div className="mt-2 text-sm text-gray-600">
                  <span className="mr-3">{incident.affected_segment.payment_method}</span>
                  <span className="mr-3">{incident.affected_segment.bank}</span>
                  <span>{incident.affected_segment.device}</span>
                </div>
                <div className="mt-1">
                  <span className="text-red-500 font-medium">
                    {((incident.success_rate_evidence?.current_success_rate || 0) - (incident.success_rate_evidence?.baseline_success_rate || 0)) * 100}% change
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default MerchantDashboard;