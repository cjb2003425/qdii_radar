import React from 'react';
import { FundData } from '../types';
import { getRateColorClass, formatRate } from '../utils/format';

interface Props {
  fund: FundData;
  onToggle: (id: string) => void;
}

const FundRow: React.FC<Props> = ({ fund, onToggle }) => {
  const isLimitRestricted = fund.limitText && (fund.limitText.includes('暂停') || fund.limitText.includes('限'));

  return (
    <div className="flex items-center py-3 px-2 bg-white border-b border-gray-100 text-sm hover:bg-gray-50 transition-colors">
      {/* Column 1: Name & Code */}
      <div className="w-[28%] sm:w-[25%] flex flex-col justify-center overflow-hidden">
        <span className="text-[#2c68a8] font-medium text-[15px] leading-tight truncate" title={fund.name}>{fund.name}</span>
        <span className="text-[#2c68a8] text-xs mt-0.5">{fund.code}</span>
      </div>

      {/* Column 2: Valuation */}
      <div className="w-[24%] sm:w-[25%] flex flex-col items-center justify-center text-center">
        <span className="text-gray-900 text-[15px] font-medium leading-tight">{fund.valuation.toFixed(4)}</span>
        <span className={`${getRateColorClass(fund.valuationRate)} text-xs mt-0.5 scale-90`}>
          ({formatRate(fund.valuationRate)})
        </span>
      </div>

      {/* Column 3: Net Asset Value */}
      <div className="w-[24%] sm:w-[25%] flex flex-col items-center justify-center text-center">
        <span className="text-gray-900 text-[15px] font-medium leading-tight">{fund.valuation.toFixed(4)}</span>
        <span className={`${getRateColorClass(fund.valuationRate)} text-xs mt-0.5 scale-90`}>
          ({formatRate(fund.valuationRate)})
        </span>
      </div>

      {/* Column 4: Purchase Limit */}
      <div className="w-[24%] sm:w-[25%] flex items-center justify-center text-center">
        {fund.limitText ? (
          <span className={`text-xs px-1.5 py-0.5 rounded ${
            fund.limitText.includes('暂停') 
              ? 'text-red-600 bg-red-50' 
              : fund.limitText.includes('限') 
                ? 'text-orange-600 bg-orange-50'
                : 'text-gray-500'
          }`}>
            {fund.limitText}
          </span>
        ) : (
          <span className="text-gray-400 text-xs">-</span>
        )}
      </div>
    </div>
  );
};

export default FundRow;