import { Link } from 'react-router-dom';

const Navbar: React.FC = () => {
  return (
    <nav className="bg-primary p-4">
      <div className="max-w-7xl mx-auto flex justify-between items-center">
        <div className="flex space-x-4">
          <Link to="/merchant" className="text-surface hover:text-surface/80">
            Merchant Dashboard
          </Link>
          <Link to="/support" className="text-surface hover:text-surface/80">
            Support Console
          </Link>
          <Link to="/approvals" className="text-surface hover:text-surface/80">
            Approval Queue
          </Link>
        </div>
        <div className="text-surface font-medium">
          DegradeWatch
        </div>
      </div>
    </nav>
  );
};

export default Navbar;