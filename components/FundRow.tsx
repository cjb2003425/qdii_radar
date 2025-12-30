import React, { useState } from 'react';
import { FundData } from '../types/fund';
import { getRateColorClass, formatRate } from '../utils/format';
import FundTriggerSettings from './FundTriggerSettings';

interface Props {
  fund: FundData;
  onToggle: (id: string) => void;
  onDelete?: (id: string) => void;
  onToggleMonitoring?: (id: string, enabled: boolean) => void;
  onTriggerChange?: () => void;
}

const FundRow: React.FC<Props> = ({ fund, onToggle, onDelete, onToggleMonitoring, onTriggerChange }) => {
  const isLimitRestricted = fund.limitText && (fund.limitText.includes('暂停') || fund.limitText.includes('限'));
  const [showTriggerSettings, setShowTriggerSettings] = useState(false);

  return (
    <>
      <div className="flex items-center py-3 px-2 bg-white border-b border-gray-100 text-sm hover:bg-gray-50 transition-colors">
        {/* Column 1: Name & Code */}
        <div className="w-[30%] sm:w-[25%] flex flex-col justify-center overflow-hidden">
          <div className="flex items-center gap-1">
            <span className="text-[#2c68a8] font-medium text-[15px] leading-tight truncate" title={fund.name}>{fund.name}</span>
            {onDelete && (
              <button
                onClick={() => onDelete(fund.id)}
                className="text-red-500 hover:text-red-700 text-xs ml-1"
                title="删除此基金"
              >
                ✕
              </button>
            )}
          </div>
          <span className="text-[#2c68a8] text-xs mt-0.5">{fund.code}</span>
        </div>

        {/* Column 2: Price (场内价格 for LOF funds, or previous close NAV for regular funds) */}
        <div className="w-[15%] sm:w-[16%] flex flex-col items-center justify-center text-center">
          {fund.valuation > 0 ? (
            <>
              <span className="text-gray-900 text-[15px] font-medium leading-tight">{fund.valuation.toFixed(4)}</span>
              <span className={`${getRateColorClass(fund.valuationRate)} text-xs mt-0.5 font-medium`}>
                {formatRate(fund.valuationRate, true)}
              </span>
            </>
          ) : (
            <span className="text-gray-400 text-sm">—</span>
          )}
        </div>

        {/* Column 3: NAV (最新净值) */}
        <div className="w-[15%] sm:w-[16%] flex flex-col items-center justify-center text-center">
          {fund.marketPrice > 0 ? (
            <>
              <span className="text-gray-900 text-[15px] font-medium leading-tight">{fund.marketPrice.toFixed(4)}</span>
              <span className={`${getRateColorClass(fund.marketPriceRate)} text-xs mt-0.5 font-medium`}>
                {formatRate(fund.marketPriceRate, true)}
              </span>
            </>
          ) : (
            <span className="text-gray-400 text-sm">—</span>
          )}
        </div>

        {/* Column 4: Premium Rate */}
        <div className="w-[15%] sm:w-[16%] flex flex-col items-center justify-center text-center">
          {(fund.valuation > 0 && fund.marketPrice > 0) ? (
            <span className={`${getRateColorClass(fund.premiumRate)} text-[15px] font-medium leading-tight`}>
              {formatRate(fund.premiumRate, true)}
            </span>
          ) : (
            <span className="text-gray-400 text-sm">—</span>
          )}
        </div>

        {/* Column 5: Purchase Limit */}
        <div className="w-[15%] sm:w-[16%] flex items-center justify-center text-center">
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

        {/* Column 6: Monitoring Toggle Switch & Settings */}
        <div className="w-[10%] sm:w-[11%] flex items-center justify-center gap-1">
          {onToggleMonitoring && (
            <>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  className="sr-only peer"
                  checked={fund.monitoringEnabled || false}
                  onChange={(e) => onToggleMonitoring(fund.id, e.target.checked)}
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
              {fund.monitoringEnabled && (
                <button
                  onClick={() => setShowTriggerSettings(!showTriggerSettings)}
                  className="text-blue-500 hover:text-blue-700 text-xl font-medium"
                  title="配置触发器"
                >
                  ⚙
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Trigger Settings Panel */}
      {showTriggerSettings && (
        <FundTriggerSettings
          fund={fund}
          onTriggerChange={onTriggerChange}
          onClose={() => setShowTriggerSettings(false)}
        />
      )}
    </>
  );
};

export default FundRow;