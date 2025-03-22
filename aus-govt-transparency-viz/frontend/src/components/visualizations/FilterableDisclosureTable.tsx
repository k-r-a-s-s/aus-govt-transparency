import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { DisclosureData } from '../../types';
import PDFViewer from '../common/PDFViewer';
import SimplePDFViewer from '../common/SimplePDFViewer';

interface FilterableDisclosureTableProps {
  data: DisclosureData[];
  mpName: string;
}

const FilterableDisclosureTable: React.FC<FilterableDisclosureTableProps> = ({ data, mpName }) => {
  // State for filters
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [subcategoryFilter, setSubcategoryFilter] = useState<string>('');
  const [dateFilter, setDateFilter] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [sortField, setSortField] = useState<keyof DisclosureData>('declaration_date');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(10);
  const [selectedPdfUrl, setSelectedPdfUrl] = useState<string | null>(null);
  const [isPdfModalOpen, setIsPdfModalOpen] = useState(false);
  const [useSimpleViewer, setUseSimpleViewer] = useState(false);
  
  // Reset pagination when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [categoryFilter, subcategoryFilter, dateFilter, searchTerm]);
  
  // Get unique categories
  const categories = useMemo(() => {
    const categorySet = new Set<string>();
    data.forEach(disclosure => {
      if (disclosure.category) {
        categorySet.add(disclosure.category);
      }
    });
    return Array.from(categorySet).sort();
  }, [data]);
  
  // Get unique subcategories (filter by selected category if applicable)
  const subcategories = useMemo(() => {
    const subcategorySet = new Set<string>();
    data.forEach(disclosure => {
      if (disclosure.sub_category && (!categoryFilter || disclosure.category === categoryFilter)) {
        subcategorySet.add(disclosure.sub_category);
      }
    });
    return Array.from(subcategorySet).sort();
  }, [data, categoryFilter]);
  
  // Get unique years
  const years = useMemo(() => {
    const yearSet = new Set<string>();
    data.forEach(disclosure => {
      if (disclosure.declaration_date) {
        const year = new Date(disclosure.declaration_date).getFullYear().toString();
        yearSet.add(year);
      }
    });
    return Array.from(yearSet).sort().reverse();
  }, [data]);
  
  // Filter data based on filters
  const filteredData = useMemo(() => {
    return data.filter(disclosure => {
      // Filter by category
      const categoryMatch = categoryFilter 
        ? disclosure.category === categoryFilter 
        : true;
      
      // Filter by subcategory
      const subcategoryMatch = subcategoryFilter 
        ? disclosure.sub_category === subcategoryFilter 
        : true;
      
      // Filter by year
      const yearMatch = dateFilter 
        ? new Date(disclosure.declaration_date).getFullYear().toString() === dateFilter 
        : true;
      
      // Search term filter (case insensitive)
      const searchMatch = searchTerm 
        ? (
            (disclosure.item && disclosure.item.toLowerCase().includes(searchTerm.toLowerCase())) ||
            (disclosure.entity && disclosure.entity.toLowerCase().includes(searchTerm.toLowerCase())) ||
            (disclosure.details && disclosure.details.toLowerCase().includes(searchTerm.toLowerCase())) ||
            (disclosure.sub_category && disclosure.sub_category.toLowerCase().includes(searchTerm.toLowerCase()))
          )
        : true;
      
      return categoryMatch && subcategoryMatch && yearMatch && searchMatch;
    });
  }, [data, categoryFilter, subcategoryFilter, dateFilter, searchTerm]);
  
  // Sort data based on sort field and direction
  const sortedData = useMemo(() => {
    return [...filteredData].sort((a, b) => {
      const aValue = a[sortField];
      const bValue = b[sortField];
      
      if (aValue === bValue) return 0;
      
      // Handle undefined values
      if (aValue === undefined) return sortDirection === 'asc' ? -1 : 1;
      if (bValue === undefined) return sortDirection === 'asc' ? 1 : -1;
      
      // Sort strings
      if (typeof aValue === 'string' && typeof bValue === 'string') {
        return sortDirection === 'asc' 
          ? aValue.localeCompare(bValue) 
          : bValue.localeCompare(aValue);
      }
      
      // Sort dates
      if (sortField === 'declaration_date') {
        const aDate = new Date(aValue as string).getTime();
        const bDate = new Date(bValue as string).getTime();
        return sortDirection === 'asc' ? aDate - bDate : bDate - aDate;
      }
      
      // Sort everything else
      return sortDirection === 'asc' 
        ? (aValue > bValue ? 1 : -1)
        : (bValue > aValue ? 1 : -1);
    });
  }, [filteredData, sortField, sortDirection]);
  
  // Paginate data
  const paginatedData = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    return sortedData.slice(startIndex, startIndex + itemsPerPage);
  }, [sortedData, currentPage, itemsPerPage]);
  
  // Calculate total pages
  const totalPages = Math.ceil(sortedData.length / itemsPerPage);
  
  // Handle sort click
  const handleSort = (field: keyof DisclosureData) => {
    if (field === sortField) {
      // Toggle direction if clicking the same field
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      // Set new field and default to descending (newest first for dates)
      setSortField(field);
      setSortDirection(field === 'declaration_date' ? 'desc' : 'asc');
    }
  };
  
  // Render sort indicator
  const renderSortIndicator = (field: keyof DisclosureData) => {
    if (field !== sortField) return null;
    
    return sortDirection === 'asc' 
      ? <span className="ml-1">↑</span> 
      : <span className="ml-1">↓</span>;
  };
  
  // Pagination controls
  const paginate = (pageNumber: number) => {
    setCurrentPage(pageNumber);
    // Scroll to top of table
    window.scrollTo({ top: window.scrollY - 200, behavior: 'smooth' });
  };
  
  const goToFirstPage = () => paginate(1);
  const goToLastPage = () => paginate(totalPages);
  const goToPreviousPage = () => paginate(Math.max(1, currentPage - 1));
  const goToNextPage = () => paginate(Math.min(totalPages, currentPage + 1));
  
  const handleOpenPdf = (pdfUrl: string, useSimple: boolean = false) => {
    setSelectedPdfUrl(`${import.meta.env.VITE_API_URL}/pdf/${pdfUrl}`);
    setUseSimpleViewer(useSimple);
    setIsPdfModalOpen(true);
  };

  const handleClosePdf = () => {
    setIsPdfModalOpen(false);
    // Optional: clear the URL after a short delay to allow the modal to close gracefully
    setTimeout(() => {
      setSelectedPdfUrl(null);
      setUseSimpleViewer(false);
    }, 300);
  };
  
  return (
    <div className="filterable-disclosure-table">
      <h2 className="text-2xl font-bold mb-6">All Disclosures for {mpName}</h2>
      
      {/* Filters */}
      <div className="mb-6 grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Category filter */}
        <div>
          <label htmlFor="category-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Category
          </label>
          <select
            id="category-filter"
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setSubcategoryFilter(''); // Reset subcategory when category changes
            }}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          >
            <option value="">All Categories</option>
            {categories.map(category => (
              <option key={category} value={category}>{category}</option>
            ))}
          </select>
        </div>
        
        {/* Subcategory filter */}
        <div>
          <label htmlFor="subcategory-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Subcategory
          </label>
          <select
            id="subcategory-filter"
            value={subcategoryFilter}
            onChange={(e) => setSubcategoryFilter(e.target.value)}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            disabled={subcategories.length === 0}
          >
            <option value="">All Subcategories</option>
            {subcategories.map(subcategory => (
              <option key={subcategory} value={subcategory}>{subcategory}</option>
            ))}
          </select>
        </div>
        
        {/* Year filter */}
        <div>
          <label htmlFor="date-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Year
          </label>
          <select
            id="date-filter"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          >
            <option value="">All Years</option>
            {years.map(year => (
              <option key={year} value={year}>{year}</option>
            ))}
          </select>
        </div>
        
        {/* Search filter */}
        <div>
          <label htmlFor="search-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Search
          </label>
          <input
            id="search-filter"
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search in item, entity, or details..."
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          />
        </div>
      </div>
      
      {/* Results summary */}
      <div className="mb-4 text-sm text-gray-600">
        Showing {sortedData.length > 0 ? (currentPage - 1) * itemsPerPage + 1 : 0} to {Math.min(currentPage * itemsPerPage, sortedData.length)} of {sortedData.length} disclosures
      </div>
      
      {/* Table */}
      <div className="overflow-x-auto bg-white shadow rounded-lg mb-6">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th 
                scope="col" 
                className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer"
                onClick={() => handleSort('declaration_date')}
              >
                Date {renderSortIndicator('declaration_date')}
              </th>
              <th 
                scope="col" 
                className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer"
                onClick={() => handleSort('category')}
              >
                Category {renderSortIndicator('category')}
              </th>
              <th 
                scope="col" 
                className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer"
                onClick={() => handleSort('sub_category')}
              >
                Subcategory {renderSortIndicator('sub_category')}
              </th>
              <th 
                scope="col" 
                className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer w-1/5"
                onClick={() => handleSort('item')}
              >
                Item {renderSortIndicator('item')}
              </th>
              <th 
                scope="col" 
                className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer"
                onClick={() => handleSort('entity')}
              >
                Entity {renderSortIndicator('entity')}
              </th>
              <th 
                scope="col" 
                className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-1/4"
              >
                Details
              </th>
              <th 
                scope="col" 
                className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Source
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {paginatedData.length > 0 ? (
              paginatedData.map((disclosure) => (
                <tr key={disclosure.id} className="hover:bg-gray-50">
                  <td className="px-3 py-3 whitespace-nowrap text-sm text-gray-500">
                    {new Date(disclosure.declaration_date).toLocaleDateString()}
                  </td>
                  <td className="px-3 py-3 whitespace-nowrap text-sm text-gray-500">
                    {disclosure.category}
                  </td>
                  <td className="px-3 py-3 whitespace-nowrap text-sm text-gray-500">
                    {disclosure.sub_category || 'N/A'}
                  </td>
                  <td className="px-3 py-3 text-sm text-gray-500 break-words">
                    <div className="line-clamp-2 hover:line-clamp-none">
                      {disclosure.item || 'N/A'}
                    </div>
                  </td>
                  <td className="px-3 py-3 text-sm text-gray-500">
                    {disclosure.entity || 'N/A'}
                  </td>
                  <td className="px-3 py-3 text-sm text-gray-500">
                    <div className="line-clamp-3 hover:line-clamp-none">
                      {disclosure.details || 'No details available'}
                    </div>
                  </td>
                  <td className="px-3 py-3 whitespace-nowrap text-sm text-gray-500">
                    {disclosure.pdf_url ? (
                      <div className="flex items-center space-x-2">
                        <button 
                          onClick={() => handleOpenPdf(disclosure.pdf_url)}
                          className="text-blue-600 hover:text-blue-900"
                        >
                          View PDF
                        </button>
                        <button
                          onClick={() => handleOpenPdf(disclosure.pdf_url, true)}
                          className="text-xs text-gray-500 hover:text-gray-700"
                          title="Use simple viewer if advanced viewer doesn't work"
                        >
                          (simple)
                        </button>
                      </div>
                    ) : 'No PDF'}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className="px-3 py-4 text-sm text-gray-500 text-center">
                  No disclosures found matching the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      
      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 bg-white border border-gray-200 rounded-lg sm:px-6">
          <div className="flex justify-between sm:hidden w-full">
            <button
              onClick={goToPreviousPage}
              disabled={currentPage === 1}
              className={`relative inline-flex items-center px-4 py-2 text-sm font-medium rounded-md ${
                currentPage === 1
                ? 'text-gray-300 bg-gray-50 cursor-not-allowed'
                : 'text-gray-700 bg-white hover:bg-gray-50'
              }`}
            >
              Previous
            </button>
            <div className="inline-flex items-center text-sm text-gray-700">
              Page {currentPage} of {totalPages}
            </div>
            <button
              onClick={goToNextPage}
              disabled={currentPage === totalPages}
              className={`relative inline-flex items-center px-4 py-2 text-sm font-medium rounded-md ${
                currentPage === totalPages
                ? 'text-gray-300 bg-gray-50 cursor-not-allowed'
                : 'text-gray-700 bg-white hover:bg-gray-50'
              }`}
            >
              Next
            </button>
          </div>
          <div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-gray-700">
                Showing <span className="font-medium">{sortedData.length > 0 ? (currentPage - 1) * itemsPerPage + 1 : 0}</span> to <span className="font-medium">{Math.min(currentPage * itemsPerPage, sortedData.length)}</span> of <span className="font-medium">{sortedData.length}</span> results
              </p>
            </div>
            <div>
              <nav className="inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                <button
                  onClick={goToFirstPage}
                  disabled={currentPage === 1}
                  className={`relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium ${
                    currentPage === 1
                    ? 'text-gray-300 cursor-not-allowed'
                    : 'text-gray-500 hover:bg-gray-50'
                  }`}
                >
                  <span className="sr-only">First</span>
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M15.707 15.707a1 1 0 01-1.414 0l-5-5a1 1 0 010-1.414l5-5a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
                    <path fillRule="evenodd" d="M8.707 15.707a1 1 0 01-1.414 0l-5-5a1 1 0 010-1.414l5-5a1 1 0 111.414 1.414L4.414 10l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
                  </svg>
                </button>
                <button
                  onClick={goToPreviousPage}
                  disabled={currentPage === 1}
                  className={`relative inline-flex items-center px-2 py-2 border border-gray-300 bg-white text-sm font-medium ${
                    currentPage === 1
                    ? 'text-gray-300 cursor-not-allowed'
                    : 'text-gray-500 hover:bg-gray-50'
                  }`}
                >
                  <span className="sr-only">Previous</span>
                  <svg className="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                </button>
                
                {/* Page numbers */}
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  // Show pages around current page
                  let pageNum;
                  if (totalPages <= 5) {
                    pageNum = i + 1;
                  } else if (currentPage <= 3) {
                    pageNum = i + 1;
                  } else if (currentPage >= totalPages - 2) {
                    pageNum = totalPages - 4 + i;
                  } else {
                    pageNum = currentPage - 2 + i;
                  }
                  
                  return (
                    <button
                      key={pageNum}
                      onClick={() => paginate(pageNum)}
                      className={`relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium ${
                        currentPage === pageNum
                        ? 'z-10 bg-indigo-50 border-indigo-500 text-indigo-600'
                        : 'text-gray-500 hover:bg-gray-50'
                      }`}
                    >
                      {pageNum}
                    </button>
                  );
                })}
                
                <button
                  onClick={goToNextPage}
                  disabled={currentPage === totalPages}
                  className={`relative inline-flex items-center px-2 py-2 border border-gray-300 bg-white text-sm font-medium ${
                    currentPage === totalPages
                    ? 'text-gray-300 cursor-not-allowed'
                    : 'text-gray-500 hover:bg-gray-50'
                  }`}
                >
                  <span className="sr-only">Next</span>
                  <svg className="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                  </svg>
                </button>
                <button
                  onClick={goToLastPage}
                  disabled={currentPage === totalPages}
                  className={`relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium ${
                    currentPage === totalPages
                    ? 'text-gray-300 cursor-not-allowed'
                    : 'text-gray-500 hover:bg-gray-50'
                  }`}
                >
                  <span className="sr-only">Last</span>
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M4.293 15.707a1 1 0 001.414 0l5-5a1 1 0 000-1.414l-5-5a1 1 0 00-1.414 1.414L8.586 10 4.293 14.293a1 1 0 000 1.414z" clipRule="evenodd" />
                    <path fillRule="evenodd" d="M11.293 15.707a1 1 0 001.414 0l5-5a1 1 0 000-1.414l-5-5a1 1 0 00-1.414 1.414L15.586 10l-4.293 4.293a1 1 0 000 1.414z" clipRule="evenodd" />
                  </svg>
                </button>
              </nav>
            </div>
          </div>
        </div>
      )}
      
      {/* PDF Viewer */}
      {selectedPdfUrl && !useSimpleViewer && (
        <PDFViewer 
          url={selectedPdfUrl} 
          isOpen={isPdfModalOpen} 
          onClose={handleClosePdf}
          filename={selectedPdfUrl.split('/').pop() || 'Document'}
          onError={() => setUseSimpleViewer(true)}
        />
      )}
      
      {/* Simple PDF Viewer */}
      {selectedPdfUrl && useSimpleViewer && (
        <SimplePDFViewer
          url={selectedPdfUrl} 
          isOpen={isPdfModalOpen} 
          onClose={handleClosePdf}
          filename={selectedPdfUrl.split('/').pop() || 'Document'}
        />
      )}
    </div>
  );
};

export default FilterableDisclosureTable; 