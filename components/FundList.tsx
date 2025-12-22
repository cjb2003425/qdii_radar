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
        <div className="w-[22%] sm:w-[18%] flex items-center gap-0.5">
          基金名称 <Icons.ArrowDown className="w-3 h-3" />
        </div>
        <div className="w-[17%] sm:w-[18%] flex items-center justify-center gap-0.5 text-center leading-tight">
          估值 <Icons.ArrowDown className="w-3 h-3 hidden sm:block" />
        </div>
        <div className="w-[14%] sm:w-[14%] flex items-center justify-center gap-0.5">
          溢价 <Icons.ArrowDown className="w-3 h-3 hidden sm:block" />
        </div>
        <div className="w-[17%] sm:w-[18%] flex items-center justify-center text-center leading-tight">
          价格
        </div>
        <div className="w-[18%] sm:w-[16%] flex items-center justify-center text-center">
          限额
        </div>
        <div className="w-[12%] sm:w-[16%] flex items-center justify-end gap-0.5 text-[#2c68a8]">
          自选
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