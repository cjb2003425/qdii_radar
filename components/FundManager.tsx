import React, { useState, useRef } from 'react';
import { addUserFund, removeUserFund, getUserFunds, canAddUserFund } from '../services/userFundService';
import { lookupFund, addFundToBackend, deleteFundFromBackend, batchDeleteFundsFromBackend } from '../services/fundApiService';
import { FundData } from '../types/fund';

interface Props {
  onFundAdded?: (code: string, name: string) => void;
  onFundRemoved?: (code: string) => void;
  allFunds?: FundData[];
}

const FundManager: React.FC<Props> = ({ onFundAdded, onFundRemoved, allFunds = [] }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [isLookingUp, setIsLookingUp] = useState(false);
  const [selectedFunds, setSelectedFunds] = useState<Set<string>>(new Set());
  const [isBatchMode, setIsBatchMode] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleAddFund = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccessMessage('');

    const trimmedCode = code.trim();
    
    if (!trimmedCode) {
      setError('请输入基金代码');
      return;
    }

    if (trimmedCode.length !== 6) {
      setError('基金代码必须是6位数字');
      return;
    }

    setLoading(true);
    setIsLookingUp(true);

    try {
      const allPresetCodes = allFunds.map(f => f.code);

      if (!canAddUserFund(trimmedCode, allPresetCodes)) {
        setError(`基金代码 ${trimmedCode} 已经存在，不能重复添加`);
        setLoading(false);
        setIsLookingUp(false);
        return;
      }

      // 从后端获取真实基金名称
      const lookupResult = await lookupFund(trimmedCode);

      // 如果基金未找到，警告用户
      if (!lookupResult.found) {
        setError(`未找到基金代码 ${trimmedCode} 的信息。\n\n这可能是因为：\n• 基金代码不存在\n• 基金已终止或清盘\n• 基金尚未上市`);
        setLoading(false);
        setIsLookingUp(false);
        return;
      }

      const fundName = lookupResult.name;
      const newUserFund = addUserFund(trimmedCode, fundName);

      // 调用后端API将基金添加到funds.json
      const addResult = await addFundToBackend(trimmedCode, fundName);
      if (!addResult.success) {
        console.warn('Failed to add fund to backend, but added to localStorage:', addResult.message);
      }
      
      // 清空输入框，但保持弹窗打开状态，允许连续添加
      setCode('');
      setSuccessMessage(`成功添加: ${fundName}`);
      setError('');
      setLoading(false);
      setIsLookingUp(false);

      // 触发父组件刷新数据，以立即获取新基金的NAV和限额
      onFundAdded?.(newUserFund.code, newUserFund.name);

      // 聚焦回输入框，方便继续输入
      setTimeout(() => {
        inputRef.current?.focus();
      }, 100);
      
      // 3秒后清除成功消息
      setTimeout(() => {
        setSuccessMessage('');
      }, 3000);
      
    } catch (err) {
      console.error('添加基金详细错误:', err);
      if (err instanceof Error) {
        setError(`添加失败: ${err.message}`);
      } else {
        setError('添加失败，请稍后重试');
      }
      setLoading(false);
      setIsLookingUp(false);
    }
  };

  const handleRemoveFund = async (fundCode: string, isUserAdded: boolean) => {
    if (window.confirm(`确定要删除基金 ${fundCode} 吗？`)) {
      // 调用后端API从funds.json和监控数据库中删除
      const deleteResult = await deleteFundFromBackend(fundCode);

      // 从localStorage删除（无论后端是否成功）
      removeUserFund(fundCode);

      // 如果后端删除失败，警告用户
      if (!deleteResult.success) {
        setError(`⚠️ 基金 ${fundCode} 仅从前端删除。后端服务器可能未运行，刷新页面后基金可能重新出现。请确保后端服务运行后再删除。`);
        setTimeout(() => setError(''), 5000);
      }

      onFundRemoved?.(fundCode);
    }
  };

  const handleToggleSelect = (fundCode: string) => {
    const newSelected = new Set(selectedFunds);
    if (newSelected.has(fundCode)) {
      newSelected.delete(fundCode);
    } else {
      newSelected.add(fundCode);
    }
    setSelectedFunds(newSelected);
  };

  const handleSelectAll = () => {
    const currentFundCodes = allFunds.map(f => f.code);
    if (selectedFunds.size === currentFundCodes.length && currentFundCodes.every(code => selectedFunds.has(code))) {
      setSelectedFunds(new Set());
    } else {
      setSelectedFunds(new Set(currentFundCodes));
    }
  };

  const handleBatchDelete = async () => {
    if (selectedFunds.size === 0) return;

    if (window.confirm(`确定要删除选中的 ${selectedFunds.size} 只基金吗？`)) {
      const fundCodes = Array.from(selectedFunds);

      // 从localStorage删除所有选中的基金
      fundCodes.forEach(fundCode => {
        removeUserFund(fundCode);
        onFundRemoved?.(fundCode);
      });

      // 调用后端API批量删除（并行执行）
      await batchDeleteFundsFromBackend(fundCodes);

      setSelectedFunds(new Set());
      setIsBatchMode(false);
    }
  };

  const userFunds = getUserFunds();

  const displayFunds = allFunds.map(fund => ({
    ...fund,
    isUserAdded: userFunds.some(uf => uf.code === fund.code)
  }));

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 sm:bottom-8 sm:right-8 bg-[#ea3323] hover:bg-[#c42b1E] text-white p-4 rounded-full shadow-lg transition-all duration-200 z-50 flex items-center justify-center hover:scale-110 safe-area-bottom"
        title="管理基金"
        style={{ minWidth: '56px', minHeight: '56px' }}
      >
        <svg className="w-7 h-7 sm:w-8 sm:h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 safe-area-all">
      <div className="bg-white rounded-lg w-full max-w-2xl max-h-[90vh] overflow-hidden shadow-2xl flex flex-col">
        {/* Header */}
        <div className="bg-gradient-to-r from-[#ea3323] to-[#c42b1E] text-white px-4 py-3 shrink-0">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-base sm:text-lg font-bold">基金管理</h2>
              <p className="text-white/80 text-[11px] sm:text-xs mt-0.5">共 {allFunds.length} 只基金</p>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-white hover:bg-white/20 rounded-full p-1.5 transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <div className="p-3 sm:p-4 overflow-y-auto flex-1">
          {/* Add Fund Form */}
          <div className="mb-4 bg-gray-50 p-3 rounded-lg border border-gray-200">
            <h3 className="text-sm font-semibold text-gray-900 mb-2">添加新基金</h3>

            <form onSubmit={handleAddFund} className="space-y-2">
              <div className="relative">
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <input
                      ref={inputRef}
                      type="text"
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      placeholder="输入6位基金代码"
                      className="w-full px-3 py-2.5 pr-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#ea3323] focus:border-transparent text-base"
                      maxLength={6}
                      disabled={loading}
                    />
                    {isLookingUp && (
                      <div className="absolute right-3 top-1/2 -translate-y-1/2">
                        <svg className="animate-spin h-5 w-5 text-[#ea3323]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                      </div>
                    )}
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="bg-[#ea3323] hover:bg-[#c42b1E] text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors duration-200 disabled:bg-gray-400 min-h-[44px] min-w-[80px] flex items-center justify-center gap-2"
                  >
                    {loading && (
                      <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                    )}
                    {isLookingUp ? '查找中...' : loading ? '添加中...' : '添加'}
                  </button>
                </div>
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg text-xs">
                  <div className="flex items-center">
                    <svg className="w-4 h-4 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    {error}
                  </div>
                </div>
              )}

              {successMessage && (
                <div className="bg-green-50 border border-green-200 text-green-700 px-3 py-2 rounded-lg text-xs">
                  <div className="flex items-center">
                    <svg className="w-4 h-4 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    {successMessage}
                  </div>
                </div>
              )}
            </form>
          </div>

          {/* All Funds List */}
          {allFunds.length > 0 && (
            <div>
              <div className="flex justify-between items-center mb-3">
                <h3 className="text-sm font-semibold text-gray-900">基金列表</h3>
                <div className="flex gap-2">
                  {!isBatchMode && (
                    <button
                      onClick={() => setIsBatchMode(true)}
                      className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-2 rounded-lg text-xs font-medium transition-colors min-h-[36px] sm:min-h-[44px]"
                    >
                      批量管理
                    </button>
                  )}
                  {isBatchMode && (
                    <>
                      <button
                        onClick={handleSelectAll}
                        className="bg-blue-100 hover:bg-blue-200 text-blue-700 px-3 py-2 rounded-lg text-xs font-medium transition-colors min-h-[36px] sm:min-h-[44px]"
                      >
                        {selectedFunds.size === allFunds.length ? '取消全选' : '全选'}
                      </button>
                      <button
                        onClick={() => {
                          setIsBatchMode(false);
                          setSelectedFunds(new Set());
                        }}
                        className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-2 rounded-lg text-xs font-medium transition-colors min-h-[36px] sm:min-h-[44px]"
                      >
                        取消
                      </button>
                    </>
                  )}
                </div>
              </div>

              {isBatchMode && selectedFunds.size > 0 && (
                <div className="mb-3 bg-blue-50 border border-blue-200 rounded-lg p-2.5 flex justify-between items-center">
                  <span className="text-blue-700 text-xs font-medium">已选择 {selectedFunds.size} 只基金</span>
                  <button
                    onClick={handleBatchDelete}
                    className="bg-red-500 hover:bg-red-600 text-white px-3 py-2 rounded-lg text-xs font-medium transition-colors min-h-[36px] sm:min-h-[44px]"
                  >
                    删除选中
                  </button>
                </div>
              )}

              <div className="grid gap-2">
                {allFunds.map((fund) => (
                  <div
                    key={fund.code}
                    className={`bg-white border rounded-lg p-2.5 transition-all ${
                      selectedFunds.has(fund.code) ? 'border-blue-500 ring-2 ring-blue-100' : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {isBatchMode && (
                        <input
                          type="checkbox"
                          checked={selectedFunds.has(fund.code)}
                          onChange={() => handleToggleSelect(fund.code)}
                          className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                        />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-semibold text-gray-900 truncate">{fund.name}</span>
                          {fund.isUserAdded && (
                            <span className="bg-blue-100 text-blue-700 text-xs px-1.5 py-0.5 rounded-full font-medium shrink-0">自定义</span>
                          )}
                        </div>
                        <div className="text-xs text-gray-500">代码: {fund.code}</div>
                      </div>
                      {!isBatchMode && (
                        <button
                          onClick={() => handleRemoveFund(fund.code, fund.isUserAdded || false)}
                          className="text-red-500 hover:text-red-700 hover:bg-red-50 p-2 rounded-lg transition-colors shrink-0"
                          title="删除基金"
                          style={{ minWidth: '40px', minHeight: '40px' }}
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default FundManager;