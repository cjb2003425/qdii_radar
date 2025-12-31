import React, { useState } from 'react';
import { API_CONFIG } from '../config/api';
import { addUserFund, removeUserFund, getUserFunds, canAddUserFund } from '../services/userFundService';
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
  const [selectedFunds, setSelectedFunds] = useState<Set<string>>(new Set());
  const [isBatchMode, setIsBatchMode] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

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
    
    try {
      const allPresetCodes = allFunds.map(f => f.code);
      
      if (!canAddUserFund(trimmedCode, allPresetCodes)) {
        setError(`基金代码 ${trimmedCode} 已经存在，不能重复添加`);
        setLoading(false);
        return;
      }
      
      // 从后端获取真实基金名称
      let fundName = `自定义基金${trimmedCode}`;
      let fundFound = false;
      try {
        const response = await fetch(`http://127.0.0.1:8000/api/fund/${trimmedCode}`);
        if (response.ok) {
          const data = await response.json();
          if (data.found && data.name) {
            fundName = data.name;
            fundFound = true;
          }
        }
      } catch (err) {
        console.warn('获取基金名称失败，使用默认名称:', err);
      }

      // 如果基金未找到，警告用户
      if (!fundFound) {
        setError(`未找到基金代码 ${trimmedCode} 的信息。\n\n这可能是因为：\n• 基金代码不存在\n• 基金已终止或清盘\n• 基金尚未上市`);
        setLoading(false);
        return;
      }

      const newUserFund = addUserFund(trimmedCode, fundName);

      // 调用后端API将基金添加到funds.json
      try {
        const addResponse = await fetch(`http://127.0.0.1:8000/api/fund?code=${trimmedCode}&name=${encodeURIComponent(fundName)}`, {
          method: 'POST',
        });
        if (addResponse.ok) {
          console.log('Fund added to funds.json');
        } else {
          console.warn('Failed to add fund to funds.json, but added to localStorage');
        }
      } catch (err) {
        console.warn('Failed to call backend add fund API:', err);
      }
      
      // 清空输入框，但保持弹窗打开状态，允许连续添加
      setCode('');
      setSuccessMessage(`成功添加: ${fundName}`);
      setError('');
      setLoading(false);
      
      // 触发父组件刷新数据，以立即获取新基金的NAV和限额
      onFundAdded?.(newUserFund.code, newUserFund.name);
      
      // 聚焦回输入框，方便继续输入
      setTimeout(() => {
        const input = document.querySelector('input[type="text"]') as HTMLInputElement;
        if (input) {
          input.focus();
        }
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
    }
  };

  const handleRemoveFund = async (fundCode: string, isUserAdded: boolean) => {
    if (window.confirm(`确定要删除基金 ${fundCode} 吗？`)) {
      // 调用后端API从funds.json和监控数据库中删除
      let backendDeleted = false;
      try {
        const deleteResponse = await fetch(`http://127.0.0.1:8000/api/fund/${fundCode}`, {
          method: 'DELETE',
        });
        if (deleteResponse.ok) {
          const result = await deleteResponse.json();
          if (result.success) {
            backendDeleted = true;
            console.log('✅ Fund deleted from funds.json and monitoring database');
          } else {
            console.warn('⚠️ Backend returned success=false:', result.message);
          }
        } else {
          console.warn('⚠️ Backend DELETE failed:', deleteResponse.status, deleteResponse.statusText);
        }
      } catch (err) {
        console.error('❌ Failed to call backend delete fund API:', err);
      }

      // 从localStorage删除（无论后端是否成功）
      removeUserFund(fundCode);

      // 如果后端删除失败，警告用户
      if (!backendDeleted) {
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
      // 从localStorage删除所有选中的基金
      selectedFunds.forEach(fundCode => {
        removeUserFund(fundCode);
        onFundRemoved?.(fundCode);
      });

      // 调用后端API删除（并行执行）
      const deletePromises = Array.from(selectedFunds).map(async (fundCode) => {
        try {
          const response = await fetch(`http://127.0.0.1:8000/api/fund/${fundCode}`, {
            method: 'DELETE',
          });
          if (response.ok) {
            console.log(`Deleted ${fundCode} from server`);
          }
        } catch (err) {
          console.warn(`Failed to delete ${fundCode} from server:`, err);
        }
      });

      await Promise.all(deletePromises);

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
        className="fixed bottom-8 right-8 bg-[#ea3323] hover:bg-[#c42b1E] text-white p-4 rounded-full shadow-lg transition-all duration-200 z-50 flex items-center justify-center hover:scale-110"
        title="管理基金"
        style={{ minWidth: '60px', minHeight: '60px' }}
      >
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg w-full max-w-2xl max-h-[90vh] overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="bg-gradient-to-r from-[#ea3323] to-[#c42b1E] text-white px-4 py-3">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-lg font-bold">基金管理</h2>
              <p className="text-white/80 text-xs mt-0.5">共 {allFunds.length} 只基金</p>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-white hover:bg-white/20 rounded-full p-1.5 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <div className="p-4 overflow-y-auto max-h-[70vh]">
          {/* Add Fund Form */}
          <div className="mb-4 bg-gray-50 p-3 rounded-lg border border-gray-200">
            <h3 className="text-sm font-semibold text-gray-900 mb-2">添加新基金</h3>

            <form onSubmit={handleAddFund} className="space-y-2">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="输入6位基金代码"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#ea3323] focus:border-transparent text-sm"
                  maxLength={6}
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="bg-[#ea3323] hover:bg-[#c42b1E] text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors duration-200 disabled:bg-gray-400 min-w-[80px]"
                >
                  {loading ? '添加中...' : '添加'}
                </button>
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
                      className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                    >
                      批量管理
                    </button>
                  )}
                  {isBatchMode && (
                    <>
                      <button
                        onClick={handleSelectAll}
                        className="bg-blue-100 hover:bg-blue-200 text-blue-700 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                      >
                        {selectedFunds.size === allFunds.length ? '取消全选' : '全选'}
                      </button>
                      <button
                        onClick={() => {
                          setIsBatchMode(false);
                          setSelectedFunds(new Set());
                        }}
                        className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
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
                    className="bg-red-500 hover:bg-red-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
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
                          className="text-red-500 hover:text-red-700 hover:bg-red-50 p-1.5 rounded-lg transition-colors shrink-0"
                          title="删除基金"
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