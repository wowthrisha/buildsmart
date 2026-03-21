import { useState } from 'react';
import { checkCompliance } from '../api';

const ROAD_WIDTHS = [10, 12, 15, 20, 24, 30, 40];
const ZONE_OPTIONS = [
  { value: 'residential_R1', label: 'Residential R1' },
  { value: 'residential_R2', label: 'Residential R2' },
  { value: 'commercial_C1',  label: 'Commercial C1'  },
];

const STATUS_STYLES = {
  PASS:     { card: 'bg-green-50 border-green-300',  badge: 'bg-green-100 text-green-800',  icon: '🟢' },
  MARGINAL: { card: 'bg-yellow-50 border-yellow-300', badge: 'bg-yellow-100 text-yellow-800', icon: '🟡' },
  FAIL:     { card: 'bg-red-50 border-red-300',      badge: 'bg-red-100 text-red-800',      icon: '🔴' },
};

const OVERALL_STYLES = {
  PASS:     'bg-green-100 text-green-800 border-green-300',
  MARGINAL: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  FAIL:     'bg-red-100 text-red-800 border-red-300',
};

const defaultForm = {
  road_width_ft: '20',
  provided_front_m: '',
  provided_rear_m: '',
  provided_side_m: '',
  plot_area_sqm: '',
  proposed_builtup_sqm: '',
  footprint_sqm: '',
  proposed_height_m: '',
  floors: '2',
  zone_type: 'residential_R1',
  building_type: 'residential',
};

export default function ComplianceChecker() {
  const [form, setForm] = useState(defaultForm);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const set = (key, val) => setForm((f) => ({ ...f, [key]: val }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const payload = {
        road_width_ft:        parseInt(form.road_width_ft),
        provided_front_m:     parseFloat(form.provided_front_m),
        provided_rear_m:      parseFloat(form.provided_rear_m),
        provided_side_m:      parseFloat(form.provided_side_m),
        plot_area_sqm:        parseFloat(form.plot_area_sqm),
        proposed_builtup_sqm: parseFloat(form.proposed_builtup_sqm),
        footprint_sqm:        parseFloat(form.footprint_sqm),
        proposed_height_m:    parseFloat(form.proposed_height_m),
        floors:               parseInt(form.floors),
        zone_type:            form.zone_type,
        building_type:        form.building_type,
      };
      const { data } = await checkCompliance(payload);
      setResult(data);
    } catch (e) {
      setError('Could not reach the server. Make sure the backend is running on port 8000.');
    } finally {
      setLoading(false);
    }
  };

  const inputCls = 'w-full border border-gray-300 rounded-lg px-3 py-2 text-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400';
  const labelCls = 'block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1';

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Compliance Check</h1>
        <p className="text-sm text-gray-500 mt-1">
          Enter your building parameters to check against TNCDBR 2019 rules.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-5">

        {/* Row 1 */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Road Width</label>
            <select value={form.road_width_ft} onChange={(e) => set('road_width_ft', e.target.value)} className={inputCls}>
              {ROAD_WIDTHS.map((w) => <option key={w} value={w}>{w}ft</option>)}
            </select>
          </div>
          <div>
            <label className={labelCls}>Number of Floors</label>
            <select value={form.floors} onChange={(e) => set('floors', e.target.value)} className={inputCls}>
              {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
        </div>

        {/* Setbacks */}
        <div>
          <p className={labelCls}>Setbacks (metres)</p>
          <div className="grid grid-cols-3 gap-3">
            {[
              { key: 'provided_front_m', label: 'Front' },
              { key: 'provided_rear_m',  label: 'Rear'  },
              { key: 'provided_side_m',  label: 'Side'  },
            ].map(({ key, label }) => (
              <div key={key}>
                <label className="block text-xs text-gray-400 mb-1">{label}</label>
                <input
                  type="number" min="0" step="0.1" required
                  value={form[key]}
                  onChange={(e) => set(key, e.target.value)}
                  className={inputCls}
                  placeholder="0.0"
                />
              </div>
            ))}
          </div>
        </div>

        {/* Areas */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Plot Area (sq.m)</label>
            <input type="number" min="0" step="0.1" required value={form.plot_area_sqm}
              onChange={(e) => set('plot_area_sqm', e.target.value)} className={inputCls} placeholder="e.g. 150" />
          </div>
          <div>
            <label className={labelCls}>Proposed Built-up Area (sq.m)</label>
            <input type="number" min="0" step="0.1" required value={form.proposed_builtup_sqm}
              onChange={(e) => set('proposed_builtup_sqm', e.target.value)} className={inputCls} placeholder="e.g. 210" />
          </div>
          <div>
            <label className={labelCls}>Ground Floor Footprint (sq.m)</label>
            <input type="number" min="0" step="0.1" required value={form.footprint_sqm}
              onChange={(e) => set('footprint_sqm', e.target.value)} className={inputCls} placeholder="e.g. 90" />
          </div>
          <div>
            <label className={labelCls}>Proposed Height (m)</label>
            <input type="number" min="0" step="0.1" required value={form.proposed_height_m}
              onChange={(e) => set('proposed_height_m', e.target.value)} className={inputCls} placeholder="e.g. 8.5" />
          </div>
        </div>

        {/* Zone & Type */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Zone Type</label>
            <select value={form.zone_type} onChange={(e) => set('zone_type', e.target.value)} className={inputCls}>
              {ZONE_OPTIONS.map(({ value, label }) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelCls}>Building Type</label>
            <select value={form.building_type} onChange={(e) => set('building_type', e.target.value)} className={inputCls}>
              <option value="residential">Residential</option>
              <option value="commercial">Commercial</option>
            </select>
          </div>
        </div>

        {error && <p className="text-red-500 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-40 transition flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
              </svg>
              Checking…
            </>
          ) : 'Run Compliance Check'}
        </button>
      </form>

      {/* Results */}
      {result && !result.error && (
        <div className="space-y-4">
          {/* Overall status badge */}
          <div className={`flex items-center gap-3 p-4 rounded-xl border text-sm font-semibold ${OVERALL_STYLES[result.overall_status]}`}>
            <span className="text-xl">{STATUS_STYLES[result.overall_status]?.icon}</span>
            <div>
              <span className="text-xs uppercase tracking-wide opacity-70">Overall Status</span>
              <p className="text-lg font-bold">{result.overall_status}</p>
            </div>
            <p className="ml-auto text-sm font-normal max-w-xs text-right">{result.summary}</p>
          </div>

          {/* Individual rule cards */}
          {result.results.map((r) => {
            const s = STATUS_STYLES[r.status] || STATUS_STYLES.FAIL;
            return (
              <div key={r.rule_name} className={`rounded-xl border p-4 space-y-2 ${s.card}`}>
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-gray-800 flex items-center gap-2">
                    {s.icon} {r.rule_name}
                  </span>
                  <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${s.badge}`}>
                    {r.status}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs text-gray-600">
                  <div><span className="font-medium">Provided:</span> {r.provided_value} {r.gap_unit}</div>
                  <div><span className="font-medium">Required:</span> {r.required_value} {r.gap_unit}</div>
                  <div><span className="font-medium">Gap:</span> {r.gap > 0 ? '+' : ''}{r.gap} {r.gap_unit}</div>
                </div>
                <p className="text-sm text-gray-700 bg-white/60 rounded-lg px-3 py-2">
                  💡 {r.fix_suggestion}
                </p>
                <p className="text-xs text-gray-400">{r.source_rule} · {r.go_number}</p>
              </div>
            );
          })}

          {/* Disclaimer */}
          <p className="text-xs text-gray-400 text-center px-4 pb-2">{result.disclaimer}</p>
        </div>
      )}

      {result?.error && (
        <div className="bg-red-50 border border-red-300 rounded-xl p-4 text-sm text-red-700">
          ⚠️ {result.message}
        </div>
      )}
    </div>
  );
}
