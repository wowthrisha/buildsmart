import axios from 'axios';
const BASE = 'http://localhost:8000';
export const checkJurisdiction = (data) => axios.post(`${BASE}/api/jurisdiction`, data);
export const checkCompliance = (data) => axios.post(`${BASE}/api/check-compliance`, data);
export const getFeeEstimate = (data) => axios.post(`${BASE}/api/fee-estimate`, data);
