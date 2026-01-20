import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

export const api = {
    getSummary: () => axios.get(`${API_URL}/summary`).then(res => res.data),
    getPositions: () => axios.get(`${API_URL}/positions`).then(res => res.data),
    getHistory: async () => {
        const response = await axios.get(`${API_URL}/history`);
        return response.data;
    },
    getLogs: async () => {
        const response = await axios.get(`${API_URL}/logs`);
        return response.data;
    },
    getCandidates: async () => {
        const response = await axios.get(`${API_URL}/candidates`);
        return response.data;
    },
    sellPosition: async (symbol) => {
        const response = await axios.post(`${API_URL}/trade/sell/${symbol}`);
        return response.data;
    }
};
