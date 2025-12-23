import React from 'react';
import { FundData } from '../types';
import FundRow from './FundRow';
import { Icons } from './Icon';

interface Props {
  funds: FundData[];
  onToggle: (id: string) => void;
}

const FundList: React.FC<Props> = ({ funds, onToggle }) => {
  return (
    <div className="flex-1 overflow-y-auto pb-4 bg-white">
      {/* Header Row */}
      <div className="flex items-center px-2 py-2 bg-gray-50 text-gray-500 text-xs border-b border-gray-200 sticky top-0 z-10">
        <div className="w-[33%] sm:w-[30%] flex items-center gap-0.5">
          基金名称 <Icons.ArrowDown className="w-3 h-3" />
        </div>
        <div className="w-[33%] sm:w-[30%] flex items-center justify-center gap-0.5 text-center leading-tight">
          估值 <Icons.ArrowDown className="w-3 h-3 hidden sm:block" />
        </div>
        <div className="w-[33%] sm:w-[30%] flex items-center justify-center text-center leading-tight">
          净值
        </div>
        <div className="w-[0%] sm:w-[0%] hidden items-center justify-center text-center">
          限额
        </div>
      </div>

      {/* Rows */}
      <div className="flex flex-col">
        {funds.map((fund) => (
          <FundRow key={fund.id} fund={fund} onToggle={onToggle} />
        ))}
      </div>
    </div>
  );
};

export default FundList;