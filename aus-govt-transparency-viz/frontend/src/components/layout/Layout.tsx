import React, { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';

interface LayoutProps {
  children: ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();
  
  // Navigation items
  const navItems = [
    { path: '/', label: 'Dashboard' },
    { path: '/analytics', label: 'Analytics' },
    { path: '/entities', label: 'Entities' },
    { path: '/travel', label: 'Travel Analysis' },
    { path: '/geographic', label: 'Geographic View' },
    { path: '/export', label: 'Export' },
  ];
  
  return (
    <div className="min-h-screen flex flex-col bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <div className="flex items-center">
            <Link to="/" className="flex items-center">
              <span className="text-2xl font-bold text-gray-800">AusParlDisclosures</span>
            </Link>
            <span className="ml-2 text-sm bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">Beta</span>
          </div>
          <div className="flex items-center space-x-4">
            <a 
              href="https://github.com/username/aus-govt-transparency" 
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-600 hover:text-gray-900"
            >
              <svg className="h-6 w-6" fill="currentColor" viewBox="0 0 24 24">
                <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.162 6.839 9.49.5.092.682-.217.682-.48v-1.68c-2.782.603-3.369-1.338-3.369-1.338-.454-1.152-1.11-1.459-1.11-1.459-.907-.619.07-.608.07-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.088 2.912.832.091-.646.35-1.087.636-1.337-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.03-2.682-.103-.253-.446-1.27.098-2.646 0 0 .84-.269 2.75 1.022A9.578 9.578 0 0112 6.832c.85.004 1.705.114 2.504.336 1.909-1.291 2.747-1.022 2.747-1.022.546 1.376.202 2.394.1 2.646.64.699 1.026 1.591 1.026 2.682 0 3.841-2.337 4.687-4.565 4.934.359.31.678.92.678 1.852v2.747c0 .264.18.574.688.476C19.138 20.16 22 16.416 22 12c0-5.523-4.477-10-10-10z"></path>
              </svg>
            </a>
            <Link to="/about" className="text-blue-600 hover:text-blue-800">About</Link>
          </div>
        </div>
      </header>
      
      {/* Navigation */}
      <nav className="bg-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-12">
            <div className="flex items-center">
              <div className="flex space-x-4">
                {navItems.map(item => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={`
                      px-3 py-2 rounded-md text-sm font-medium
                      ${location.pathname === item.path
                        ? 'bg-gray-900 text-white'
                        : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                      }
                    `}
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </nav>
      
      {/* Main Content */}
      <main className="flex-grow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </div>
      </main>
      
      {/* Footer */}
      <footer className="bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="text-gray-500 text-sm">
              &copy; {new Date().getFullYear()} Australian Government Transparency Project
            </div>
            <div className="flex space-x-4 mt-4 md:mt-0">
              <Link to="/privacy" className="text-gray-500 hover:text-gray-700 text-sm">Privacy Policy</Link>
              <Link to="/terms" className="text-gray-500 hover:text-gray-700 text-sm">Terms of Use</Link>
              <Link to="/contact" className="text-gray-500 hover:text-gray-700 text-sm">Contact</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Layout; 