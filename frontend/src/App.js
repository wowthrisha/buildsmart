import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import DisclaimerBanner from './components/DisclaimerBanner';
import JurisdictionWizard from './components/JurisdictionWizard';
import ComplianceChecker from './components/ComplianceChecker';
import FeeCalculator from './components/FeeCalculator';

function Navbar() {
  return (
    <nav className="bg-gray-900 text-white px-6 py-3 flex items-center gap-6">
      <span className="font-bold text-lg text-blue-400">BuildIQ</span>
      <Link to="/" className="hover:text-blue-300 text-sm">Jurisdiction</Link>
      <Link to="/compliance" className="hover:text-blue-300 text-sm">Compliance Check</Link>
      <Link to="/fees" className="hover:text-blue-300 text-sm">Fee Estimate</Link>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <DisclaimerBanner />
      <Navbar />
      <div className="min-h-screen bg-gray-50 p-6">
        <Routes>
          <Route path="/" element={<JurisdictionWizard />} />
          <Route path="/compliance" element={<ComplianceChecker />} />
          <Route path="/fees" element={<FeeCalculator />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
