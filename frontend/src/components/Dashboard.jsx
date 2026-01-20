import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import KPISection from './KPISection';
import EquityChart from './EquityChart';
import PositionsTable from './PositionsTable';
import CandidatesTable from './CandidatesTable';
import { RefreshCw } from 'lucide-react';

const Dashboard = () => {
    // 1. Fetch Summary (Wallet KPIs)
    const { data: summary, isLoading: loadingSummary, refetch: refetchSummary } = useQuery({
        queryKey: ['summary'],
        queryFn: api.getSummary,
        refetchInterval: 5000, // 5s
    });

    // 2. Fetch Positions
    const { data: positions, isLoading: loadingPositions, refetch: refetchPositions } = useQuery({
        queryKey: ['positions'],
        queryFn: api.getPositions,
        refetchInterval: 3000, // 3s (Faster for PnL)
    });

    // 3. Fetch History (Chart)
    const { data: history, isLoading: loadingHistory, refetch: refetchHistory } = useQuery({
        queryKey: ['history'],
        queryFn: api.getHistory,
        refetchInterval: 60000, // 1m
    });

    // 4. Fetch Candidates (Watchlist)
    const { data: candidates, isLoading: loadingCandidates, refetch: refetchCandidates } = useQuery({
        queryKey: ['candidates'],
        queryFn: api.getCandidates,
        refetchInterval: 5000, // 5s
    });

    const handleRefresh = () => {
        refetchSummary();
        refetchPositions();
        refetchHistory();
        refetchCandidates();
    };

    return (
        <div className="min-h-screen bg-slate-950 text-slate-200 p-6 font-sans selection:bg-indigo-500/30">
            <div className="max-w-7xl mx-auto space-y-6">

                {/* Header */}
                <div className="flex justify-between items-center mb-8">
                    <div>
                        <h1 className="text-3xl font-bold bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">
                            DEX V2 Auto-Trader
                        </h1>
                        <p className="text-slate-500 text-sm mt-1">AI-Powered Scalping Bot</p>
                    </div>
                    <button
                        onClick={handleRefresh}
                        className="p-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-all border border-slate-700 shadow-sm group"
                    >
                        <RefreshCw className="w-5 h-5 text-slate-400 group-hover:rotate-180 transition-transform duration-500" />
                    </button>
                </div>

                {/* KPIs */}
                <KPISection summary={summary} loading={loadingSummary} />

                {/* Main Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                    {/* Left Column: Chart & Positions (2/3 width) */}
                    <div className="lg:col-span-2 space-y-6">
                        <EquityChart history={history} loading={loadingHistory} />
                        <PositionsTable positions={positions} loading={loadingPositions} />
                    </div>

                    {/* Right Column: Watchlist (1/3 width) */}
                    <div className="space-y-6">
                        <CandidatesTable candidates={candidates} />

                        {/* Mini Status Card (Optional) */}
                        <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800">
                            <h4 className="text-xs font-bold text-slate-500 uppercase mb-2">Bot Status</h4>
                            <div className="flex items-center gap-2">
                                <span className="relative flex h-3 w-3">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                                </span>
                                <span className="text-sm text-emerald-400 font-medium">Running</span>
                            </div>
                            <p className="text-xs text-slate-600 mt-2">
                                Last update: {summary?.updated_at || '...'}
                            </p>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
};

export default Dashboard;
