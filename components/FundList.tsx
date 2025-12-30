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
  onTriggerChange?: () => void;
}

const FundList: React.FC<Props> = ({ funds, currentPage, onToggle, onDelete, onToggleMonitoring, onTriggerChange }) => {
  // Exchange-traded funds: funds with real-time trading prices (valuation > 0)
  // This includes both LOF (Listed Open-End Fund) and ETF (Exchange Traded Fund)
  const lofFunds = funds.filter(f => f.valuation > 0);
  const regularFunds = funds.filter(f => f.valuation === 0);
  const nasdaqFunds = funds.filter(f => f.name.includes('纳指') || f.name.includes('纳斯达克'));

  // Determine which funds to display based on current page
  const displayFunds =
    currentPage === 'lof' ? lofFunds :
    currentPage === 'nasdaq' ? nasdaqFunds :
    funds;

  return (
    <div className="flex-1 overflow-y-auto pb-4 bg-white">
      {/* Header Row */}
      <div className="flex items-center px-2 py-2 bg-gray-50 text-gray-500 text-xs border-b border-gray-200 sticky top-0 z-10">
        <div className="w-[30%] sm:w-[25%] flex items-center gap-0.5">
          基金名称 <Icons.ArrowDown className="w-3 h-3" />
        </div>
        <div className="w-[15%] sm:w-[16%] flex items-center justify-center gap-0.5 text-center leading-tight">
          价格 <Icons.ArrowDown className="w-3 h-3 hidden sm:block" />
        </div>
        <div className="w-[15%] sm:w-[16%] flex items-center justify-center text-center leading-tight">
          净值
        </div>
        <div className="w-[15%] sm:w-[16%] flex items-center justify-center text-center leading-tight">
          溢价率
        </div>
        <div className="w-[15%] sm:w-[16%] flex items-center justify-center text-center">
          限额
        </div>
        <div className="w-[10%] sm:w-[11%] flex items-center justify-center text-center">
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
                <FundRow key={fund.id} fund={fund} onToggle={onToggle} onDelete={onDelete} onToggleMonitoring={onToggleMonitoring} onTriggerChange={onTriggerChange} />
              ))}
            </div>
          )}

          {/* Regular Funds Section */}
          <div className="flex flex-col">
            {regularFunds.map((fund) => (
              <FundRow key={fund.id} fund={fund} onToggle={onToggle} onDelete={onDelete} onToggleMonitoring={onToggleMonitoring} onTriggerChange={onTriggerChange} />
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
              <FundRow key={fund.id} fund={fund} onToggle={onToggle} onDelete={onDelete} onToggleMonitoring={onToggleMonitoring} onTriggerChange={onTriggerChange} />
            ))}
          </div>
        </>
      )}

      {/* NASDAQ Funds Page */}
      {currentPage === 'nasdaq' && (
        <>
          {/* Page indicator */}
          <div className="px-2 py-1.5 bg-green-100 text-green-800 text-xs font-semibold flex items-center justify-between">
            <span className="flex items-center gap-1">
              <span className="inline-block w-1.5 h-1.5 bg-green-600 rounded-full"></span>
              纳斯达克指数基金 ({nasdaqFunds.length}只)
            </span>
          </div>

          {/* NASDAQ Funds */}
          <div className="flex flex-col">
            {displayFunds.map((fund) => (
              <FundRow key={fund.id} fund={fund} onToggle={onToggle} onDelete={onDelete} onToggleMonitoring={onToggleMonitoring} onTriggerChange={onTriggerChange} />
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default FundList;