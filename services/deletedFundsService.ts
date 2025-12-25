const DELETED_FUNDS_KEY = 'deleted_funds';

export const getDeletedFunds = (): Set<string> => {
  try {
    const stored = localStorage.getItem(DELETED_FUNDS_KEY);
    const deletedArray = stored ? JSON.parse(stored) : [];
    return new Set(deletedArray);
  } catch {
    return new Set();
  }
};

export const addDeletedFund = (code: string): void => {
  const deletedFunds = getDeletedFunds();
  deletedFunds.add(code);
  localStorage.setItem(DELETED_FUNDS_KEY, JSON.stringify(Array.from(deletedFunds)));
};

export const removeDeletedFund = (code: string): void => {
  const deletedFunds = getDeletedFunds();
  deletedFunds.delete(code);
  localStorage.setItem(DELETED_FUNDS_KEY, JSON.stringify(Array.from(deletedFunds)));
};

export const isFundDeleted = (code: string): boolean => {
  const deletedFunds = getDeletedFunds();
  return deletedFunds.has(code);
};

export const clearAllDeletedFunds = (): void => {
  localStorage.removeItem(DELETED_FUNDS_KEY);
};