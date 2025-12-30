import React, { useState, useEffect } from 'react';
import FundList from './components/FundList';
import FundManager from './components/FundManager';
import HeadlineStats from './components/HeadlineStats';
import NavBar from './components/NavBar';
import MonitoringControl from './components/MonitoringControl';
import Footer from './components/Footer';
import { FundData } from './types/fund';
import { fetchQDIIFunds } from './services/fundService';
import { initializeFunds, removeUserFund } from './services/userFundService';

const App: React.FC = () => {
  const [funds, setFunds] = useState<FundData[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState<string>('all');

  // localStorage key for monitoring preferences
  const MONITORING_STORAGE_KEY = 'qdii_fund_monitoring';

  useEffect(() => {
    const loadFunds = async () => {
      setLoading(true);
      try {
        // 初始化预设基金（仅第一次）
        initializeFunds();

        const data = await fetchQDIIFunds();

        // Load monitoring preferences from localStorage
        let monitoringPrefs = loadMonitoringPreferences();

        // Sync with backend to get the latest monitored funds
        try {
          const response = await fetch('http://127.0.0.1:8000/api/notifications/monitored-funds');
          if (response.ok) {
            const monitoredFunds = await response.json();
            // Update localStorage to match backend
            const syncedPrefs: Record<string, boolean> = {};
            data.forEach(fund => {
              syncedPrefs[fund.id] = monitoredFunds.includes(fund.id);
            });
            monitoringPrefs = syncedPrefs;
            saveMonitoringPreferences(syncedPrefs);
          }
        } catch (error) {
          console.error("Failed to sync monitoring state:", error);
        }

        // Merge monitoring preferences with fund data
        const fundsWithMonitoring = data.map(fund => ({
          ...fund,
          monitoringEnabled: monitoringPrefs[fund.id] || false
        }));

        setFunds(fundsWithMonitoring);
      } catch (error) {
        console.error("Failed to fetch funds", error);
      } finally {
        setLoading(false);
      }
    };

    loadFunds();
  }, []);

  const loadMonitoringPreferences = (): Record<string, boolean> => {
    try {
      const stored = localStorage.getItem(MONITORING_STORAGE_KEY);
      return stored ? JSON.parse(stored) : {};
    } catch {
      return {};
    }
  };

  const saveMonitoringPreferences = (prefs: Record<string, boolean>) => {
    try {
      localStorage.setItem(MONITORING_STORAGE_KEY, JSON.stringify(prefs));
    } catch (error) {
      console.error("Failed to save monitoring preferences", error);
    }
  };

  const handleToggle = (id: string) => {
    setFunds(prev => prev.map(f =>
      f.id === id ? { ...f, isWatchlisted: !f.isWatchlisted } : f
    ));
  };

  const handleToggleMonitoring = async (id: string, enabled: boolean) => {
    // Update the fund's monitoring state
    setFunds(prev => prev.map(f =>
      f.id === id ? { ...f, monitoringEnabled: enabled } : f
    ));

    // Save to localStorage
    const prefs = loadMonitoringPreferences();
    prefs[id] = enabled;
    saveMonitoringPreferences(prefs);

    // Sync to backend
    try {
      const monitoredFunds = Object.keys(prefs).filter(code => prefs[code]);
      await fetch('http://127.0.0.1:8000/api/notifications/monitored-funds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ funds: monitoredFunds })
      });
    } catch (error) {
      console.error("Failed to sync monitoring preferences to backend:", error);
    }
  };

  // Calculate page counts
  // Exchange-traded funds: funds with real-time trading prices (valuation > 0)
  const lofCount = funds.filter(f => f.valuation > 0).length;
  const allCount = funds.length;
  const nasdaqCount = funds.filter(f => f.name.includes('纳指') || f.name.includes('纳斯达克')).length;

  const pages = [
    { id: 'all', label: '全部基金', count: allCount },
    { id: 'nasdaq', label: '纳斯达克', count: nasdaqCount },
    { id: 'lof', label: '场内基金', count: lofCount },
  ];

  const handlePageChange = (pageId: string) => {
    setCurrentPage(pageId);
  };

  const handleFundAdded = (code: string, name: string) => {
    // Reload funds when a new fund is added
    loadFunds();
  };

  const handleFundRemoved = (code: string) => {
    // Always reload funds, regardless of whether it was a user fund or preset fund
    loadFunds();
  };

  const handleDeleteFund = async (id: string) => {
    // Find fund by id and remove directly from both localStorage and display
    const fund = funds.find(f => f.id === id);
    if (fund) {
      // Show confirmation dialog
      if (window.confirm(`确定要删除基金 "${fund.name}" (${fund.code}) 吗？`)) {
        // Call backend API to delete from funds.json and monitoring database
        let backendDeleted = false;
        try {
          const deleteResponse = await fetch(`http://127.0.0.1:8000/api/fund/${fund.code}`, {
            method: 'DELETE',
          });
          if (deleteResponse.ok) {
            const result = await deleteResponse.json();
            if (result.success) {
              backendDeleted = true;
              console.log(`✅ Fund ${fund.code} deleted from funds.json and monitoring database`);
            } else {
              console.warn(`⚠️ Backend returned success=false for ${fund.code}:`, result.message);
            }
          } else {
            console.warn(`⚠️ Backend DELETE failed for ${fund.code}:`, deleteResponse.status, deleteResponse.statusText);
          }
        } catch (err) {
          console.error(`❌ Failed to call backend delete fund API for ${fund.code}:`, err);
        }

        // Remove from localStorage (regardless of backend success)
        removeUserFund(fund.code);

        // Update display immediately by filtering out the deleted fund
        setFunds(prev => prev.filter(f => f.id !== id));

        // Warn user if backend deletion failed
        if (!backendDeleted) {
          console.warn(`⚠️ Fund ${fund.code} only removed from frontend. Backend server may not be running. Fund may reappear on refresh.`);
        }
      }
    }
  };

  const loadFunds = async () => {
    setLoading(true);
    try {
      const data = await fetchQDIIFunds();
      setFunds(data);
    } catch (error) {
      console.error("Failed to fetch funds", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex justify-center w-full">
      {/* 
        Responsive Container: 
        - w-full for mobile
        - max-w-3xl for tablet/desktop to resemble a dashboard 
        - shadow for better aesthetics on desktop
      */}
      <div className="w-full max-w-3xl bg-white min-h-screen shadow-xl relative flex flex-col md:border-x md:border-gray-200">
        
        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center text-gray-400 gap-2 pb-20">
             <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#ea3323]"></div>
             <span className="text-sm">正在获取最新QDII数据...</span>
          </div>
        ) : (
          <>
            <NavBar
              currentPage={currentPage}
              pages={pages}
              onPageChange={handlePageChange}
            />
            <MonitoringControl />
            <HeadlineStats funds={funds} />
            <FundList
              funds={funds}
              currentPage={currentPage}
              onToggle={handleToggle}
              onDelete={handleDeleteFund}
              onToggleMonitoring={handleToggleMonitoring}
              onTriggerChange={() => {
                // Optional: Refresh data when triggers change
                // Currently no-op, but can be used to trigger refresh if needed
              }}
            />
          </>
        )}

        <FundManager
          onFundAdded={handleFundAdded}
          onFundRemoved={handleFundRemoved}
          allFunds={funds}
        />
        <Footer />
      </div>
    </div>
  );
};

export default App;