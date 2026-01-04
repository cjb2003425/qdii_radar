import React, { useState, useRef } from 'react';
import { Plus, X, Search, Trash2, CheckSquare, Square, AlertCircle, Check } from 'lucide-react';
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
        className="fixed bottom-6 right-6 sm:bottom-8 sm:right-8 bg-indigo-600 hover:bg-indigo-700 text-white p-4 rounded-full shadow-glow transition-all duration-200 z-50 flex items-center justify-center hover:scale-110 active:scale-95 safe-area-bottom"
        title="管理基金"
        style={{ minWidth: '56px', minHeight: '56px' }}
      >
        <Plus size={28} className="sm:w-8 sm:h-8" strokeWidth={2.5} />
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-2 sm:p-4 safe-area-all backdrop-blur-sm">
      <div className="bg-white rounded-2xl w-full max-w-lg sm:max-w-2xl max-h-[90vh] overflow-hidden shadow-2xl flex flex-col border border-slate-200/60">
        {/* Header */}
        <div className="bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-700 text-white px-3 py-2.5 sm:px-4 sm:py-3 shrink-0 relative overflow-hidden">
          {/* Decorative background element */}
          <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full blur-2xl -mr-10 -mt-10 pointer-events-none"></div>

          <div className="flex justify-between items-center gap-2 relative z-10">
            <div className="min-w-0 flex-1">
              <h2 className="text-base sm:text-lg font-bold truncate flex items-center gap-2">
                <Search size={18} className="sm:w-5 sm:h-5" strokeWidth={2} />
                基金管理
              </h2>
              <p className="text-white/80 text-[10px] sm:text-xs mt-0.5">共 {allFunds.length} 只基金</p>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-white hover:bg-white/20 rounded-full p-1.5 transition-all hover:scale-110 active:scale-95 min-w-[40px] min-h-[40px] sm:min-w-[44px] sm:min-h-[44px] flex items-center justify-center shrink-0"
            >
              <X size={20} className="sm:w-5 sm:h-5" strokeWidth={2} />
            </button>
          </div>
        </div>

        <div className="p-2.5 sm:p-4 overflow-y-auto flex-1 bg-slate-50/30">
          {/* Add Fund Form */}
          <div className="mb-3 sm:mb-4 bg-white p-2.5 sm:p-3 rounded-xl border border-slate-200 shadow-soft">
            <h3 className="text-xs sm:text-sm font-bold text-slate-800 mb-2 flex items-center gap-1.5">
              <Plus size={14} className="sm:w-4 sm:h-4" strokeWidth={2.5} />
              添加新基金
            </h3>

            <form onSubmit={handleAddFund} className="space-y-2">
              <div className="relative">
                <div className="flex gap-1.5 sm:gap-2">
                  <div className="relative flex-1">
                    <input
                      ref={inputRef}
                      type="text"
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      placeholder="输入6位基金代码"
                      className="w-full px-2.5 py-2 sm:px-3 sm:py-2.5 pr-9 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm sm:text-base bg-white transition-all"
                      maxLength={6}
                      disabled={loading}
                    />
                    {isLookingUp && (
                      <div className="absolute right-2.5 top-1/2 -translate-y-1/2">
                        <svg className="animate-spin h-4 w-4 sm:h-5 sm:w-5 text-indigo-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                      </div>
                    )}
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white px-3 py-2 sm:px-4 sm:py-2.5 rounded-lg text-xs sm:text-sm font-semibold transition-all duration-200 disabled:from-slate-400 disabled:to-slate-500 disabled:cursor-not-allowed min-h-[40px] sm:min-h-[44px] min-w-[60px] sm:min-w-[80px] flex items-center justify-center gap-1.5 shrink-0 shadow-md hover:shadow-lg active:scale-95"
                  >
                    {loading && (
                      <svg className="animate-spin h-3.5 w-3.5 sm:h-4 sm:w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                    )}
                    <span className="hidden sm:inline">{isLookingUp ? '查找中...' : loading ? '添加中...' : '添加'}</span>
                    <span className="sm:hidden">{isLookingUp ? '...' : loading ? '...' : '添加'}</span>
                  </button>
                </div>
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-2.5 py-1.5 sm:px-3 sm:py-2 rounded-lg text-[10px] sm:text-xs">
                  <div className="flex items-start gap-1.5">
                    <AlertCircle size={14} className="sm:w-4 sm:h-4 shrink-0 mt-0.5" strokeWidth={2} />
                    <span className="flex-1 whitespace-pre-line">{error}</span>
                  </div>
                </div>
              )}

              {successMessage && (
                <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 px-2.5 py-1.5 sm:px-3 sm:py-2 rounded-lg text-[10px] sm:text-xs">
                  <div className="flex items-center gap-1.5">
                    <Check size={14} className="sm:w-4 sm:h-4 shrink-0" strokeWidth={2.5} />
                    <span className="flex-1">{successMessage}</span>
                  </div>
                </div>
              )}
            </form>
          </div>

          {/* All Funds List */}
          {allFunds.length > 0 && (
            <div>
              <div className="flex justify-between items-center mb-2 sm:mb-3 gap-2">
                <h3 className="text-xs sm:text-sm font-bold text-slate-800">基金列表</h3>
                <div className="flex gap-1.5 sm:gap-2">
                  {!isBatchMode && (
                    <button
                      onClick={() => setIsBatchMode(true)}
                      className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-2 py-1.5 sm:px-3 sm:py-2 rounded-lg text-[10px] sm:text-xs font-semibold transition-colors min-h-[36px] sm:min-h-[44px] active:scale-95"
                    >
                      批量管理
                    </button>
                  )}
                  {isBatchMode && (
                    <>
                      <button
                        onClick={handleSelectAll}
                        className="bg-indigo-100 hover:bg-indigo-200 text-indigo-700 px-2 py-1.5 sm:px-3 sm:py-2 rounded-lg text-[10px] sm:text-xs font-semibold transition-colors min-h-[36px] sm:min-h-[44px] active:scale-95"
                      >
                        {selectedFunds.size === allFunds.length ? '取消全选' : '全选'}
                      </button>
                      <button
                        onClick={() => {
                          setIsBatchMode(false);
                          setSelectedFunds(new Set());
                        }}
                        className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-2 py-1.5 sm:px-3 sm:py-2 rounded-lg text-[10px] sm:text-xs font-semibold transition-colors min-h-[36px] sm:min-h-[44px] active:scale-95"
                      >
                        取消
                      </button>
                    </>
                  )}
                </div>
              </div>

              {isBatchMode && selectedFunds.size > 0 && (
                <div className="mb-2 sm:mb-3 bg-indigo-50 border border-indigo-200 rounded-xl p-2 flex justify-between items-center gap-2 shadow-sm">
                  <span className="text-indigo-700 text-[10px] sm:text-xs font-semibold flex items-center gap-1">
                    <CheckSquare size={12} className="sm:w-4 sm:h-4" strokeWidth={2.5} />
                    已选择 {selectedFunds.size} 只基金
                  </span>
                  <button
                    onClick={handleBatchDelete}
                    className="bg-gradient-to-r from-red-500 to-rose-600 hover:from-red-600 hover:to-rose-700 text-white px-2 py-1.5 sm:px-3 sm:py-2 rounded-lg text-[10px] sm:text-xs font-semibold transition-all min-h-[36px] sm:min-h-[44px] shrink-0 shadow-md hover:shadow-lg active:scale-95"
                  >
                    删除选中
                  </button>
                </div>
              )}

              <div className="grid gap-1.5 sm:gap-2">
                {allFunds.map((fund) => (
                  <div
                    key={fund.code}
                    className={`bg-white border rounded-xl p-2 sm:p-2.5 transition-all shadow-sm hover:shadow-md ${
                      selectedFunds.has(fund.code) ? 'border-indigo-500 ring-2 ring-indigo-100' : 'border-slate-200 hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center gap-1.5 sm:gap-2">
                      {isBatchMode && (
                        <div className="relative shrink-0">
                          {selectedFunds.has(fund.code) ? (
                            <CheckSquare size={18} className="text-indigo-600" strokeWidth={2.5} />
                          ) : (
                            <Square size={18} className="text-slate-400" strokeWidth={2} />
                          )}
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1">
                          <span className="text-xs sm:text-sm font-bold text-slate-800 truncate">{fund.name}</span>
                          {fund.isUserAdded && (
                            <span className="bg-indigo-100 text-indigo-700 text-[9px] sm:text-xs px-1 py-0.5 sm:px-1.5 sm:py-0.5 rounded-full font-bold shrink-0">自定义</span>
                          )}
                        </div>
                        <div className="text-[10px] sm:text-xs text-slate-500 font-mono">{fund.code}</div>
                      </div>
                      {!isBatchMode && (
                        <button
                          onClick={() => handleRemoveFund(fund.code, fund.isUserAdded || false)}
                          className="text-red-500 hover:text-red-700 hover:bg-red-50 p-1.5 sm:p-2 rounded-lg transition-all shrink-0 active:scale-95"
                          title="删除基金"
                          style={{ minWidth: '36px', minHeight: '36px' }}
                        >
                          <Trash2 size={14} className="sm:w-4 sm:h-4" strokeWidth={2} />
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