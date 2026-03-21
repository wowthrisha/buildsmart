import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { checkJurisdiction } from '../api';

const STEPS = 4;

export default function JurisdictionWizard() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    in_city_limits: null,
    plot_area_acres: '',
    floors: '1',
    building_type: 'Residential',
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const set = (key, val) => setForm((f) => ({ ...f, [key]: val }));

  const handleSubmit = async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await checkJurisdiction({
        in_city_limits: form.in_city_limits,
        plot_area_acres: parseFloat(form.plot_area_acres),
        floors: parseInt(form.floors),
        building_type: form.building_type,
      });
      setResult(data);
    } catch (e) {
      setError('Could not reach the server. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-800">Jurisdiction Check</h1>
        <p className="text-sm text-gray-500 mt-1">
          Find out which authority handles your building permit — Step {step} of {STEPS}
        </p>
        {/* Progress bar */}
        <div className="mt-3 h-1.5 bg-gray-200 rounded-full">
          <div
            className="h-1.5 bg-blue-500 rounded-full transition-all"
            style={{ width: `${(step / STEPS) * 100}%` }}
          />
        </div>
      </div>

      {!result && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">

          {/* Q1 */}
          {step === 1 && (
            <div>
              <p className="text-base font-medium text-gray-700 mb-4">
                Is your plot within Coimbatore city limits?
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => { set('in_city_limits', true); setStep(2); }}
                  className="flex-1 py-3 rounded-lg border-2 border-blue-400 bg-blue-50 text-blue-700 font-semibold hover:bg-blue-100 transition"
                >
                  Yes
                </button>
                <button
                  onClick={() => { set('in_city_limits', false); setStep(2); }}
                  className="flex-1 py-3 rounded-lg border-2 border-gray-300 text-gray-600 font-semibold hover:bg-gray-50 transition"
                >
                  No
                </button>
              </div>
            </div>
          )}

          {/* Q2 */}
          {step === 2 && (
            <div>
              <label className="block text-base font-medium text-gray-700 mb-2">
                What is your total plot area in acres?
              </label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.plot_area_acres}
                onChange={(e) => set('plot_area_acres', e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-400"
                placeholder="e.g. 0.25"
              />
              <div className="flex gap-3 mt-4">
                <button onClick={() => setStep(1)} className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700">← Back</button>
                <button
                  onClick={() => setStep(3)}
                  disabled={!form.plot_area_acres}
                  className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-40 transition"
                >
                  Next →
                </button>
              </div>
            </div>
          )}

          {/* Q3 */}
          {step === 3 && (
            <div>
              <label className="block text-base font-medium text-gray-700 mb-2">
                How many floors are you planning?
              </label>
              <select
                value={form.floors}
                onChange={(e) => set('floors', e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
              <div className="flex gap-3 mt-4">
                <button onClick={() => setStep(2)} className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700">← Back</button>
                <button
                  onClick={() => setStep(4)}
                  className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition"
                >
                  Next →
                </button>
              </div>
            </div>
          )}

          {/* Q4 */}
          {step === 4 && (
            <div>
              <label className="block text-base font-medium text-gray-700 mb-2">
                Building type?
              </label>
              <select
                value={form.building_type}
                onChange={(e) => set('building_type', e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-400"
              >
                <option value="Residential">Residential</option>
                <option value="Commercial">Commercial</option>
              </select>
              {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
              <div className="flex gap-3 mt-4">
                <button onClick={() => setStep(3)} className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700">← Back</button>
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-40 transition"
                >
                  {loading ? 'Checking…' : 'Check Jurisdiction'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="bg-white rounded-xl shadow-sm border border-green-300 p-6 space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-2xl">✅</span>
            <h2 className="text-lg font-bold text-gray-800">
              Your plot falls under{' '}
              <span className="text-blue-600">{result.authority}</span> jurisdiction
            </h2>
          </div>
          <div className="bg-blue-50 rounded-lg p-4 space-y-2 text-sm text-gray-700">
            <p><span className="font-semibold">Authority:</span> {result.authority}</p>
            <p><span className="font-semibold">Note:</span> {result.note}</p>
            <p><span className="font-semibold">Helpline:</span> {result.helpline}</p>
            <p><span className="font-semibold">Typical approval time:</span> {result.approval_time}</p>
          </div>
          <div className="flex gap-3 pt-2">
            <button
              onClick={() => { setResult(null); setStep(1); }}
              className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50"
            >
              Start over
            </button>
            <button
              onClick={() => navigate('/compliance')}
              className="flex-1 py-2.5 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition"
            >
              Check Compliance →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
