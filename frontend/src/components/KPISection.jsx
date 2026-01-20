import React from 'react';
import { TrendingUp, TrendingDown, DollarSign, Activity } from 'lucide-react';

const KPISection = ({ summary }) => {
    if (!summary || !summary.wallet_summary) return null;

    const { wallet_summary, active_positions_count } = summary;
    const equity = wallet_summary.current_equity;

    // Mock daily change for now, or calculate if history is available
    const dailyChange = 0;
    const isPositive = dailyChange >= 0;

    return (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            {/* Total Equity */}
            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-lg">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-slate-400 text-sm font-medium">Total Equity</span>
                    <DollarSign className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="text-2xl font-bold text-white">
                    ${equity.toFixed(2)}
                </div>
                <div className={`text-xs mt-1 ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {isPositive ? '+' : ''}{dailyChange}% (24h)
                </div>
            </div>

            {/* Active Positions */}
            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-lg">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-slate-400 text-sm font-medium">Active Positions</span>
                    <Activity className="w-4 h-4 text-blue-400" />
                </div>
                <div className="text-2xl font-bold text-white">
                    {active_positions_count}
                </div>
                <div className="text-xs text-slate-500 mt-1">
                    Running strategies
                </div>
            </div>

            {/* Exposure (Mock) */}
            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-lg">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-slate-400 text-sm font-medium">Exposure</span>
                    <TrendingUp className="w-4 h-4 text-purple-400" />
                </div>
                <div className="text-2xl font-bold text-white">
                    100%
                </div>
                <div className="text-xs text-slate-500 mt-1">
                    Capital deployed
                </div>
            </div>

            {/* Win Rate (Mock) */}
            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-lg">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-slate-400 text-sm font-medium">Win Rate</span>
                    <TrendingDown className="w-4 h-4 text-amber-400" />
                </div>
                <div className="text-2xl font-bold text-white">
                    65%
                </div>
                <div className="text-xs text-slate-500 mt-1">
                    Last 30 days
                </div>
            </div>
        </div>
    );
};

export default KPISection;
