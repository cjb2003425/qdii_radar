import { UserFund } from '../types/fund';
import { PRESET_FUNDS } from '../data/funds';

const USER_FUNDS_KEY = 'user_funds';
const INITIALIZED_KEY = 'funds_initialized';

export const initializeFunds = (): void => {
  const initialized = localStorage.getItem(INITIALIZED_KEY);
  if (!initialized) {
    const initialFunds: UserFund[] = PRESET_FUNDS.map(fund => ({
      ...fund,
      addedAt: new Date().toISOString()
    }));
    localStorage.setItem(USER_FUNDS_KEY, JSON.stringify(initialFunds));
    localStorage.setItem(INITIALIZED_KEY, 'true');
    console.log('初始化预设基金:', initialFunds.length);
  }
};

export const getUserFunds = (): UserFund[] => {
  try {
    const stored = localStorage.getItem(USER_FUNDS_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
};

export const addUserFund = (code: string, name: string): UserFund => {
  const userFunds = getUserFunds();
  
  // 检查是否已经存在
  if (userFunds.some(fund => fund.code === code)) {
    throw new Error('Fund already exists');
  }
  
  const newUserFund: UserFund = {
    code,
    name,
    addedAt: new Date().toISOString()
  };
  
  userFunds.push(newUserFund);
  localStorage.setItem(USER_FUNDS_KEY, JSON.stringify(userFunds));
  
  return newUserFund;
};

export const removeUserFund = (code: string): boolean => {
  const userFunds = getUserFunds();
  const filteredFunds = userFunds.filter(fund => fund.code !== code);
  
  if (filteredFunds.length === userFunds.length) {
    return false; // Fund not found
  }
  
  localStorage.setItem(USER_FUNDS_KEY, JSON.stringify(filteredFunds));
  return true;
};

export const isUserFund = (code: string): boolean => {
  const userFunds = getUserFunds();
  return userFunds.some(fund => fund.code === code);
};

export const canAddUserFund = (code: string, allPresetCodes: string[]): boolean => {
  const userFunds = getUserFunds();
  const allVisibleCodes = new Set([...allPresetCodes, ...userFunds.map(f => f.code)]);
  return !allVisibleCodes.has(code);
};