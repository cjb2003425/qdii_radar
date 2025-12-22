import React, { useState, useEffect } from 'react';
import FundList from './components/FundList';
import { FundData } from './types';
import { fetchQDIIFunds } from './services/fundService';

const App: React.FC = () => {
  const [funds, setFunds] = useState<FundData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
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

    loadFunds();
  }, []);

  const handleToggle = (id: string) => {
    setFunds(prev => prev.map(f => 
      f.id === id ? { ...f, isWatchlisted: !f.isWatchlisted } : f
    ));
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
          <FundList 
            funds={funds} 
            onToggle={handleToggle} 
          />
        )}
        
      </div>
    </div>
  );
};

export default App;