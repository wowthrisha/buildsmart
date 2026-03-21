import { useState } from 'react';
import { getFeeEstimate } from '../api';

const fmt = (n) => '₹' + Number(n).toLocaleString('en-IN');

export default function FeeCalculator() {
  const [form, setForm] = useState({
    authority: 'CCMC',
    building_type: 'residential',
    builtup_area_sqm: '',
  });
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
      const { data } = await getFeeEstimate({
        authority: form.authority,
        building_type: form.building_type,
        builtup_area_sqm: parseFloat(form.builtup_area_sqm),
      });
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
    <div className="max-w-xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Fee Estimate</h1>
        <p className="text-sm text-gray-500 mt-1">
          Approximate government fees for your building permit application.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
        <div>
          <label className={labelCls}>Authority</label>
          <select value={form.authority} onChange={(e) => set('authority', e.target.value)} className={inputCls}>
            <option value="CCMC">CCMC — Coimbatore City Municipal Corporation</option>
            <option value="DTCP">DTCP — Directorate of Town &amp; Country Planning</option>
            <option value="LPA">LPA — Local Planning Authority</option>
          </select>
        </div>
        <div>
          <label className={labelCls}>Building Type</label>
          <select value={form.building_type} onChange={(e) => set('building_type', e.target.value)} className={inputCls}>
            <option value="residential">Residential</option>
            <option value="commercial">Commercial</option>
          </select>
        </div>
        <div>
          <label className={labelCls}>Built-up Area (sq.m)</label>
          <input
            type="number" min="0" step="0.1" required
            value={form.builtup_area_sqm}
            onChange={(e) => set('builtup_area_sqm', e.target.value)}
            className={inputCls}
            placeholder="e.g. 150"
          />
        </div>

        {error && <p className="text-red-500 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-40 transition"
        >
          {loading ? 'Calculating…' : 'Get Fee Estimate'}
        </button>
      </form>

      {result && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
          <h2 className="font-semibold text-gray-700">
            Estimate for {result.builtup_area_sqm} sq.m · {result.authority}
          </h2>

          {/* Government fees table */}
          <table className="w-full text-sm">
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="py-2.5 text-gray-600">Scrutiny Fee</td>
                <td className="py-2.5 text-right text-gray-800">{fmt(result.government_fees.scrutiny_fee_rs)}</td>
              </tr>
              <tr>
                <td className="py-2.5 text-gray-600">Permit Fee</td>
                <td className="py-2.5 text-right text-gray-800">{fmt(result.government_fees.permit_fee_rs)}</td>
              </tr>
              <tr>
                <td className="py-2.5 text-gray-600">Development Charges</td>
                <td className="py-2.5 text-right text-gray-800">{fmt(result.government_fees.development_charges_rs)}</td>
              </tr>
              <tr className="border-t-2 border-gray-300">
                <td className="py-3 font-bold text-gray-800">Total Government Fee</td>
                <td className="py-3 text-right font-bold text-blue-700 text-base">{fmt(result.government_fees.total_rs)}</td>
              </tr>
            </tbody>
          </table>

          {/* Agency benchmark */}
          <div className="bg-gray-50 rounded-lg p-4 space-y-1">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Agency Fee Benchmark</p>
            <p className="text-base font-bold text-gray-800">
              {fmt(result.agency_fee_benchmark.min_rs)} – {fmt(result.agency_fee_benchmark.max_rs)}
            </p>
            <p className="text-xs text-gray-500">{result.agency_fee_benchmark.note}</p>
          </div>

          <p className="text-xs text-gray-400">{result.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
