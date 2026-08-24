import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { supportAPI } from '../../api/support';

const SupportAuditDetail: React.FC = () => {
  const { incidentId } = useParams<{ incidentId: string }>();
  const [audit, setAudit] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchAudit = async () => {
      try {
        setLoading(true);
        const response = await supportAPI.getAudit(incidentId!);
        setAudit(response.data);
        setError(null);
      } catch (err: any) {
        console.error('Failed to fetch audit:', err);
        if (err.response?.status === 404) {
          setError('Audit trail not found');
        } else {
          setError('Failed to load audit trail');
        }
      } finally {
        setLoading(false);
      }
    };

    if (incidentId) {
      fetchAudit();
    }
  }, [incidentId]);

  if (loading) {
    return <div className="text-center py-12">Loading...</div>;
  }

  if (error) {
    return <div className="text-center py-12 text-red-500">{error}</div>;
  }

  if (!audit || !audit.audit_trail) {
    return <div className="text-center py-12">No audit trail data available</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-start mb-4">
        <h1 className="text-2xl font-bold">Audit Trail</h1>
        <Link
          to={`/support/incidents/${incidentId}`}
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          ← Back to Incident
        </Link>
      </div>

      <div className="bg-white p-6 rounded-lg shadow">
        <div className="space-y-4">
          <div>
            <h2 className="bg-slate-100 border-b border-slate-200 px-4 py-3 font-bold text-sm text-slate-700 uppercase tracking-wider">Audit Trail for Incident</h2>
            <p className="text-sm text-gray-500 mb-2">
              Incident ID: {audit.audit_trail.length > 0 ? audit.audit_trail[0].incident_id || 'N/A' : 'N/A'}
            </p>
          </div>

          {/* Display audit events in a timeline */}
          <div className="space-y-4">
            {audit.audit_trail.map((event: any, index: number) => (
              <div key={index} className="border-l-2 border-blue-500 pl-4">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="text-lg font-medium">{event.action}</h3>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    event.success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}>
                    {event.state}
                  </span>
                </div>
                <p className="text-sm text-gray-500">
                  {new Date(event.timestamp || 0).toLocaleString()}
                </p>
                {!event.success && event.error_message && (
                  <p className="mt-1 text-sm text-red-600">
                    Error: {event.error_message}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SupportAuditDetail;