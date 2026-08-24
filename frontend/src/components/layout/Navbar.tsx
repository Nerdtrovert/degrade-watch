import { Link, useNavigate } from 'react-router-dom';

const Navbar: React.FC = () => {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    navigate('/login');
  };

  return (
    <nav className="bg-blue-800 p-4 text-white">
      <div className="max-w-7xl mx-auto flex justify-between items-center">
        <div className="flex space-x-6 items-center">
          <div className="font-bold text-xl mr-4">
            DegradeWatch
          </div>
          <Link to="/merchant" className="hover:text-gray-300">
            Merchant
          </Link>
          <Link to="/support" className="hover:text-gray-300">
            Support
          </Link>
          <Link to="/approvals" className="hover:text-gray-300">
            Approvals
          </Link>
        </div>
        <div>
          {localStorage.getItem('access_token') ? (
            <button 
              onClick={handleLogout}
              className="px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-sm font-medium"
            >
              Logout
            </button>
          ) : (
            <Link to="/login" className="px-3 py-1 bg-green-600 hover:bg-green-700 rounded text-sm font-medium">
              Login
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
