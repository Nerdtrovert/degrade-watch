import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { supportAPI } from '../../api/support';

const SupportEvidenceDetail: React.FC = () => {
  const { incidentId } = useParams<{ incidentId: string }>();
  const [evidence, setEvidence] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchEvidence = async () => {
      try {
        setLoading(true);
        const response = await supportAPI.getEvidence(incidentId!);
        setEvidence(response.data);
        setError(null);
      } catch (err: any) {
        console.error('Failed to fetch evidence:', err);
        if (err.response?.status === 404) {
          setError('Evidence not found');
        } else {
          setError('Failed to load evidence');
        }
      } finally {
        setLoading(false);
      }
    };

    if (incidentId) {
      fetchEvidence();
    }
  }, [incidentId]);

  if (loading) {
    return <div className="text-center py-12">Loading...</div>;
  }

  if (error) {
    return <div className="text-center py-12 text-red-500">{error}</div>;
  }

  if (!evidence) {
    return <div className="text-center py-12">No evidence data available</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-start mb-4">
        <h1 className="text-2xl font-bold">Evidence Details</h1>
        <Link
          to={`/support/incidents/${incidentId}`}
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          ← Back to Incident
        </Link>
      </div>

      <div className="bg-white p-6 rounded-lg shadow">
        {/* We'll display the evidence in a readable format */}
        <div className="space-y-4">
          <div>
            <h2 className="text-xl font-bold mb-2">Evidence Package</h2>
            <p className="text-sm text-gray-500 mb-2">
              Incident ID: {evidence.incident_metadata?.incident_id || 'N/A'}
            </p>
          </div>

          {/* We can break down the evidence into sections, but for now we'll show the raw JSON in a readable way */}
          {/* In a real app, we would format this nicely, but for the MVP we'll show a preformatted JSON */}
          <div className="bg-gray-50 p-4 rounded overflow-auto">
            <pre className="text-sm">{JSON.stringify(evidence, null, 2)}</pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SupportEvidenceDetail;