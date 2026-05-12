import { UserFund } from '../types/fund';
import { PRESET_FUNDS } from '../data/funds';

const PRESET_FUND_CODES = new Set(PRESET_FUNDS.map(fund => fund.code));
const USER_FUNDS_KEY = '***';
const INITIALIZED_KEY = '***';

export const initializeFunds = (): void => {
  const initialized = localStorage.getItem(INITIALIZED_KEY);
  if (!initialized) {
    localStorage.setItem(USER_FUNDS_KEY, JSON.stringify([]));
    localStorage.setItem(INITIALIZED_KEY, 'true');
    console.log('初始化自定义基金列表为空');
  }
};

export const getUserFunds = (): UserFund[] => {
  try {
    const stored = localStorage.getItem(USER_FUNDS_KEY);
    if (!stored) return [];

    const parsed = JSON.parse(stored);
    if (!Array.isArray(parsed)) return [];

    const migrated = parsed.filter((fund: UserFund) => !PRESET_FUND_CODES.has(fund.code));
    if (migrated.length !== parsed.length) {
      localStorage.setItem(USER_FUNDS_KEY, JSON.stringify(migrated));
      console.log(`清理本地预设基金镜像: ${parsed.length - migrated.length} 条`);
    }

    return migrated;
  } catch {
    return [];
  }
};

export const addUserFund = (code: string, name: string): UserFund => {
  const userFunds = getUserFunds();

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
    return false;
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

export const isPresetFundCode = (code: string): boolean => PRESET_FUND_CODES.has(code);
