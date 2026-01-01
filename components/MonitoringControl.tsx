import React, { useState, useEffect } from 'react';
import { Switch } from '@headlessui/react';
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

// Pulse animation icon component
const PulseIcon = ({ active }: { active: boolean }) => (
  <span className={`relative flex h-3 w-3`}>
    {active && (
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
    )}
    <span className={`relative inline-flex rounded-full h-3 w-3 ${
      active ? 'bg-green-500' : 'bg-gray-500'
    }`}></span>
  </span>
);

export default function MonitoringControl() {
  const [config, setConfig] = useState<MonitoringConfig | null>(null);
  const [status, setStatus] = useState<MonitoringStatus | null>(null);
  const [lastEmailSent, setLastEmailSent] = useState<string>('-');
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [updatingInterval, setUpdatingInterval] = useState(false);

  const formatTime = (dateString: string) => {
    if (!dateString) return 'Never';
    // Backend returns UTC time without timezone, so we need to parse it as UTC
    // Add 'Z' to indicate it's UTC time
    const utcDateString = dateString.endsWith('Z') ? dateString : dateString + 'Z';
    const date = new Date(utcDateString);
    // Convert to Beijing timezone (UTC+8)
    return date.toLocaleString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
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
          const lastNotification = data[0];
          setLastEmailSent(formatTime(lastNotification.sent_at));
        } else {
          setLastEmailSent('无邮件发送记录');
        }
      }
    } catch (error) {
      console.error('Failed to fetch notification history:', error);
      setLastEmailSent('获取失败');
    }
  };

  const toggleMonitoring = async () => {
    setToggling(true);
    try {
      const response = await fetch(`${API_CONFIG.notifications}/monitoring/toggle`, {
        method: 'POST',
      });
      if (response.ok) {
        const data = await response.json();
        await fetchConfig();
        await fetchStatus();
      }
    } catch (error) {
      console.error('Failed to toggle monitoring:', error);
    } finally {
      setToggling(false);
    }
  };

  const updateTimePeriod = async (period: string) => {
    try {
      const response = await fetch(`${API_CONFIG.notifications}/config/alert_time_period`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: period })
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
        console.log(`✅ Check interval updated to ${seconds} seconds`);
      } else {
        console.error('❌ Failed to update check interval');
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
      await Promise.all([fetchConfig(), fetchStatus(), fetchLastEmailSent()]);
      setLoading(false);
    };
    loadData();

    // Refresh status every 5 seconds
    const interval = setInterval(() => {
      fetchStatus();
      fetchLastEmailSent();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  if (loading || !config || !status) {
    return (
      <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-200">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 rounded w-1/4"></div>
          <div className="h-20 bg-gray-200 rounded-lg"></div>
        </div>
      </div>
    );
  }

  const isMonitoringEnabled = config.monitoring_enabled === 'true' || config.monitoring_enabled === 'True';
  const isSmtpEnabled = config.smtp_enabled === 'true' || config.smtp_enabled === 'True';
  const intervalMinutes = Math.round(parseInt(config.check_interval_seconds) / 60);
  const statusIntervalMinutes = Math.round(status.check_interval_seconds / 60);
  const isTradingHours = config.alert_time_period === 'trading_hours';

  return (
    <div className="space-y-1.5 px-3">
      {/* Main Status Card */}
      <div className="bg-white rounded-xl shadow-md border border-gray-200 overflow-hidden">
        {/* Header with gradient */}
        <div className="bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 px-2.5 py-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1">
              <div className="bg-white/20 p-0.5 sm:p-1 rounded-lg backdrop-blur-sm">
                <svg className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <div>
                <h2 className="text-[10px] sm:text-sm font-bold text-white">
                  监控控制
                </h2>
              </div>
            </div>
            <div className={`px-1 py-0.5 rounded-full flex items-center space-x-0.5 shadow-md backdrop-blur-sm ${
              status.is_running
                ? 'bg-white/30 border border-white/50'
                : 'bg-white/20 border border-white/30'
            }`}>
              <PulseIcon active={status.is_running} />
              <span className={`text-[8px] sm:text-xs font-semibold text-white`}>
                {status.is_running ? '运行中' : '已停止'}
              </span>
            </div>
          </div>
        </div>

        {/* Control Section */}
        <div className="p-1.5 space-y-1.5">
          <div className="grid grid-cols-1 gap-1">
            {/* Monitoring Toggle */}
            <div className={`relative overflow-hidden rounded-lg border transition-all duration-300 ${
              isMonitoringEnabled
                ? 'border-green-200 bg-gradient-to-br from-green-50 to-emerald-50'
                : 'border-gray-200 bg-gradient-to-br from-gray-50 to-slate-50'
            }`}>
              <div className="absolute top-0 right-0 w-20 h-20 bg-gradient-to-br from-white/40 to-transparent rounded-bl-full"></div>
              <div className="relative p-1.5">
                <div className="flex items-center justify-between">
<<<<<<< HEAD
                  <div className="flex items-center space-x-1.5">
=======
                  <div className="flex items-center space-x-1">
>>>>>>> 469233e (feat: Optimize monitoring control layout for iPhone 15)
                    <div className={`p-1 sm:p-1.5 rounded-lg ${
                      isMonitoringEnabled
                        ? 'bg-gradient-to-br from-green-500 to-emerald-600 text-white shadow-md'
                        : 'bg-gray-200 text-gray-500'
                    }`}>
<<<<<<< HEAD
                      <svg className="w-2 h-2 sm:w-3.5 sm:h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
=======
                      <svg className="w-2.5 h-2.5 sm:w-3.5 sm:h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
>>>>>>> 469233e (feat: Optimize monitoring control layout for iPhone 15)
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-[10px] font-semibold text-gray-900">基金监控</h3>
                      <p className="text-[9px] text-gray-500">
                        {isMonitoringEnabled ? '已启用' : '已禁用'}
                      </p>
                    </div>
                  </div>
                  <Switch
                    checked={isMonitoringEnabled}
                    onChange={toggleMonitoring}
                    disabled={toggling}
                    className={`${
                      toggling ? 'opacity-50 cursor-not-allowed' : ''
                    } relative inline-flex h-3.5 w-6 sm:h-5 sm:w-9 items-center rounded-full transition-all duration-300 shadow-sm ${
                      isMonitoringEnabled
                        ? 'bg-gradient-to-r from-green-500 to-emerald-600'
                        : 'bg-gray-300'
                    }`}
                  >
                    <span
                      className={`${
                        isMonitoringEnabled ? 'translate-x-2.5 sm:translate-x-5' : 'translate-x-0.5 sm:translate-x-1'
                      } inline-block h-1.5 w-1.5 sm:h-3.5 sm:w-3.5 transform rounded-full bg-white shadow-md transition-transform duration-300`}
                    />
                  </Switch>
                </div>
              </div>
            </div>

            {/* Time Period */}
            <div className={`relative overflow-hidden rounded-lg border transition-all duration-300 ${
              isTradingHours
                ? 'border-amber-200 bg-gradient-to-br from-amber-50 to-yellow-50'
                : 'border-rose-200 bg-gradient-to-br from-rose-50 to-pink-50'
            }`}>
              <div className="absolute top-0 right-0 w-20 h-20 bg-gradient-to-br from-white/40 to-transparent rounded-bl-full"></div>
              <div className="relative p-1.5">
                <div className="flex items-center justify-between">
<<<<<<< HEAD
                  <div className="flex items-center space-x-1.5">
=======
                  <div className="flex items-center space-x-1">
>>>>>>> 469233e (feat: Optimize monitoring control layout for iPhone 15)
                    <div className={`p-1 sm:p-1.5 rounded-lg ${
                      isTradingHours
                        ? 'bg-gradient-to-br from-amber-500 to-yellow-600 text-white shadow-md'
                        : 'bg-gradient-to-br from-rose-500 to-pink-600 text-white shadow-md'
                    }`}>
<<<<<<< HEAD
                      <svg className="w-2 h-2 sm:w-3.5 sm:h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
=======
                      <svg className="w-2.5 h-2.5 sm:w-3.5 sm:h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
>>>>>>> 469233e (feat: Optimize monitoring control layout for iPhone 15)
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-[10px] font-semibold text-gray-900">提醒时间</h3>
                      <p className="text-[9px] text-gray-500">
                        {isTradingHours ? '交易时间' : '全天'}
                      </p>
                    </div>
                  </div>
                  <Switch
                    checked={isTradingHours}
                    onChange={() => updateTimePeriod(isTradingHours ? 'all_day' : 'trading_hours')}
                    className={`relative inline-flex h-3.5 w-6 sm:h-5 sm:w-9 items-center rounded-full transition-all duration-300 shadow-sm ${
                      isTradingHours
                        ? 'bg-gradient-to-r from-amber-500 to-yellow-600'
                        : 'bg-gradient-to-r from-rose-500 to-pink-600'
                    }`}
                  >
                    <span
                      className={`${
                        isTradingHours ? 'translate-x-2.5 sm:translate-x-5' : 'translate-x-0.5 sm:translate-x-1'
                      } inline-block h-1.5 w-1.5 sm:h-3.5 sm:w-3.5 transform rounded-full bg-white shadow-md transition-transform duration-300`}
                    />
                  </Switch>
                </div>
              </div>
            </div>

            {/* Check Interval Selector */}
            <div className={`relative overflow-hidden rounded-lg border transition-all duration-300 ${
              updatingInterval ? 'border-gray-200 bg-gray-50 opacity-60' : 'border-orange-200 bg-gradient-to-br from-orange-50 to-amber-50'
            }`}>
              <div className="absolute top-0 right-0 w-20 h-20 bg-gradient-to-br from-white/40 to-transparent rounded-bl-full"></div>
              <div className="relative p-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-1">
                    <div className={`p-1 sm:p-1.5 rounded-lg shadow-md ${
                      updatingInterval ? 'bg-gray-300 text-gray-500' : 'bg-gradient-to-br from-orange-500 to-amber-600 text-white'
                    }`}>
                      <svg className="w-2.5 h-2.5 sm:w-3.5 sm:h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-[10px] font-semibold text-gray-900">检查间隔</h3>
                      <p className="text-[9px] text-gray-500">
                        {intervalMinutes} 分钟
                      </p>
                    </div>
                  </div>
                  <select
                    value={config.check_interval_seconds}
                    onChange={(e) => updateCheckInterval(parseInt(e.target.value))}
                    disabled={updatingInterval}
                    className={`text-[10px] sm:text-[11px] font-medium rounded-lg border-2 bg-white px-1 py-1 focus:outline-none focus:ring-2 transition-all ${
                      updatingInterval
                        ? 'border-gray-200 cursor-not-allowed'
                        : 'border-orange-200 cursor-pointer focus:ring-orange-500 focus:border-transparent'
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
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Status Cards - Responsive grid layout */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-[auto_auto_auto_minmax(120px,1fr)_minmax(120px,1fr)] gap-0.5 sm:gap-2">
        {/* Monitor Status */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 px-1 py-1">
          <div className="flex items-center space-x-0.5">
            <div className="p-0.5 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg shrink-0">
              <svg className="w-2 h-2 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <div className="min-w-0">
              <p className="text-[7px] text-gray-500">监控</p>
              <p className="text-[9px] font-bold text-gray-900 truncate">
                {isMonitoringEnabled ? '已启用' : '已禁用'}
              </p>
            </div>
          </div>
        </div>

        {/* Running Status */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 px-1 py-1">
          <div className="flex items-center space-x-0.5">
            <div className={`p-0.5 rounded-lg shrink-0 ${
              status.is_running
                ? 'bg-gradient-to-br from-green-500 to-emerald-600'
                : 'bg-gradient-to-br from-gray-400 to-gray-500'
            }`}>
              <svg className="w-2 h-2 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div className="min-w-0">
              <p className="text-[7px] text-gray-500">状态</p>
              <p className={`text-[9px] font-bold truncate ${
                status.is_running ? 'text-green-600' : 'text-gray-600'
              }`}>
                {status.is_running ? '运行中' : '已停止'}
              </p>
            </div>
          </div>
        </div>

        {/* Check Interval */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 px-1 py-1">
          <div className="flex items-center space-x-0.5">
            <div className="p-0.5 bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg shrink-0">
              <svg className="w-2 h-2 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="min-w-0">
              <p className="text-[7px] text-gray-500">间隔</p>
              <p className="text-[9px] font-bold text-gray-900">
                {statusIntervalMinutes}分
              </p>
            </div>
          </div>
        </div>

        {/* Last Check Time */}
        <div className="hidden md:block bg-white rounded-lg shadow-sm border border-gray-200 p-2">
          <div className="flex items-center space-x-1.5">
            <div className="p-1 bg-gradient-to-br from-indigo-500 to-indigo-600 rounded-lg shrink-0">
              <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[10px] text-gray-500">上次检查</p>
              <p className="text-[11px] font-semibold text-gray-900 truncate">
                {status.last_check_time ? formatTime(status.last_check_time) : '从未'}
              </p>
            </div>
          </div>
        </div>

        {/* Last Email Sent */}
        <div className="hidden md:block bg-white rounded-lg shadow-sm border border-gray-200 p-2">
          <div className="flex items-center space-x-1.5">
            <div className="p-1 bg-gradient-to-br from-pink-500 to-pink-600 rounded-lg shrink-0">
              <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[10px] text-gray-500">上次邮件</p>
              <p className="text-[11px] font-semibold text-gray-900 truncate">
                {lastEmailSent}
              </p>
            </div>
          </div>
        </div>

        {/* Mobile-only combined status for last check and email */}
        <div className="md:hidden col-span-2 bg-white rounded-lg shadow-sm border border-gray-200 p-1">
          <div className="grid grid-cols-2 gap-1">
            <div className="flex items-center space-x-0.5">
              <div className="p-0.5 bg-gradient-to-br from-indigo-500 to-indigo-600 rounded-lg shrink-0">
                <svg className="w-2 h-2 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div className="min-w-0">
                <p className="text-[7px] text-gray-500">上次检查</p>
                <p className="text-[9px] font-semibold text-gray-900 truncate">
                  {status.last_check_time ? formatTime(status.last_check_time).split(' ')[1] : '从未'}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-0.5">
              <div className="p-0.5 bg-gradient-to-br from-pink-500 to-pink-600 rounded-lg shrink-0">
                <svg className="w-2 h-2 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <div className="min-w-0">
                <p className="text-[7px] text-gray-500">上次邮件</p>
                <p className="text-[9px] font-semibold text-gray-900 truncate">
                  {lastEmailSent.includes(' ') ? lastEmailSent.split(' ')[1] : lastEmailSent}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Info Banner - Compact */}
      {!isMonitoringEnabled && (
        <div className="relative overflow-hidden rounded-lg shadow-md border border-amber-300 bg-gradient-to-br from-amber-50 to-yellow-50">
          <div className="absolute top-0 right-0 w-20 h-20 bg-gradient-to-br from-amber-200/50 to-transparent rounded-bl-full"></div>
          <div className="relative p-1.5">
            <div className="flex items-start space-x-1">
              <div className="flex-shrink-0">
                <div className="p-0.5 sm:p-1 bg-gradient-to-br from-amber-400 to-amber-500 rounded-lg shadow-md">
                  <svg className="w-2.5 h-2.5 sm:w-3 sm:h-3 text-white" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>
              <div className="flex-1">
                <p className="text-[9px] sm:text-[10px] text-amber-800 leading-relaxed">
                  系统将不会检查基金溢价率或发送警报邮件。
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
