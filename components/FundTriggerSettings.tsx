import React, { useState, useEffect } from 'react';
import { FundData } from '../types/fund';
import { FundTrigger, CreateTriggerRequest } from '../types/notifications';
import { getFundTriggers, createTrigger, updateTrigger, deleteTrigger } from '../services/notificationService';

interface Props {
  fund: FundData;
  onTriggerChange?: () => void;
  onClose?: () => void;
}

const FundTriggerSettings: React.FC<Props> = ({ fund, onTriggerChange, onClose }) => {
  const [triggers, setTriggers] = useState<FundTrigger[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newTriggerType, setNewTriggerType] = useState<'premium_high' | 'premium_low' | 'limit_change' | 'limit_high'>('premium_high');
  const [newThreshold, setNewThreshold] = useState<string>('');
  const [editingTriggerId, setEditingTriggerId] = useState<number | null>(null);
  const [editThreshold, setEditThreshold] = useState<string>('');

  useEffect(() => {
    loadTriggers();
  }, [fund.id]);

  const loadTriggers = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getFundTriggers(fund.id);
      setTriggers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load triggers');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTrigger = async () => {
    let threshold: number | null = null;

    if (newTriggerType === 'limit_change') {
      // Optional threshold for limit_change
      if (newThreshold.trim()) {
        threshold = parseFloat(newThreshold);
        if (isNaN(threshold)) {
          setError('请输入有效的限额阈值');
          return;
        }
      }
    } else {
      // Required threshold for premium triggers
      threshold = parseFloat(newThreshold);
      if (isNaN(threshold)) {
        setError('请输入有效的阈值');
        return;
      }
    }

    try {
      const request: CreateTriggerRequest = {
        trigger_type: newTriggerType,
        threshold_value: threshold,
        enabled: true
      };

      await createTrigger(fund.id, request);
      setShowAddForm(false);
      setNewThreshold('');
      await loadTriggers();
      if (onTriggerChange) onTriggerChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create trigger');
    }
  };

  const handleToggleTrigger = async (triggerId: number, enabled: boolean) => {
    try {
      const trigger = triggers.find(t => t.id === triggerId);
      if (!trigger) return;

      await updateTrigger(fund.id, triggerId, {
        trigger_type: trigger.trigger_type,
        enabled
      });
      await loadTriggers();
      if (onTriggerChange) onTriggerChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update trigger');
    }
  };

  const handleDeleteTrigger = async (triggerId: number) => {
    if (!confirm('确定要删除这个触发器吗？')) {
      return;
    }

    try {
      await deleteTrigger(fund.id, triggerId);
      await loadTriggers();
      if (onTriggerChange) onTriggerChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete trigger');
    }
  };

  const handleStartEdit = (trigger: FundTrigger) => {
    setEditingTriggerId(trigger.id);
    setEditThreshold(trigger.threshold_value?.toString() || '');
  };

  const handleCancelEdit = () => {
    setEditingTriggerId(null);
    setEditThreshold('');
  };

  const handleSaveEdit = async (triggerId: number) => {
    // Find the trigger to get its type
    const trigger = triggers.find(t => t.id === triggerId);
    if (!trigger) return;

    let threshold: number | null = null;

    if (trigger.trigger_type === 'limit_change') {
      // Optional threshold for limit_change
      if (editThreshold.trim()) {
        threshold = parseFloat(editThreshold);
        if (isNaN(threshold)) {
          setError('请输入有效的限额阈值');
          return;
        }
      }
    } else {
      // Required threshold for premium triggers
      threshold = parseFloat(editThreshold);
      if (isNaN(threshold)) {
        setError('请输入有效的阈值');
        return;
      }
    }

    try {
      // Include trigger_type in the update
      await updateTrigger(fund.id, triggerId, {
        trigger_type: trigger.trigger_type,
        threshold_value: threshold
      });
      setEditingTriggerId(null);
      setEditThreshold('');
      await loadTriggers();
      if (onTriggerChange) onTriggerChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update trigger');
    }
  };

  const getTriggerLabel = (type: string) => {
    switch (type) {
      case 'premium_high':
        return '溢价率高于';
      case 'premium_low':
        return '溢价率低于';
      case 'limit_change':
        return '申购额度大于';
      case 'limit_high':
        return '申购限制放开';
      default:
        return type;
    }
  };

  const getTriggerColor = (type: string) => {
    switch (type) {
      case 'premium_high':
        return 'text-red-600 bg-red-50';
      case 'premium_low':
        return 'text-green-600 bg-green-50';
      case 'limit_change':
        return 'text-orange-600 bg-orange-50';
      case 'limit_high':
        return 'text-green-600 bg-green-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  return (
    <div className="p-4 bg-white border-t border-gray-200">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700">
          {fund.name} ({fund.id}) - 自定义触发器
        </h3>
        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-lg leading-none"
          >
            ×
          </button>
        )}
      </div>

      {error && (
        <div className="mb-3 p-2 bg-red-50 text-red-700 text-xs rounded">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-center text-gray-400 text-sm py-4">加载中...</div>
      ) : (
        <>
          {triggers.length === 0 ? (
            <div className="text-center text-gray-400 text-sm py-4">
              暂无自定义触发器，使用全局默认阈值
            </div>
          ) : (
            <div className="space-y-2 mb-3">
              {triggers.map((trigger) => (
                <div
                  key={trigger.id}
                  className={`p-2 rounded border ${
                    trigger.enabled ? 'border-gray-200' : 'border-gray-100 opacity-60'
                  }`}
                >
                  {editingTriggerId === trigger.id ? (
                    // Edit Mode
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-0.5 rounded ${getTriggerColor(trigger.trigger_type)}`}>
                          {getTriggerLabel(trigger.trigger_type)}
                        </span>
                        <input
                          type="number"
                          step={trigger.trigger_type === 'limit_change' ? '1' : '0.1'}
                          value={editThreshold}
                          onChange={(e) => setEditThreshold(e.target.value)}
                          className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder={trigger.trigger_type === 'limit_change' ? '限额 (元)' : '阈值'}
                        />
                        <span className="text-sm text-gray-600">
                          {trigger.trigger_type === 'limit_change' ? '元' : '%'}
                        </span>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleSaveEdit(trigger.id)}
                          className="flex-1 py-1 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-700 transition-colors"
                        >
                          保存
                        </button>
                        <button
                          onClick={handleCancelEdit}
                          className="flex-1 py-1 bg-gray-200 text-gray-700 text-xs font-medium rounded hover:bg-gray-300 transition-colors"
                        >
                          取消
                        </button>
                      </div>
                    </div>
                  ) : (
                    // View Mode
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-0.5 rounded ${getTriggerColor(trigger.trigger_type)}`}>
                          {getTriggerLabel(trigger.trigger_type)}
                        </span>
                        {trigger.threshold_value !== null && trigger.threshold_value !== undefined && (
                          <span className="text-sm font-medium text-gray-700">
                            {trigger.trigger_type === 'limit_change'
                              ? `≥${trigger.threshold_value.toLocaleString()}元`
                              : `${trigger.threshold_value}%`
                            }
                          </span>
                        )}
                        {trigger.trigger_type === 'limit_change' && (trigger.threshold_value === null || trigger.threshold_value === undefined) && (
                          <span className="text-xs text-gray-500">
                            任意变更
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            className="sr-only peer"
                            checked={trigger.enabled}
                            onChange={(e) => handleToggleTrigger(trigger.id, e.target.checked)}
                          />
                          <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                        </label>
                        <button
                          onClick={() => handleStartEdit(trigger)}
                          className="text-blue-500 hover:text-blue-700 text-xs font-medium"
                          title="编辑触发器"
                        >
                          ✎
                        </button>
                        <button
                          onClick={() => handleDeleteTrigger(trigger.id)}
                          className="text-red-500 hover:text-red-700 text-xs"
                          title="删除触发器"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {!showAddForm ? (
            <button
              onClick={() => setShowAddForm(true)}
              className="w-full py-2 px-3 bg-blue-50 text-blue-700 text-sm font-medium rounded hover:bg-blue-100 transition-colors"
            >
              + 添加触发器
            </button>
          ) : (
            <div className="p-3 bg-gray-50 rounded space-y-2">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  触发器类型
                </label>
                <select
                  value={newTriggerType}
                  onChange={(e) => setNewTriggerType(e.target.value as any)}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="premium_high">溢价率高于</option>
                  <option value="premium_low">溢价率低于</option>
                  <option value="limit_change">申购额度大于</option>
                  <option value="limit_high">申购限制放开</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  {newTriggerType === 'limit_change' || newTriggerType === 'limit_high' ? '限额阈值 (元)' : '阈值 (%)'}
                </label>
                <input
                  type="number"
                  step={newTriggerType === 'limit_change' || newTriggerType === 'limit_high' ? '1' : '0.1'}
                  value={newThreshold}
                  onChange={(e) => setNewThreshold(e.target.value)}
                  placeholder={
                    newTriggerType === 'limit_change' ? '例如: 100000' :
                    newTriggerType === 'limit_high' ? '例如: 100' :
                    '例如: 5.0'
                  }
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {newTriggerType === 'premium_high' && (
                  <p className="text-xs text-gray-500 mt-1">当溢价率高于此值时触发警报</p>
                )}
                {newTriggerType === 'premium_low' && (
                  <p className="text-xs text-gray-500 mt-1">当溢价率低于此值时触发（良好购买机会）</p>
                )}
                {newTriggerType === 'limit_change' && (
                  <p className="text-xs text-gray-500 mt-1">留空表示任何额度都触发</p>
                )}
                {newTriggerType === 'limit_high' && (
                  <p className="text-xs text-gray-500 mt-1">当限额大于此值时触发</p>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleCreateTrigger}
                  className="flex-1 py-1.5 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 transition-colors"
                >
                  保存
                </button>
                <button
                  onClick={() => {
                    setShowAddForm(false);
                    setNewThreshold('');
                    setError(null);
                  }}
                  className="flex-1 py-1.5 bg-gray-200 text-gray-700 text-sm font-medium rounded hover:bg-gray-300 transition-colors"
                >
                  取消
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default FundTriggerSettings;
