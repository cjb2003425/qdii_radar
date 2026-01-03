import React from 'react';

export const Footer: React.FC = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-slate-50 border-t border-slate-200 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex flex-col md:flex-row justify-between items-center gap-4">
          {/* App Info */}
          <div className="flex items-center gap-3">
            <div className="bg-gradient-to-br from-indigo-500 to-purple-600 text-white p-2 rounded-lg">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-700">QDII Fund Radar</h3>
              <p className="text-xs text-slate-500">实时监控纳斯达克基金溢价率</p>
            </div>
          </div>

          {/* Links */}
          <div className="flex items-center gap-6 text-xs text-slate-600">
            <a
              href="https://github.com/cjb2003425/qdii_radar"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-indigo-600 transition-colors"
            >
              GitHub
            </a>
            <a
              href="https://fundf10.eastmoney.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-indigo-600 transition-colors"
            >
              数据来源: 东方财富
            </a>
          </div>

          {/* Copyright */}
          <div className="text-xs text-slate-500">
            © {currentYear} QDII Fund Radar
          </div>
        </div>

        {/* Additional Info */}
        <div className="mt-4 pt-4 border-t border-slate-200">
          <div className="flex flex-wrap justify-center gap-4 text-xs text-slate-500">
            <span>📊 监控 {39} 只基金</span>
            <span>⚡ 实时数据</span>
            <span>🔔 智能提醒</span>
            <span>🌐 NASDAQ & S&P 500 指数</span>
          </div>
        </div>
      </div>
    </footer>
  );
};
