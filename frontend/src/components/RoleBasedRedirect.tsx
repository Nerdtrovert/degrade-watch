import { Navigate } from 'react-router-dom';

const RoleBasedRedirect = () => {
  try {
    const token = localStorage.getItem('access_token');
    if (!token) {
      return <Navigate to="/login" replace />;
    }

    const roles = JSON.parse(localStorage.getItem('user_roles') || '[]');
    if (roles.includes('support')) {
      return <Navigate to="/support" replace />;
    } else if (roles.includes('approver')) {
      return <Navigate to="/approvals" replace />;
    } else {
      return <Navigate to="/merchant" replace />;
    }
  } catch (e) {
    return <Navigate to="/login" replace />;
  }
};

export default RoleBasedRedirect;
