import React from 'react';
import { FundData } from '../types/fund';

interface Props {
  funds: FundData[];
}

const HeadlineStats: React.FC<Props> = ({ funds }) => {
  // Calculate statistics
  const totalFunds = funds.length;
  const lofFunds = funds.filter(f => f.valuation > 0);
  const lofCount = lofFunds.length;

  // Count funds by limit status
  const suspendedFunds = funds.filter(f => f.limitText === '暂停').length;
  const limitedFunds = funds.filter(f => f.limitText.startsWith('限') && f.limitText !== '暂停').length;
  const openFunds = funds.filter(f => f.limitText === '不限').length;

  // Calculate premium rates for LOF funds
  const avgPremium = lofCount > 0
    ? lofFunds.reduce((sum, f) => sum + f.premiumRate, 0) / lofCount
    : 0;

  // Count rising/falling LOF funds
  const risingLOF = lofFunds.filter(f => f.valuationRate > 0).length;
  const fallingLOF = lofFunds.filter(f => f.valuationRate < 0).length;

  const stats = [
    { label: '总基金数', value: totalFunds, color: 'text-gray-900' },
    { label: 'LOF基金', value: lofCount, color: 'text-blue-600' },
    { label: '暂停申购', value: suspendedFunds, color: 'text-red-600' },
    { label: '限制申购', value: limitedFunds, color: 'text-orange-600' },
    { label: '开放申购', value: openFunds, color: 'text-green-600' },
    { label: 'LOF平均溢价', value: `${avgPremium >= 0 ? '+' : ''}${avgPremium.toFixed(2)}%`, color: avgPremium >= 0 ? 'text-red-600' : 'text-green-600' },
    { label: 'LOF上涨', value: risingLOF, color: 'text-red-600' },
    { label: 'LOF下跌', value: fallingLOF, color: 'text-green-600' },
  ];

  return (
    <div className="bg-gradient-to-r from-gray-50 to-white border-b border-gray-200 px-4 py-3">
      <div className="grid grid-cols-4 gap-3">
        {stats.map((stat, index) => (
          <div key={index} className="flex flex-col">
            <span className="text-[10px] text-gray-500 leading-tight">{stat.label}</span>
            <span className={`text-sm font-semibold ${stat.color} leading-tight`}>{stat.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default HeadlineStats;
