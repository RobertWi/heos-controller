import axios from 'axios';

// Use relative path since we're using Vite's proxy
const API_BASE_URL = '/api';

// Configure axios defaults
axios.defaults.headers.common['Content-Type'] = 'application/json';

export interface DeviceInfo {
  name: string;
  model: string;
  version?: string;
  serial?: string;
  network?: string;
  pid?: number;
}

export interface Device {
  ip: string;
  info: DeviceInfo;
  status: 'ready' | 'error' | 'initializing';
  error?: string;
}

export interface DiscoverResponse {
  devices: Device[];
}

export interface HeosResponse {
  success: boolean;
  message?: string;
  error?: string;
}

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const heosApi = {
  async discover(): Promise<DiscoverResponse> {
    const response = await api.get<DiscoverResponse>('/discover');
    console.log('API Response:', response.data);
    return response.data;
  },

  async sendCommand(ip: string, command: string, parameters?: Record<string, any>): Promise<HeosResponse> {
    const response = await api.post<HeosResponse>(`/player/${ip}/command`, {
      command,
      parameters,
    });
    return response.data;
  },

  async playPreset(ip: string, presetNumber: number): Promise<HeosResponse> {
    const response = await api.post<HeosResponse>(`/player/${ip}/preset/${presetNumber}`);
    return response.data;
  },
};
