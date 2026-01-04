import React, { useState } from 'react';
import { Fund } from '../types';
import { Settings, X } from 'lucide-react';
import FundTriggerSettings from './FundTriggerSettings';
import { FundData } from '../types/fund';

interface FundRowProps {
  fund: Fund;
  onDelete: (id: string) => void;
  onToggle: (id: string) => void;
}

const getLimitBadgeStyle = (status: string) => {
  switch (status) {
    case 'warning': return 'bg-orange-50 text-orange-600 border-orange-100';
    case 'danger': return 'bg-red-50 text-red-600 border-red-100';
    case 'neutral': return 'bg-slate-100 text-slate-600 border-slate-200';
    default: return 'bg-slate-50 text-slate-500 border-slate-200';
  }
};

const formatPercent = (val: number) => {
  const sign = val > 0 ? '+' : '';
  return `${sign}${val.toFixed(2)}%`;
};

const getColor = (val: number) => {
  if (val > 0) return 'text-up';
  if (val < 0) return 'text-down';
  return 'text-slate-500';
};

const getBgColor = (val: number) => {
  if (val > 0) return 'bg-red-50';
  if (val < 0) return 'bg-green-50';
  return 'bg-slate-50';
}

export const FundRow: React.FC<FundRowProps> = ({ fund, onDelete, onToggle }) => {
  const [showTriggerSettings, setShowTriggerSettings] = useState(false);

  // Convert Fund to FundData format for FundTriggerSettings
  const fundData: FundData = {
    id: fund.code,
    code: fund.code,
    name: fund.name,
    valuation: fund.price,
    valuationRate: fund.priceChangePercent,
    marketPrice: fund.netValue,
    marketPriceRate: fund.netValueChangePercent,
    premiumRate: fund.premiumRate,
    limitText: fund.limitTag || '—',
    isWatchlisted: false,
  };

  return (
    <>
      {/* Trigger Settings Modal */}
      {showTriggerSettings && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <FundTriggerSettings
              fund={fundData}
              onClose={() => setShowTriggerSettings(false)}
            />
          </div>
        </div>
      )}
      {/* Desktop View (Table Row) */}
      <tr className="hidden md:table-row border-b border-slate-50 hover:bg-slate-50/80 transition-colors group last:border-0">
        <td className="py-2.5 px-4 align-middle">
          <div className="flex items-center gap-3">
            <div className={`w-1 h-8 rounded-full ${fund.isMonitorEnabled ? 'bg-indigo-500' : 'bg-slate-200'}`}></div>
            <div className="max-w-[220px]">
              <div className="font-semibold text-slate-700 text-[14px] truncate cursor-pointer hover:text-indigo-600 transition-colors" title={fund.name}>
                {fund.name}
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xs font-mono text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">{fund.code}</span>
                {fund.limitTag && (
                  <span className={`px-1.5 py-0.5 rounded-[4px] text-[10px] font-medium border ${getLimitBadgeStyle(fund.limitStatus)}`}>
                    {fund.limitTag}
                  </span>
                )}
              </div>
            </div>
          </div>
        </td>
        <td className="py-2.5 px-4 align-middle">
          <div className="flex flex-col">
            <span className="font-bold text-slate-700 font-mono tracking-tight tabular-nums text-[14px]">{fund.price.toFixed(4)}</span>
            <span className={`text-[11px] font-semibold font-mono tabular-nums mt-0.5 ${getColor(fund.priceChangePercent)}`}>
              {formatPercent(fund.priceChangePercent)}
            </span>
          </div>
        </td>
        <td className="py-2.5 px-4 align-middle">
          <div className="flex flex-col">
            <span className="font-medium text-slate-600 font-mono tracking-tight tabular-nums text-[14px]">{fund.netValue.toFixed(4)}</span>
            <span className={`text-[11px] font-medium font-mono tabular-nums mt-0.5 ${getColor(fund.netValueChangePercent)}`}>
              {formatPercent(fund.netValueChangePercent)}
            </span>
          </div>
        </td>
        <td className="py-2.5 px-4 align-middle">
          <div className={`inline-flex items-center px-2 py-0.5 rounded-md text-[13px] font-bold font-mono tabular-nums ${getBgColor(fund.premiumRate)} ${getColor(fund.premiumRate)}`}>
            {formatPercent(fund.premiumRate)}
          </div>
        </td>
        <td className="py-2.5 px-4 align-middle">
          <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
             <button 
              onClick={() => onToggle(fund.id)}
              className={`p-1.5 rounded-full hover:bg-slate-100 transition-colors ${fund.isMonitorEnabled ? 'text-indigo-600' : 'text-slate-400'}`}
              title="Toggle Monitor"
            >
              <div className={`w-2.5 h-2.5 rounded-full ${fund.isMonitorEnabled ? 'bg-indigo-600' : 'bg-slate-300'}`}></div>
            </button>
            {fund.hasSettings && (
              <button
                onClick={() => setShowTriggerSettings(true)}
                className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-full transition-colors"
                title="触发器设置"
              >
                <Settings size={16} />
              </button>
            )}
            <button 
              onClick={() => onDelete(fund.id)}
              className="p-1.5 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-full transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        </td>
      </tr>

      {/* Mobile View (Compact Card) */}
      <div className="md:hidden bg-white rounded-xl p-2.5 border border-slate-100 shadow-sm relative overflow-hidden active:scale-[0.99] transition-transform duration-150">
        {/* Status Bar */}
        <div className={`absolute left-0 top-0 bottom-0 w-1 ${fund.isMonitorEnabled ? 'bg-indigo-500' : 'bg-slate-200'}`}></div>

        <div className="pl-2.5 flex flex-col gap-2">
            {/* Header: Name, Code, Tags, Toggle */}
            <div className="flex justify-between items-start gap-2">
                <div className="min-w-0 flex-1">
                     <div className="font-bold text-slate-800 text-[13px] leading-tight truncate pr-1">{fund.name}</div>
                     <div className="flex items-center flex-wrap gap-1 mt-1">
                        <span className="text-[9px] text-slate-400 font-mono bg-slate-50 px-1 py-0.5 rounded border border-slate-100">{fund.code}</span>
                        {fund.limitTag && (
                          <span className={`px-1 py-0.5 rounded text-[8px] leading-none font-medium border ${getLimitBadgeStyle(fund.limitStatus)}`}>
                            {fund.limitTag}
                          </span>
                        )}
                     </div>
                </div>
                {/* Compact Controls */}
                <div className="flex items-center gap-1.5 flex-shrink-0">
                    {fund.hasSettings && (
                      <button
                        onClick={() => setShowTriggerSettings(true)}
                        className="text-slate-400 active:text-indigo-600 p-1.5 -m-1.5 rounded-full hover:bg-slate-100 active:bg-indigo-50 transition-colors"
                        title="触发器设置"
                      >
                        <Settings size={15} />
                      </button>
                    )}
                    <button
                        onClick={() => onToggle(fund.id)}
                        className={`w-10 h-5.5 rounded-full p-0.5 transition-colors duration-200 ease-in-out relative flex-shrink-0 ${fund.isMonitorEnabled ? 'bg-indigo-500' : 'bg-slate-300'} active:scale-95`}
                    >
                        <div className={`bg-white w-4.5 h-4.5 rounded-full shadow-md transform transition-transform duration-200 ease-in-out ${fund.isMonitorEnabled ? 'translate-x-4.5' : 'translate-x-0'}`}></div>
                    </button>
                </div>
            </div>

            {/* Compact Data Grid */}
            <div className="grid grid-cols-3 gap-1.5 bg-slate-50/80 rounded-lg p-1.5 border border-slate-100">
                 {/* Price */}
                 <div className="flex flex-col">
                    <span className="text-[8px] text-slate-400 mb-0.5">现价</span>
                    <div className="flex flex-col leading-none">
                        <span className="font-bold text-slate-700 font-mono text-[13px]">{fund.price.toFixed(4)}</span>
                        <span className={`text-[9px] font-bold mt-0.5 ${getColor(fund.priceChangePercent)}`}>{formatPercent(fund.priceChangePercent)}</span>
                    </div>
                 </div>

                 {/* Net Value */}
                 <div className="flex flex-col pl-1.5 border-l border-slate-200">
                    <span className="text-[8px] text-slate-400 mb-0.5">净值</span>
                    <div className="flex flex-col leading-none">
                        <span className="font-medium text-slate-600 font-mono text-[13px]">{fund.netValue.toFixed(4)}</span>
                        <span className={`text-[9px] font-medium mt-0.5 ${getColor(fund.netValueChangePercent)}`}>{formatPercent(fund.netValueChangePercent)}</span>
                    </div>
                 </div>

                 {/* Premium */}
                 <div className="flex flex-col items-end pl-1.5 border-l border-slate-200">
                    <span className="text-[8px] text-slate-400 mb-0.5">溢价率</span>
                     <div className={`font-bold font-mono text-[13px] mt-0.5 ${getColor(fund.premiumRate)}`}>{formatPercent(fund.premiumRate)}</div>
                 </div>
            </div>
        </div>
      </div>
    </>
  );
};