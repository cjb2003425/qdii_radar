import React from 'react';

interface Page {
  id: string;
  label: string;
  count?: number;
}

interface Props {
  currentPage: string;
  pages: Page[];
  onPageChange: (pageId: string) => void;
}

const NavBar: React.FC<Props> = ({ currentPage, pages, onPageChange }) => {
  return (
    <div className="flex items-center gap-2 px-4 py-3 bg-white border-b border-gray-200">
      {pages.map((page) => {
        const isActive = currentPage === page.id;
        return (
          <button
            key={page.id}
            onClick={() => onPageChange(page.id)}
            className={`
              px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
              flex items-center gap-2
              ${isActive
                ? 'bg-blue-600 text-white shadow-md'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }
            `}
          >
            <span>{page.label}</span>
            {page.count !== undefined && (
              <span className={`
                px-2 py-0.5 rounded-full text-xs font-semibold
                ${isActive
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-200 text-gray-600'
                }
              `}>
                {page.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};

export default NavBar;
