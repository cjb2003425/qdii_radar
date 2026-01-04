import React, { useState, useEffect } from 'react';
import { ControlPanel } from './components/ControlPanel';
import { FundRow } from './components/FundRow';
import FundManager from './components/FundManager';
import { Footer } from './components/Footer';
import { Fund } from './types';
import { fetchQDIIFunds } from './services/fundService';
import { initializeFunds } from './services/userFundService';
import { FundData } from './types/fund';
import { ArrowDown, RefreshCcw, LayoutDashboard } from 'lucide-react';

// Map FundData (from backend) to Fund (new UI format)
const mapFundDataToFund = (data: FundData): Fund => {
  const getLimitStatus = (text: string): Fund['limitStatus'] => {
    if (text.includes('暂停')) return 'danger';
    if (text.includes('限')) return text.includes('万') && parseInt(text) < 10 ? 'warning' : 'neutral';
    return 'info';
  };

  return {
    id: data.id,
    code: data.code,
    name: data.name,
    price: data.valuation || 0,
    priceChangePercent: data.valuationRate || 0,
    netValue: data.marketPrice || 0,
    netValueChangePercent: data.marketPriceRate || 0,
    premiumRate: data.premiumRate || 0,
    limitTag: data.limitText !== '—' ? data.limitText : undefined,
    limitStatus: getLimitStatus(data.limitText),
    isMonitorEnabled: data.isMonitorEnabled || false,
    hasSettings: true,
  };
};

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState('all');
  const [funds, setFunds] = useState<Fund[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Filter funds based on active tab
  const filteredFunds = funds.filter(fund => {
    if (activeTab === 'all') return true;
    if (activeTab === 'nasdaq') {
      return fund.name.includes('纳斯达克') || fund.name.includes('纳指');
    }
    if (activeTab === 'exchange') {
      return fund.price > 0; // Has trading price = exchange-traded
    }
    return true;
  });

  // Calculate counts
  const nasdaqCount = funds.filter(f => f.name.includes('纳斯达克') || f.name.includes('纳指')).length;
  const exchangeCount = funds.filter(f => f.price > 0).length;

  useEffect(() => {
    const loadFunds = async () => {
      try {
        // Initialize preset funds
        initializeFunds();

        const data = await fetchQDIIFunds();
        const mappedFunds = data.map(mapFundDataToFund);
        setFunds(mappedFunds);
      } catch (error) {
        console.error('Failed to load funds:', error);
      } finally {
        setLoading(false);
      }
    };
    loadFunds();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-slate-600">加载中...</p>
        </div>
      </div>
    );
  }

  const handleDelete = async (id: string) => {
    // Find the fund to get its code
    const fundToDelete = funds.find(f => f.id === id);
    if (!fundToDelete) return;

    // Confirm before deleting
    if (!window.confirm(`确定要删除基金 ${fundToDelete.code} (${fundToDelete.name}) 吗？`)) {
      return;
    }

    try {
      // Call backend API to delete the fund (from funds.json and monitoring database)
      const baseUrl = 'http://127.0.0.1:8088/api'; // TODO: Use API_CONFIG
      const response = await fetch(`${baseUrl}/fund/${fundToDelete.code}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          console.log(`✅ Fund ${fundToDelete.code} deleted from backend`);
        } else {
          console.warn(`⚠️ Backend returned success=false: ${result.message}`);
        }
      } else {
        console.warn(`⚠️ Backend DELETE failed: ${response.status}`);
      }
    } catch (error) {
      console.error('❌ Failed to delete fund from backend:', error);
      // Still remove from UI even if backend fails
    }

    // Remove from local state
    setFunds(funds.filter(f => f.id !== id));
  };

  const handleToggle = async (id: string) => {
    const fundToToggle = funds.find(f => f.id === id);
    if (!fundToToggle) return;

    const newEnabledState = !fundToToggle.isMonitorEnabled;

    try {
      // Call backend API to persist the change
      const baseUrl = 'http://127.0.0.1:8088/api/notifications';
      const response = await fetch(`${baseUrl}/monitored-funds/${fundToToggle.code}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: newEnabledState })
      });

      if (response.ok) {
        const result = await response.json();
        console.log(`✅ Fund ${fundToToggle.code} monitoring ${newEnabledState ? 'enabled' : 'disabled'}`);
      } else {
        console.error(`❌ Failed to update monitoring status: ${response.statusText}`);
      }
    } catch (error) {
      console.error('❌ Failed to update fund monitoring in backend:', error);
    }

    // Update local state
    setFunds(funds.map(f => f.id === id ? { ...f, isMonitorEnabled: newEnabledState } : f));
  };

  const handleFundAdded = async (code: string, name: string) => {
    // Refresh fund data from backend after adding
    try {
      const data = await fetchQDIIFunds();
      const mappedFunds = data.map(mapFundDataToFund);
      setFunds(mappedFunds);
    } catch (error) {
      console.error('Failed to refresh funds after adding:', error);
    }
  };

  const handleFundRemoved = (code: string) => {
    setFunds(funds.filter(f => f.code !== code));
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const data = await fetchQDIIFunds();
      const mappedFunds = data.map(mapFundDataToFund);
      setFunds(mappedFunds);
      console.log('✅ Fund data refreshed successfully');
    } catch (error) {
      console.error('❌ Failed to refresh fund data:', error);
      // Show error to user
      alert('刷新失败，请稍后重试');
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col selection:bg-indigo-100 selection:text-indigo-700 overflow-x-hidden">

      {/* Top Decoration */}
      <div className="h-36 md:h-64 bg-slate-900 w-full absolute top-0 left-0 -z-10 overflow-hidden">
        <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-indigo-600/20 rounded-full blur-3xl -mr-20 -mt-20"></div>
        <div className="absolute bottom-0 left-0 w-[300px] h-[300px] bg-emerald-600/10 rounded-full blur-3xl -ml-20 -mb-20"></div>
      </div>

      <div className="w-full max-w-6xl mx-auto px-2.5 md:px-8 pt-3 md:pt-6 pb-4">

        {/* Header Section */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-3 md:gap-4 mb-3 md:mb-5">
          <div>
             <h1 className="text-xl md:text-4xl font-extrabold text-white tracking-tight mb-0.5 md:mb-2 flex items-center gap-2 md:gap-3">
               <span className="bg-gradient-to-br from-indigo-400 to-purple-400 text-transparent bg-clip-text">FundMonitor</span>
               <span className="text-slate-400 text-base md:text-2xl font-light">Pro</span>
             </h1>
             <p className="text-slate-400 font-medium text-[10px] md:text-base opacity-80 md:opacity-100 hidden sm:block">Real-time premium tracking & arbitrage dashboard</p>
          </div>
          <div className="flex gap-2 self-end md:self-auto">
             <button
                onClick={handleRefresh}
                disabled={refreshing}
                className={`bg-slate-800 hover:bg-slate-700 active:bg-slate-600 text-slate-300 hover:text-white px-5 py-3 md:px-4 md:py-2 rounded-xl text-sm md:text-sm font-medium transition-colors border border-slate-700 flex items-center justify-center gap-2 min-h-[48px] min-w-[48px] touch-manipulation active:scale-95 ${
                  refreshing ? 'opacity-60 cursor-not-allowed' : ''
                }`}
                title="刷新基金数据"
             >
                <RefreshCcw size={18} className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
                <span className="hidden sm:inline">{refreshing ? '刷新中...' : 'Sync'}</span>
                <span className="sm:hidden">{refreshing ? '...' : 'Sync'}</span>
             </button>
          </div>
        </div>

        {/* Control Panel */}
        <ControlPanel />

        {/* Main Fund List */}
        <div className="mb-6">
            
            {/* Tabs & Filters */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-3 md:mb-4">
              <div className="bg-white p-1 rounded-xl shadow-sm border border-slate-200 inline-flex w-full sm:w-auto overflow-hidden">
                {[
                  { id: 'all', label: '全部基金', count: funds.length },
                  { id: 'nasdaq', label: '纳斯达克', count: nasdaqCount },
                  { id: 'exchange', label: '场内基金', count: exchangeCount }
                ].map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex-1 sm:flex-none px-2.5 py-2 md:px-4 md:py-1.5 rounded-lg text-sm md:text-sm font-medium transition-all flex items-center justify-center gap-1.5 whitespace-nowrap min-h-[44px] active:scale-95 ${
                      activeTab === tab.id
                        ? 'bg-slate-900 text-white shadow-md'
                        : 'text-slate-500 hover:text-slate-800 hover:bg-slate-50'
                    }`}
                  >
                    {tab.label}
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      activeTab === tab.id ? 'bg-slate-700 text-slate-200' : 'bg-slate-100 text-slate-500'
                    }`}>
                      {tab.count}
                    </span>
                  </button>
                ))}
              </div>

              <div className="text-xs text-slate-500 font-medium px-2 hidden sm:block">
                 共 <span className="font-bold text-slate-900">{filteredFunds.length}</span> 个监控项
              </div>
            </div>

            {/* List Container */}
            <div className="bg-white rounded-2xl shadow-soft border border-slate-200/60 overflow-hidden">
              {/* Mobile Cards */}
              <div className="md:hidden flex flex-col gap-3 p-2.5 bg-slate-50">
                {filteredFunds.map((fund) => (
                  <FundRow
                    key={`mobile-${fund.id}`}
                    fund={fund}
                    onDelete={handleDelete}
                    onToggle={handleToggle}
                  />
                ))}
              </div>

              {/* Desktop Table */}
              <div className="hidden md:block">
                <table className="w-full">
                  <thead className="bg-slate-50/80 border-b border-slate-100 backdrop-blur-sm">
                    <tr>
                      {[
                        { label: '基金名称', width: 'w-1/3' },
                        { label: '现价', width: 'w-1/6' },
                        { label: '净值', width: 'w-1/6' },
                        { label: '溢价率', width: 'w-1/6' },
                        { label: '操作', width: 'w-[100px]' }
                      ].map((header, i) => (
                        <th key={i} className={`px-4 py-2.5 text-left text-[11px] font-bold text-slate-400 uppercase tracking-wider ${header.width}`}>
                          <div className="flex items-center gap-1 cursor-pointer hover:text-slate-600 transition-colors">
                            {header.label}
                            {i < 4 && <ArrowDown size={12} strokeWidth={2.5}/>}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-slate-50">
                    {filteredFunds.map((fund) => (
                      <FundRow
                        key={`desktop-${fund.id}`}
                        fund={fund}
                        onDelete={handleDelete}
                        onToggle={handleToggle}
                      />
                    ))}
                  </tbody>
                </table>
              </div>

              {filteredFunds.length === 0 && (
                 <div className="p-12 text-center flex flex-col items-center gap-3">
                    <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center text-slate-300">
                      <LayoutDashboard size={24} />
                    </div>
                    <span className="text-slate-400 text-sm font-medium">暂无基金数据</span>
                 </div>
              )}
            </div>
        </div>

      </div>

      {/* Fund Manager - Floating Action Button */}
      <FundManager
        onFundAdded={handleFundAdded}
        onFundRemoved={handleFundRemoved}
        allFunds={funds.map(f => ({
          id: f.id,
          code: f.code,
          name: f.name,
          valuation: f.price,
          valuationRate: f.priceChangePercent,
          marketPrice: f.netValue,
          marketPriceRate: f.netValueChangePercent,
          premiumRate: f.premiumRate,
          limitText: f.limitTag || '—',
          isWatchlisted: false,
          isUserAdded: false
        }))}
      />

      {/* Footer */}
      <Footer />
    </div>
  );
};

export default App;