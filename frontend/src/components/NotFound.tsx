import { Navigate } from 'react-router-dom';

const NotFound: React.FC = () => {
  const accessToken = localStorage.getItem('access_token');

  if (!accessToken) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="text-center py-12 text-slate-500 font-medium">
      404 - Page Not Found
    </div>
  );
};

export default NotFound;