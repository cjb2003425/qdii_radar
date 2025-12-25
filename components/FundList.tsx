import React from 'react';
import { FundData } from '../types/fund';
import FundRow from './FundRow';
import { Icons } from './Icon';

interface Props {
  funds: FundData[];
  currentPage: string;
  onToggle: (id: string) => void;
  onDelete?: (id: string) => void;
  onToggleMonitoring?: (id: string, enabled: boolean) => void;
}

const FundList: React.FC<Props> = ({ funds, currentPage, onToggle, onDelete, onToggleMonitoring }) => {
  // Separate LOF funds (with real-time valuation) from regular funds
  const lofFunds = funds.filter(f => f.valuation > 0);
  const regularFunds = funds.filter(f => f.valuation === 0);

  // Determine which funds to display based on current page
  const displayFunds = currentPage === 'lof' ? lofFunds : funds;

  return (
    <div className="flex-1 overflow-y-auto pb-4 bg-white">
      {/* Header Row */}
      <div className="flex items-center px-2 py-2 bg-gray-50 text-gray-500 text-xs border-b border-gray-200 sticky top-0 z-10">
        <div className="w-[20%] sm:w-[18%] flex items-center gap-0.5">
          基金名称 <Icons.ArrowDown className="w-3 h-3" />
        </div>
        <div className="w-[17%] sm:w-[17%] flex items-center justify-center gap-0.5 text-center leading-tight">
          估值 <Icons.ArrowDown className="w-3 h-3 hidden sm:block" />
        </div>
        <div className="w-[17%] sm:w-[17%] flex items-center justify-center text-center leading-tight">
          净值
        </div>
        <div className="w-[17%] sm:w-[17%] flex items-center justify-center text-center leading-tight">
          溢价率
        </div>
        <div className="w-[17%] sm:w-[17%] flex items-center justify-center text-center">
          限额
        </div>
        <div className="w-[15%] sm:w-[14%] flex items-center justify-center text-center">
          监控
        </div>
      </div>

      {/* All Funds Page */}
      {currentPage === 'all' && (
        <>
          {/* LOF Funds Section */}
          {lofFunds.length > 0 && (
            <div className="flex flex-col">
              {lofFunds.map((fund) => (
                <FundRow key={fund.id} fund={fund} onToggle={onToggle} onDelete={onDelete} onToggleMonitoring={onToggleMonitoring} />
              ))}
            </div>
          )}

          {/* Regular Funds Section */}
          <div className="flex flex-col">
            {regularFunds.map((fund) => (
              <FundRow key={fund.id} fund={fund} onToggle={onToggle} onDelete={onDelete} onToggleMonitoring={onToggleMonitoring} />
            ))}
          </div>
        </>
      )}

      {/* LOF Funds Only Page */}
      {currentPage === 'lof' && (
        <>
          {/* Page indicator */}
          <div className="px-2 py-1.5 bg-blue-100 text-blue-800 text-xs font-semibold flex items-center justify-between">
            <span className="flex items-center gap-1">
              <span className="inline-block w-1.5 h-1.5 bg-blue-600 rounded-full"></span>
              LOF基金实时行情 ({lofFunds.length}只)
            </span>
          </div>

          {/* LOF Funds */}
          <div className="flex flex-col">
            {displayFunds.map((fund) => (
              <FundRow key={fund.id} fund={fund} onToggle={onToggle} onDelete={onDelete} onToggleMonitoring={onToggleMonitoring} />
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default FundList;