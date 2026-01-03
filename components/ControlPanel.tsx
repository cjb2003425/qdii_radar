import React, { useState, useEffect } from 'react';
import { Eye, Clock, Hourglass, Activity, Mail, LayoutDashboard } from 'lucide-react';
import { API_CONFIG } from '../config/api';

interface MonitoringConfig {
  monitoring_enabled: string;
  smtp_enabled: string;
  check_interval_seconds: string;
  alert_time_period: string;
}

interface MonitoringStatus {
  is_running: boolean;
  last_check_time: string;
  check_interval_seconds: number;
  enabled: boolean;
}

interface MarketIndices {
  nasdaq: {
    name: string;
    value: number;
    change: number;
  };
  sp500: {
    name: string;
    value: number;
    change: number;
  };
  avg_premium: number;
  exchange_traded_count: number;
  total_funds: number;
}

export const ControlPanel: React.FC = () => {
  const [config, setConfig] = useState<MonitoringConfig | null>(null);
  const [status, setStatus] = useState<MonitoringStatus | null>(null);
  const [lastEmailTime, setLastEmailTime] = useState<string>('-');
  const [marketData, setMarketData] = useState<MarketIndices | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [updatingInterval, setUpdatingInterval] = useState(false);

  const formatTime = (dateString: string) => {
    if (!dateString) return '从未';
    const utcDateString = dateString.endsWith('Z') ? dateString : dateString + 'Z';
    const date = new Date(utcDateString);
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const fetchConfig = async () => {
    try {
      const response = await fetch(`${API_CONFIG.notifications}/monitoring/config`);
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
      }
    } catch (error) {
      console.error('Failed to fetch monitoring config:', error);
    }
  };

  const fetchStatus = async () => {
    try {
      const response = await fetch(`${API_CONFIG.notifications}/monitoring/status`);
      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      }
    } catch (error) {
      console.error('Failed to fetch monitoring status:', error);
    }
  };

  const fetchLastEmailSent = async () => {
    try {
      const response = await fetch(`${API_CONFIG.notifications}/history?limit=1&offset=0`);
      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data) && data.length > 0) {
          setLastEmailTime(formatTime(data[0].sent_at));
        } else {
          setLastEmailTime('无邮件');
        }
      }
    } catch (error) {
      console.error('Failed to fetch notification history:', error);
    }
  };

  const fetchMarketIndices = async () => {
    try {
      const response = await fetch(`${API_CONFIG.funds.replace('/api/funds', '')}/api/market-indices`);
      if (response.ok) {
        const data = await response.json();
        setMarketData(data);
      }
    } catch (error) {
      console.error('Failed to fetch market indices:', error);
    }
  };

  const toggleMonitoring = async () => {
    setToggling(true);
    try {
      const response = await fetch(`${API_CONFIG.notifications}/monitoring/toggle`, {
        method: 'POST',
      });
      if (response.ok) {
        await fetchConfig();
        await fetchStatus();
      }
    } catch (error) {
      console.error('Failed to toggle monitoring:', error);
    } finally {
      setToggling(false);
    }
  };

  const toggleTimePeriod = async () => {
    if (!config) return;
    const newPeriod = config.alert_time_period === 'trading_hours' ? 'all_day' : 'trading_hours';
    try {
      const response = await fetch(`${API_CONFIG.notifications}/config/alert_time_period`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: newPeriod })
      });
      if (response.ok) {
        await fetchConfig();
      }
    } catch (error) {
      console.error('Failed to update time period:', error);
    }
  };

  const updateCheckInterval = async (seconds: number) => {
    setUpdatingInterval(true);
    try {
      const response = await fetch(`${API_CONFIG.notifications}/config/check_interval_seconds`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: seconds.toString() })
      });
      if (response.ok) {
        await fetchConfig();
        await fetchStatus();
      }
    } catch (error) {
      console.error('Failed to update check interval:', error);
    } finally {
      setUpdatingInterval(false);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([
        fetchConfig(),
        fetchStatus(),
        fetchLastEmailSent(),
        fetchMarketIndices()
      ]);
      setLoading(false);
    };

    loadData();

    // Refresh every 5 seconds
    const interval = setInterval(() => {
      fetchStatus();
      fetchLastEmailSent();
      fetchMarketIndices();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // Derived state
  const isMonitoringEnabled = config?.monitoring_enabled === 'true' || config?.monitoring_enabled === 'True';
  const isTradingHours = config?.alert_time_period === 'trading_hours';
  const intervalSeconds = parseInt(config?.check_interval_seconds || '60');
  const intervalMinutes = Math.round(intervalSeconds / 60);
  const lastCheckTime = status?.last_check_time ? formatTime(status.last_check_time) : '-';

  if (loading || !config || !status) {
    return (
      <div className="bg-white rounded-2xl shadow-soft border border-slate-100 overflow-hidden mb-4 p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-slate-200 rounded w-1/4"></div>
          <div className="h-20 bg-slate-200 rounded-lg"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl shadow-soft border border-slate-100 overflow-hidden mb-4">
      {/* Header Bar */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 px-4 md:px-5 py-2.5 md:py-3 flex justify-between items-center text-white relative overflow-hidden">
        {/* Decorative background element */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none"></div>

        <div className="flex items-center gap-3 relative z-10">
          <div className="bg-indigo-500/20 p-1.5 rounded-xl backdrop-blur-sm ring-1 ring-white/10">
             <Activity className="text-indigo-300 w-4 h-4" />
          </div>
          <div>
            <span className="font-bold text-base md:text-[17px] tracking-tight block">监控中心</span>
            <span className="text-[10px] text-slate-400 font-medium hidden md:block leading-none mt-0.5">System Control</span>
          </div>
        </div>

        <div className="relative z-10 flex items-center gap-2 bg-slate-800/50 backdrop-blur-md border border-white/10 px-2.5 py-1 rounded-full">
          <span className="relative flex h-2 w-2">
            {status.is_running && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            )}
            <span className={`relative inline-flex rounded-full h-2 w-2 ${
              status.is_running ? 'bg-emerald-500' : 'bg-slate-500'
            }`}></span>
          </span>
          <span className="text-[10px] font-medium text-emerald-50">
            {status.is_running ? '运行中' : '已停止'}
          </span>
        </div>
      </div>

      {/* Cards Area */}
      <div className="p-3 md:p-3 grid grid-cols-1 md:grid-cols-3 gap-3 bg-slate-50/50">
        {/* Card 1: Monitor Toggle */}
        <div className={`bg-white rounded-xl p-2.5 md:p-3 flex justify-between items-center border shadow-sm hover:shadow-md transition-all duration-300 ${
          isMonitoringEnabled
            ? 'border-green-200 bg-gradient-to-br from-green-50/50 to-emerald-50/50'
            : 'border-slate-200'
        }`}>
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-xl transition-colors ${
              isMonitoringEnabled
                ? 'bg-gradient-to-br from-green-500 to-emerald-600 text-white shadow-md'
                : 'bg-slate-200 text-slate-500'
            }`}>
              <Eye size={18} className="md:w-[20px] md:h-[20px]" strokeWidth={1.5} />
            </div>
            <div>
              <div className="font-bold text-slate-700 text-xs md:text-[13px] mb-0.5">基金监控</div>
              <div className={`text-[10px] font-medium ${
                isMonitoringEnabled ? 'text-green-600' : 'text-slate-400'
              }`}>
                {isMonitoringEnabled ? '正在监控' : '已暂停'}
              </div>
            </div>
          </div>
          <button
            onClick={toggleMonitoring}
            disabled={toggling}
            className={`w-9 h-5 md:w-10 md:h-6 rounded-full p-0.5 transition-all duration-300 ease-in-out cursor-pointer ${
              toggling ? 'opacity-50 cursor-not-allowed' : ''
            } ${
              isMonitoringEnabled ? 'bg-gradient-to-r from-green-500 to-emerald-600 shadow-inner' : 'bg-slate-200'
            }`}
          >
            <div className={`bg-white w-4 h-4 md:w-5 md:h-5 rounded-full shadow-sm transform transition-transform duration-300 ease-out ${
              isMonitoringEnabled ? 'translate-x-4' : 'translate-x-0'
            }`}></div>
          </button>
        </div>

        {/* Card 2: Time Period */}
        <div className={`bg-white rounded-xl p-2.5 md:p-3 flex justify-between items-center border shadow-sm hover:shadow-md transition-all duration-300 ${
          isTradingHours
            ? 'border-amber-200 bg-gradient-to-br from-amber-50/50 to-yellow-50/50'
            : 'border-rose-200 bg-gradient-to-br from-rose-50/50 to-pink-50/50'
        }`}>
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-xl transition-colors ${
              isTradingHours
                ? 'bg-gradient-to-br from-amber-500 to-yellow-600 text-white shadow-md'
                : 'bg-gradient-to-br from-rose-500 to-pink-600 text-white shadow-md'
            }`}>
              <Clock size={18} className="md:w-[20px] md:h-[20px]" strokeWidth={1.5} />
            </div>
            <div>
              <div className="font-bold text-slate-700 text-xs md:text-[13px] mb-0.5">智能提醒</div>
              <div className="text-[10px] text-slate-500 font-medium">
                {isTradingHours ? '仅交易时间' : '全天'}
              </div>
            </div>
          </div>
          <button
            onClick={toggleTimePeriod}
            className={`w-9 h-5 md:w-10 md:h-6 rounded-full p-0.5 transition-all duration-300 ease-in-out cursor-pointer ${
              isTradingHours ? 'bg-gradient-to-r from-amber-500 to-yellow-600 shadow-inner' : 'bg-gradient-to-r from-rose-500 to-pink-600 shadow-inner'
            }`}
          >
            <div className={`bg-white w-4 h-4 md:w-5 md:h-5 rounded-full shadow-sm transform transition-transform duration-300 ease-out ${
              isTradingHours ? 'translate-x-4' : 'translate-x-0'
            }`}></div>
          </button>
        </div>

        {/* Card 3: Check Interval */}
        <div className={`bg-white rounded-xl p-2.5 md:p-3 flex justify-between items-center border shadow-sm hover:shadow-md transition-all duration-300 ${
          updatingInterval ? 'border-slate-200 opacity-60' : 'border-blue-200'
        }`}>
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-xl transition-colors ${
              updatingInterval ? 'bg-slate-200 text-slate-500' : 'bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-md'
            }`}>
              <Hourglass size={18} className="md:w-[20px] md:h-[20px]" strokeWidth={1.5} />
            </div>
            <div>
              <div className="font-bold text-slate-700 text-xs md:text-[13px] mb-0.5">检查间隔</div>
              <div className="text-[10px] text-slate-500 font-medium">{intervalMinutes} 分钟</div>
            </div>
          </div>
          <div className={`relative`}>
            <select
              value={config.check_interval_seconds}
              onChange={(e) => updateCheckInterval(parseInt(e.target.value))}
              disabled={updatingInterval}
              className={`appearance-none px-2 py-1 pr-6 rounded-lg border text-xs font-semibold shadow-sm transition-all cursor-pointer ${
                updatingInterval
                  ? 'bg-slate-100 border-slate-200 text-slate-400 cursor-not-allowed'
                  : 'bg-white border-blue-200 text-blue-700 hover:bg-blue-50 hover:border-blue-300'
              }`}
            >
              <option value="60">1 分钟</option>
              <option value="180">3 分钟</option>
              <option value="300">5 分钟</option>
              <option value="600">10 分钟</option>
              <option value="900">15 分钟</option>
              <option value="1800">30 分钟</option>
              <option value="3600">60 分钟</option>
            </select>
            <div className={`absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none ${
              updatingInterval ? 'text-slate-400' : 'text-blue-600'
            }`}>
              <span className="text-[10px]">▼</span>
            </div>
          </div>
        </div>
      </div>

      {/* Warning Banner */}
      {!isMonitoringEnabled && (
        <div className="mx-3 mt-3 relative overflow-hidden rounded-lg shadow-sm border border-amber-300 bg-gradient-to-br from-amber-50 to-yellow-50">
          <div className="absolute top-0 right-0 w-20 h-20 bg-gradient-to-br from-amber-200/50 to-transparent rounded-bl-full"></div>
          <div className="relative p-2 flex items-start gap-2">
            <div className="flex-shrink-0">
              <div className="p-1 bg-gradient-to-br from-amber-400 to-amber-500 rounded-lg shadow-md">
                <svg className="w-3 h-3 text-white" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </div>
            </div>
            <div className="flex-1">
              <p className="text-[10px] text-amber-800 leading-relaxed">
                系统将不会检查基金溢价率或发送警报邮件
              </p>
            </div>
          </div>
        </div>
      )}

      {/* System Health Section */}
      <div className="px-3 md:px-3 pb-3 bg-slate-50/50">
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-3">
          <h3 className="text-[10px] md:text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Activity size={12} /> System Health
          </h3>
          <div className="flex items-center justify-between bg-slate-50/50 rounded-lg p-2 border border-slate-100">
            <div className="flex items-center gap-2">
              <div className="bg-white p-1 rounded-md text-emerald-500 shadow-sm border border-slate-100">
                <Clock size={14} />
              </div>
              <div className="flex flex-col">
                <span className="text-[9px] text-slate-400 font-medium leading-none mb-0.5">检查</span>
                <span className="text-[11px] font-bold text-slate-700 font-mono leading-none">{lastCheckTime}</span>
              </div>
            </div>

            <div className="w-px h-6 bg-slate-200 mx-1"></div>

            <div className="flex items-center gap-2">
              <div className="flex flex-col items-end">
                <span className="text-[9px] text-slate-400 font-medium leading-none mb-0.5">通知</span>
                <span className="text-[11px] font-bold text-slate-700 font-mono leading-none">{lastEmailTime}</span>
              </div>
              <div className="bg-white p-1 rounded-md text-indigo-500 shadow-sm border border-slate-100">
                <Mail size={14} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Market Overview Section */}
      <div className="px-3 md:px-3 pb-3 bg-slate-50/50">
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-3">
          <h3 className="text-[10px] md:text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <LayoutDashboard size={12} /> Market Overview
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <div className="flex flex-col overflow-hidden">
              <span className="text-[9px] font-semibold text-slate-400 mb-0.5">纳斯达克</span>
              <span className="text-base font-bold leading-none tracking-tight text-emerald-600">
                {marketData ? marketData.nasdaq.value.toLocaleString('en-US', {maximumFractionDigits: 0}) : '...'}
              </span>
            </div>
            <div className="flex flex-col overflow-hidden">
              <span className="text-[9px] font-semibold text-slate-400 mb-0.5">标普500</span>
              <span className="text-base font-bold leading-none tracking-tight text-blue-600">
                {marketData ? marketData.sp500.value.toLocaleString('en-US', {maximumFractionDigits: 0}) : '...'}
              </span>
            </div>
            <div className="flex flex-col overflow-hidden">
              <span className="text-[9px] font-semibold text-slate-400 mb-0.5">平均溢价</span>
              <span className={`text-base font-bold leading-none tracking-tight ${
                (marketData?.avg_premium || 0) > 0 ? 'text-red-500' : 'text-green-500'
              }`}>
                {marketData ? (marketData.avg_premium > 0 ? '+' : '') + marketData.avg_premium.toFixed(2) + '%' : '...'}
              </span>
            </div>
            <div className="flex flex-col overflow-hidden">
              <span className="text-[9px] font-semibold text-slate-400 mb-0.5">可交易</span>
              <span className="text-base font-bold leading-none tracking-tight text-indigo-600">
                {marketData ? `${marketData.exchange_traded_count}/${marketData.total_funds}` : '...'}
              </span>
            </div>
          </div>
        </div>
      </div>

    </div>
  );
};
