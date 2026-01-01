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

  // Debug: Log when monitoring state changes
  React.useEffect(() => {
    if (fund.monitoringEnabled) {
      console.log(`✅ Settings icon should be visible for fund ${fund.code} (${fund.name})`);
    }
  }, [fund.monitoringEnabled, fund.code, fund.name]);

  return (
    <>
      <div className="flex items-center py-2.5 px-2 bg-white border-b border-gray-100 text-sm hover:bg-gray-50 transition-colors">
        {/* Column 1: Name & Code */}
        <div className="w-[24%] sm:w-[25%] flex flex-col justify-center overflow-hidden">
          <div className="flex items-center gap-1">
            <span className="text-[#2c68a8] font-medium text-[13px] sm:text-[15px] leading-tight truncate" title={fund.name}>{fund.name}</span>
            {onDelete && (
              <button
                onClick={() => onDelete(fund.id)}
                className="text-red-500 hover:text-red-700 text-xs ml-1 min-w-[20px] min-h-[20px] flex items-center justify-center"
                title="删除此基金"
              >
                ✕
              </button>
            )}
          </div>
          <span className="text-[#2c68a8] text-[10px] sm:text-xs mt-0.5">{fund.code}</span>
        </div>

        {/* Column 2: Price (场内价格 for LOF funds, or previous close NAV for regular funds) */}
        <div className="w-[13.5%] sm:w-[16%] flex flex-col items-center justify-center text-center">
          {fund.valuation > 0 ? (
            <>
              <span className="text-gray-900 text-[13px] sm:text-[15px] font-medium leading-tight">{fund.valuation.toFixed(4)}</span>
              <span className={`${getRateColorClass(fund.valuationRate)} text-[11px] sm:text-xs mt-0.5 font-medium`}>
                {formatRate(fund.valuationRate, true)}
              </span>
            </>
          ) : (
            <span className="text-gray-400 text-xs sm:text-sm">—</span>
          )}
        </div>

        {/* Column 3: NAV (最新净值) */}
        <div className="w-[13.5%] sm:w-[16%] flex flex-col items-center justify-center text-center">
          {fund.marketPrice > 0 ? (
            <>
              <span className="text-gray-900 text-[13px] sm:text-[15px] font-medium leading-tight">{fund.marketPrice.toFixed(4)}</span>
              <span className={`${getRateColorClass(fund.marketPriceRate)} text-[11px] sm:text-xs mt-0.5 font-medium`}>
                {formatRate(fund.marketPriceRate, true)}
              </span>
            </>
          ) : (
            <span className="text-gray-400 text-xs sm:text-sm">—</span>
          )}
        </div>

        {/* Column 4: Premium Rate */}
        <div className="w-[13%] sm:w-[16%] flex flex-col items-center justify-center text-center">
          {(fund.valuation > 0 && fund.marketPrice > 0) ? (
            <span className={`${getRateColorClass(fund.premiumRate)} text-[13px] sm:text-[15px] font-medium leading-tight`}>
              {formatRate(fund.premiumRate, true)}
            </span>
          ) : (
            <span className="text-gray-400 text-xs sm:text-sm">—</span>
          )}
        </div>

        {/* Column 5: Purchase Limit */}
        <div className="w-[13%] sm:w-[16%] flex items-center justify-center text-center">
          {fund.limitText ? (
            <span className={`text-[10px] sm:text-xs px-1 sm:px-1.5 py-0.5 rounded ${
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
        <div className="w-[23%] sm:w-[11%] flex items-center justify-center gap-0.5 flex-shrink-0">
          {onToggleMonitoring && (
            <>
              <label className="relative inline-flex items-center cursor-pointer flex-shrink-0">
                <input
                  type="checkbox"
                  className="sr-only peer"
                  checked={fund.monitoringEnabled || false}
                  onChange={(e) => onToggleMonitoring(fund.id, e.target.checked)}
                />
                <div className="w-9 h-5 sm:w-11 sm:h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 sm:after:h-5 sm:after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              </label>
              {fund.monitoringEnabled && (
                <button
                  onClick={() => {
                    console.log(`🔧 Settings button clicked for ${fund.code}`);
                    setShowTriggerSettings(!showTriggerSettings);
                  }}
                  className="text-blue-600 hover:text-blue-800 hover:bg-blue-100 active:bg-blue-200 rounded flex items-center justify-center transition-all flex-shrink-0"
                  style={{ width: '34px', height: '42px' }}
                  title="配置触发器"
                  aria-label="配置触发器"
                >
                  <svg className="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
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