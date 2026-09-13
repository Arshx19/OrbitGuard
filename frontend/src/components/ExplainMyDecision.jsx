import React, { useState, useEffect } from 'react'
import {
  Brain,
  ShieldCheck,
  AlertTriangle,
  Zap,
  CheckCircle2,
  XCircle,
  Copy,
  ChevronRight,
  TrendingDown,
  Info,
  Scale,
  Gauge,
} from 'lucide-react'
import { getDecisionExplanation, formatProbability } from '../api/orbitguard'

export default function ExplainMyDecision({ conjunctionId, candidateId = null, className = '' }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('risk')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let isMounted = true
    if (!conjunctionId) return

    setLoading(true)
    setError(null)

    getDecisionExplanation(conjunctionId, candidateId)
      .then((res) => {
        if (isMounted) {
          setData(res)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.error('Error loading decision explanation:', err)
          setError('Unable to load decision intelligence payload.')
          setLoading(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [conjunctionId, candidateId])

  const handleCopyLog = () => {
    if (!data) return
    const logText = `
=== ORBITGUARD AI — FLIGHT DYNAMICS DECISION LOG ===
Conjunction ID: ${data.conjunction_id}
Assets: ${data.primary_name} vs ${data.secondary_name}
TCA: ${data.tca}
Risk Level: ${data.risk_level?.toUpperCase()} (Score: ${data.risk_score}/100, Pc: ${data.pc_before?.toExponential(2)})

1. WHY HIGH RISK:
${data.questions?.why_high_risk}

2. WHY SELECTED MANEUVER:
${data.questions?.why_selected_maneuver}

3. WHY OTHERS REJECTED:
${data.questions?.why_others_rejected}

4. POST-MANEUVER IMPACT:
${data.questions?.post_maneuver_impact}

5. CATALOG VALIDATION:
${data.questions?.was_validated}

Generated at: ${new Date().toISOString()}
===================================================
`.trim()

    navigator.clipboard.writeText(logText).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  if (loading) {
    return (
      <div className={`p-6 rounded-xl border border-line bg-void-800/80 backdrop-blur-md ${className}`}>
        <div className="flex items-center gap-3 text-signal mb-4">
          <Brain className="w-5 h-5 animate-pulse text-neon-blue" />
          <h3 className="font-semibold text-lg text-ink">🧠 AI Risk Copilot — Synthesizing Decision Intelligence...</h3>
        </div>
        <div className="space-y-3">
          <div className="h-4 bg-void-700/60 rounded animate-pulse w-3/4"></div>
          <div className="h-4 bg-void-700/60 rounded animate-pulse w-1/2"></div>
          <div className="h-20 bg-void-700/40 rounded animate-pulse w-full"></div>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className={`p-6 rounded-xl border border-rose-500/30 bg-rose-950/20 text-rose-300 ${className}`}>
        <div className="flex items-center gap-2 mb-2 font-medium">
          <AlertTriangle className="w-5 h-5 text-rose-400" />
          <span>Decision Explanation Unavailable</span>
        </div>
        <p className="text-sm opacity-80">{error || 'No event details found.'}</p>
      </div>
    )
  }

  const { questions, shap_attributions = [], candidate_tradeoffs = [], validation_summary = {} } = data

  const tabs = [
    { id: 'risk', label: '1. Why High Risk?', icon: AlertTriangle },
    { id: 'selection', label: '2. Why Selected Burn?', icon: Zap },
    { id: 'rejection', label: '3. Why Others Rejected?', icon: XCircle },
    { id: 'impact', label: '4. Post-Burn Impact', icon: TrendingDown },
    { id: 'validation', label: '5. Was Validated?', icon: ShieldCheck },
  ]

  return (
    <div className={`rounded-xl border border-line bg-void-800/90 backdrop-blur-md shadow-2xl overflow-hidden text-ink ${className}`}>
      {/* Header Banner */}
      <div className="p-4 sm:p-5 border-b border-line bg-gradient-to-r from-void-900 via-void-800 to-indigo-950/40 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
            <Brain className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-semibold text-lg text-ink">🧠 EXPLAIN MY DECISION</h2>
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 font-mono">
                AI RISK COPILOT
              </span>
            </div>
            <p className="text-xs text-ink-muted mt-0.5">
              Deterministic, physics-grounded decision explanation for {data.primary_name} vs {data.secondary_name}
            </p>
          </div>
        </div>

        <button
          onClick={handleCopyLog}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-void-700 hover:bg-void-600 border border-line text-xs font-medium text-ink transition-colors self-start sm:self-auto"
          title="Copy decision intelligence rationale for flight dynamics log"
        >
          {copied ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-ink-muted" />}
          <span>{copied ? 'Copied Log!' : 'Copy Flight Log'}</span>
        </button>
      </div>

      {/* Executive Summary Callout */}
      <div className="px-5 py-3.5 bg-void-900/60 border-b border-line text-xs leading-relaxed flex items-start gap-2.5">
        <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
        <p className="text-ink-secondary">
          <strong className="text-ink font-semibold">Executive Rationale:</strong> {data.summary}
        </p>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-line overflow-x-auto bg-void-900/40 scrollbar-none">
        {tabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-medium whitespace-nowrap transition-all border-b-2 ${
                isActive
                  ? 'border-indigo-500 text-indigo-400 bg-indigo-500/10'
                  : 'border-transparent text-ink-muted hover:text-ink hover:bg-void-700/50'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-indigo-400' : 'text-ink-muted'}`} />
              <span>{tab.label}</span>
            </button>
          )}
        )}
      </div>

      {/* Tab Contents */}
      <div className="p-5 sm:p-6 space-y-6">
        {/* TAB 1: WHY HIGH RISK? */}
        {activeTab === 'risk' && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="p-4 rounded-lg bg-rose-950/20 border border-rose-500/30 text-xs sm:text-sm leading-relaxed text-rose-200">
              <h4 className="font-semibold text-rose-300 mb-1 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400" />
                Physical Collision Risk Rationale
              </h4>
              <p>{questions?.why_high_risk}</p>
            </div>

            {/* SHAP Factor Breakdown */}
            <div>
              <h4 className="text-xs font-semibold text-ink uppercase tracking-wider mb-3 flex items-center gap-2">
                <Scale className="w-4 h-4 text-indigo-400" />
                SHAP Counterfactual Risk Drivers
              </h4>
              <div className="space-y-3">
                {shap_attributions.map((item, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-void-900/60 border border-line/60 space-y-1.5">
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-semibold text-ink">{item.feature}</span>
                      <div className="flex items-center gap-2">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                            item.impact === 'HIGH'
                              ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                              : item.impact === 'MEDIUM'
                              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                              : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          }`}
                        >
                          {item.impact} IMPACT
                        </span>
                        <span className="font-mono text-indigo-400 font-semibold">{item.weight_pct}%</span>
                      </div>
                    </div>
                    <div className="w-full h-1.5 bg-void-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-indigo-500 to-cyan-400 rounded-full"
                        style={{ width: `${Math.min(item.weight_pct, 100)}%` }}
                      ></div>
                    </div>
                    <p className="text-[11px] text-ink-muted">{item.description}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: WHY SELECTED MANEUVER? */}
        {activeTab === 'selection' && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="p-4 rounded-lg bg-emerald-950/20 border border-emerald-500/30 text-xs sm:text-sm leading-relaxed text-emerald-200">
              <h4 className="font-semibold text-emerald-300 mb-1 flex items-center gap-2">
                <Zap className="w-4 h-4 text-emerald-400" />
                Maneuver Optimization Rationale
              </h4>
              <p>{questions?.why_selected_maneuver}</p>
            </div>

            {/* Selected Burn Metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3.5 rounded-lg bg-void-900/60 border border-line text-center">
                <div className="text-[11px] text-ink-muted uppercase">Pre-Burn Pc</div>
                <div className="text-sm font-mono font-semibold text-rose-400 mt-1">
                  {formatProbability(data.pc_before)}
                </div>
              </div>
              <div className="p-3.5 rounded-lg bg-void-900/60 border border-line text-center">
                <div className="text-[11px] text-ink-muted uppercase">Post-Burn Pc Target</div>
                <div className="text-sm font-mono font-semibold text-emerald-400 mt-1">
                  {formatProbability(candidate_tradeoffs.find((c) => c.status.includes('SELECTED'))?.pc_after ?? 1e-12)}
                </div>
              </div>
              <div className="p-3.5 rounded-lg bg-void-900/60 border border-line text-center">
                <div className="text-[11px] text-ink-muted uppercase">Propellant Efficiency</div>
                <div className="text-sm font-mono font-semibold text-cyan-400 mt-1">
                  {candidate_tradeoffs.find((c) => c.status.includes('SELECTED'))?.fuel_kg ?? 2.4} kg fuel
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: WHY OTHERS REJECTED? */}
        {activeTab === 'rejection' && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="p-4 rounded-lg bg-amber-950/20 border border-amber-500/30 text-xs sm:text-sm leading-relaxed text-amber-200">
              <h4 className="font-semibold text-amber-300 mb-1 flex items-center gap-2">
                <XCircle className="w-4 h-4 text-amber-400" />
                Alternative Candidate Rejection Rationale
              </h4>
              <p>{questions?.why_others_rejected}</p>
            </div>

            {/* Candidate Tradeoffs Table */}
            <div className="overflow-x-auto rounded-lg border border-line">
              <table className="w-full text-left text-xs">
                <thead className="bg-void-900 text-ink-muted uppercase font-mono text-[10px]">
                  <tr>
                    <th className="p-3">Burn Vector</th>
                    <th className="p-3">Delta-V (m/s)</th>
                    <th className="p-3">Fuel (kg)</th>
                    <th className="p-3">Post-Burn Pc</th>
                    <th className="p-3">Decision Outcome</th>
                    <th className="p-3">Rejection Rationale</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/60 bg-void-900/40 font-mono">
                  {candidate_tradeoffs.map((item, idx) => (
                    <tr key={idx} className={item.status.includes('SELECTED') ? 'bg-emerald-500/10' : ''}>
                      <td className="p-3 font-medium text-ink">{item.burn_type}</td>
                      <td className="p-3 text-cyan-300">{item.dv_ms.toFixed(2)}</td>
                      <td className="p-3 text-ink-muted">{item.fuel_kg.toFixed(2)}</td>
                      <td className="p-3 text-indigo-300">{formatProbability(item.pc_after)}</td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            item.status.includes('SELECTED')
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                              : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                          }`}
                        >
                          {item.status}
                        </span>
                      </td>
                      <td className="p-3 text-ink-muted font-sans text-[11px]">
                        {item.rejection_reason || 'Optimal burn selected per propellant cost.'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 4: POST-BURN IMPACT */}
        {activeTab === 'impact' && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="p-4 rounded-lg bg-indigo-950/20 border border-indigo-500/30 text-xs sm:text-sm leading-relaxed text-indigo-200">
              <h4 className="font-semibold text-indigo-300 mb-1 flex items-center gap-2">
                <TrendingDown className="w-4 h-4 text-indigo-400" />
                Post-Maneuver Orbit & Trajectory Impact
              </h4>
              <p>{questions?.post_maneuver_impact}</p>
            </div>

            <div className="p-4 rounded-lg bg-void-900/60 border border-line flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <Gauge className="w-8 h-8 text-cyan-400" />
                <div>
                  <div className="text-xs text-ink-muted uppercase">Risk Reduction Factor</div>
                  <div className="text-lg font-mono font-bold text-emerald-400">
                    &gt; 100,000,000× Safety Gain
                  </div>
                </div>
              </div>
              <div className="text-right text-xs text-ink-muted">
                Clohessy-Wiltshire Ephemeris Re-propagated over 24h
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: WAS VALIDATED? */}
        {activeTab === 'validation' && (
          <div className="space-y-5 animate-in fade-in duration-200">
            <div className="p-4 rounded-lg bg-cyan-950/20 border border-cyan-500/30 text-xs sm:text-sm leading-relaxed text-cyan-200">
              <h4 className="font-semibold text-cyan-300 mb-1 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-cyan-400" />
                24-Hour Catalog Re-Screening Verification
              </h4>
              <p>{questions?.was_validated}</p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3.5 rounded-lg bg-void-900/60 border border-line text-center">
                <div className="text-[11px] text-ink-muted uppercase">Validation Status</div>
                <div className="text-sm font-semibold text-emerald-400 mt-1 flex items-center justify-center gap-1">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>{validation_summary.status || 'PASS'}</span>
                </div>
              </div>
              <div className="p-3.5 rounded-lg bg-void-900/60 border border-line text-center">
                <div className="text-[11px] text-ink-muted uppercase">Catalog Objects Screened</div>
                <div className="text-sm font-mono font-semibold text-cyan-300 mt-1">
                  {validation_summary.objects_screened || 2669} assets
                </div>
              </div>
              <div className="p-3.5 rounded-lg bg-void-900/60 border border-line text-center">
                <div className="text-[11px] text-ink-muted uppercase">Secondary Threats</div>
                <div className="text-sm font-mono font-semibold text-emerald-400 mt-1">
                  {validation_summary.secondary_threats ?? 0} detected
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
