export const formatRate = (rate: number, includeSign: boolean = false): string => {
  const sign = includeSign && rate > 0 ? '+' : '';
  return `${sign}${rate.toFixed(2)}%`;
};

// Chinese market color logic: Red = Up, Green = Down
export const getRateColor = (rate: number): string => {
  if (rate > 0) return 'text-[#ea3323]'; // Bright Red
  if (rate < 0) return 'text-[#1aa656]'; // Green
  return 'text-gray-500';
};

export const getRateColorClass = (rate: number): string => {
  if (rate > 0) return 'text-[#ea3323]';
  if (rate < 0) return 'text-[#1aa656]';
  return 'text-gray-500';
};