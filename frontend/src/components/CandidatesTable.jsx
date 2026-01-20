import React from 'react';
import { Clock, AlertCircle, CheckCircle } from 'lucide-react';

const CandidatesTable = ({ candidates }) => {
    if (!candidates || candidates.length === 0) {
        return (
            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-sm h-64 flex items-center justify-center text-slate-600">
                <div className="text-center">
                    <Clock className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>Scanning market for opportunities...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="bg-slate-950 rounded-xl border border-slate-800 font-mono text-sm h-64 flex flex-col shadow-inner overflow-hidden">
            <div className="p-2 border-b border-slate-800 bg-slate-900/50 text-xs text-slate-500 uppercase tracking-wider font-semibold px-4 flex justify-between items-center">
                <span>Market Scanner Watchlist</span>
                <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-400">Top 15</span>
            </div>
            <div className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                <table className="w-full text-left border-collapse">
                    <thead className="bg-slate-900/30 text-xs text-slate-500 sticky top-0 backdrop-blur-sm">
                        <tr>
                            <th className="px-4 py-2 font-medium">Symbol</th>
                            <th className="px-4 py-2 font-medium">Price</th>
                            <th className="px-4 py-2 font-medium">RSI</th>
                            <th className="px-4 py-2 font-medium">RVOL</th>
                            <th className="px-4 py-2 font-medium text-right">Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                        {candidates.map((cand) => (
                            <tr key={cand.symbol} className="hover:bg-slate-800/30 transition-colors">
                                <td className="px-4 py-2 font-bold text-slate-300">{cand.symbol}</td>
                                <td className="px-4 py-2 text-slate-400">${cand.price.toFixed(4)}</td>
                                <td className={`px-4 py-2 font-bold ${cand.rsi < 30 ? 'text-emerald-400' : 'text-slate-400'}`}>
                                    {cand.rsi.toFixed(1)}
                                </td>
                                <td className="px-4 py-2 text-slate-400">{cand.rvol.toFixed(1)}x</td>
                                <td className="px-4 py-2 text-right">
                                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold border ${cand.status === 'BUY'
                                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                                            : 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                                        }`}>
                                        {cand.status === 'BUY' ? <CheckCircle className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                                        {cand.status}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default CandidatesTable;
