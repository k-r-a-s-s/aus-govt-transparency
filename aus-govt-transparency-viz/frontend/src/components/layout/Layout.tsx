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
    { path: '/gifts-travel', label: 'Gifts & Travel' },
    { path: '/geographic', label: 'Geographic View' },
    { path: '/export', label: 'Export' },
  ];
  
  return (
    <div className="min-h-screen flex flex-col bg-gray-100">
      {/* Header */}
      <header className="bg-blue-800 text-white shadow-md">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <svg 
              xmlns="http://www.w3.org/2000/svg" 
              className="h-8 w-8" 
              viewBox="0 0 20 20" 
              fill="currentColor"
            >
              <path 
                fillRule="evenodd" 
                d="M10 2a8 8 0 100 16 8 8 0 000-16zm0 14a6 6 0 110-12 6 6 0 010 12z" 
                clipRule="evenodd" 
              />
              <path d="M10 4a1 1 0 00-1 1v4a1 1 0 001 1h3a1 1 0 100-2h-2V5a1 1 0 00-1-1z" />
            </svg>
            <h1 className="text-xl font-bold">Australian Government Transparency Dashboard</h1>
          </div>
          
          <div className="hidden md:flex items-center space-x-4">
            <a 
              href="https://github.com/your-repo/aus-govt-transparency" 
              target="_blank" 
              rel="noopener noreferrer"
              className="hover:text-blue-200 transition-colors"
            >
              GitHub
            </a>
            <a 
              href="/about" 
              className="hover:text-blue-200 transition-colors"
            >
              About
            </a>
          </div>
        </div>
      </header>
      
      {/* Navigation */}
      <nav className="bg-white shadow-md">
        <div className="container mx-auto px-4">
          <div className="flex overflow-x-auto py-2">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`px-4 py-2 mx-1 rounded-md whitespace-nowrap ${
                  location.pathname === item.path
                    ? 'bg-blue-100 text-blue-800 font-medium'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      </nav>
      
      {/* Main content */}
      <main className="flex-grow container mx-auto px-4 py-6">
        {children}
      </main>
      
      {/* Footer */}
      <footer className="bg-gray-800 text-white">
        <div className="container mx-auto px-4 py-6">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="mb-4 md:mb-0">
              <p>© 2023 Australian Government Transparency Project</p>
            </div>
            <div className="flex space-x-4">
              <a 
                href="/privacy" 
                className="hover:text-blue-300 transition-colors"
              >
                Privacy Policy
              </a>
              <a 
                href="/terms" 
                className="hover:text-blue-300 transition-colors"
              >
                Terms of Use
              </a>
              <a 
                href="/contact" 
                className="hover:text-blue-300 transition-colors"
              >
                Contact
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Layout; 