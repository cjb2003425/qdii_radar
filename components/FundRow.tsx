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
      <div className="w-[22%] sm:w-[18%] flex flex-col justify-center overflow-hidden">
        <span className="text-[#2c68a8] font-medium text-[15px] leading-tight truncate" title={fund.name}>{fund.name}</span>
        <span className="text-[#2c68a8] text-xs mt-0.5">{fund.code}</span>
      </div>

      {/* Column 2: Valuation */}
      <div className="w-[17%] sm:w-[18%] flex flex-col items-center justify-center text-center">
        <span className="text-gray-900 text-[15px] font-medium leading-tight">{fund.valuation.toFixed(4)}</span>
        <span className={`${getRateColorClass(fund.valuationRate)} text-xs mt-0.5 scale-90`}>
          ({formatRate(fund.valuationRate)})
        </span>
      </div>

      {/* Column 3: Premium Rate - Center Highlight */}
      <div className="w-[14%] sm:w-[14%] flex items-center justify-center">
        <span className={`${getRateColorClass(fund.premiumRate)} font-bold text-[15px]`}>
          {formatRate(fund.premiumRate)}
        </span>
      </div>

      {/* Column 4: Market Price */}
      <div className="w-[17%] sm:w-[18%] flex flex-col items-center justify-center text-center">
        <span className="text-gray-900 text-[15px] font-medium leading-tight">{fund.marketPrice.toFixed(3)}</span>
        <span className={`${getRateColorClass(fund.marketPriceRate)} text-xs mt-0.5 scale-90`}>
          ({formatRate(fund.marketPriceRate)})
        </span>
      </div>

      {/* Column 5: Limit (New) */}
      <div className="w-[18%] sm:w-[16%] flex items-center justify-center text-center">
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

      {/* Column 6: Toggle */}
      <div className="w-[12%] sm:w-[16%] flex items-center justify-end pr-1">
        <button 
          onClick={() => onToggle(fund.id)}
          className={`
            w-10 h-6 rounded-full transition-colors duration-200 ease-in-out relative border-2 focus:outline-none
            ${fund.isWatchlisted ? 'bg-blue-500 border-blue-500' : 'bg-white border-gray-200'}
          `}
        >
          <span 
            className={`
              absolute top-0.5 left-0.5 w-4 h-4 rounded-full shadow-sm transition-transform duration-200
              ${fund.isWatchlisted ? 'translate-x-4 bg-white' : 'bg-gray-100'}
            `}
          />
        </button>
      </div>
    </div>
  );
};

export default FundRow;