import React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import { Trash2, TrendingUp, TrendingDown } from 'lucide-react';

const PositionsTable = ({ positions }) => {
    const queryClient = useQueryClient();

    const sellMutation = useMutation({
        mutationFn: api.sellPosition,
        onSuccess: () => {
            queryClient.invalidateQueries(['positions']);
            queryClient.invalidateQueries(['summary']);
        },
    });

    const handleSell = (symbol) => {
        if (window.confirm(`Are you sure you want to sell ${symbol}?`)) {
            sellMutation.mutate(symbol);
        }
    };

    if (!positions || positions.length === 0) {
        return (
            <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-lg text-center text-slate-500">
                No active positions
            </div>
        );
    }

    return (
        <div className="bg-slate-800 rounded-xl border border-slate-700 shadow-lg overflow-hidden">
            <div className="p-6 border-b border-slate-700">
                <h3 className="text-lg font-semibold text-white">Active Positions</h3>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-300">
                    <thead className="bg-slate-900/50 text-slate-400 uppercase font-medium">
                        <tr>
                            <th className="px-6 py-4">Symbol</th>
                            <th className="px-6 py-4">Entry Price</th>
                            <th className="px-6 py-4">Current Price</th>
                            <th className="px-6 py-4">Max Price</th>
                            <th className="px-6 py-4">Stop Price</th>
                            <th className="px-6 py-4">Invested</th>
                            <th className="px-6 py-4">PnL (%)</th>
                            <th className="px-6 py-4">PnL ($)</th>
                            <th className="px-6 py-4">Status</th>
                            <th className="px-6 py-4 text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700">
                        {positions.map((pos) => {
                            const isProfit = pos.pnl_est_percent >= 0;
                            return (
                                <tr key={pos.symbol} className="hover:bg-slate-700/30 transition-colors">
                                    <td className="px-6 py-4 font-bold text-white">{pos.symbol}</td>
                                    <td className="px-6 py-4">${pos.buy_price.toFixed(4)}</td>
                                    <td className="px-6 py-4 font-mono text-slate-200">${pos.current_price?.toFixed(4) || '---'}</td>
                                    <td className="px-6 py-4 text-slate-400">${pos.highest_price.toFixed(4)}</td>
                                    <td className="px-6 py-4 text-amber-400">${pos.stop_price.toFixed(4)}</td>
                                    <td className="px-6 py-4">${pos.amount_usdt.toFixed(2)}</td>
                                    <td className={`px-6 py-4 font-bold ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                                        <div className="flex items-center gap-1">
                                            {isProfit ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                            {pos.pnl_est_percent}%
                                        </div>
                                    </td>
                                    <td className={`px-6 py-4 font-bold ${pos.pnl_usdt >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                        ${pos.pnl_usdt?.toFixed(2)}
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className={`px-2 py-1 rounded text-xs font-bold border ${pos.status_label.includes('MOONSHOT') ? 'bg-purple-500/10 text-purple-400 border-purple-500/30' :
                                            pos.status_label.includes('TENDÊNCIA') ? 'bg-blue-500/10 text-blue-400 border-blue-500/30' :
                                                'bg-slate-500/10 text-slate-400 border-slate-500/30'
                                            }`}>
                                            {pos.status_label}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <button
                                            onClick={() => handleSell(pos.symbol)}
                                            disabled={sellMutation.isLoading}
                                            className="p-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded-lg transition-colors disabled:opacity-50"
                                            title="Sell Position"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default PositionsTable;
