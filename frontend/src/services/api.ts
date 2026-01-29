import axios from 'axios'

export const apiClient = axios.create({
    baseURL: '/api/v1',
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
    },
})

// Request interceptor to add auth token
apiClient.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token')
        if (token) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    (error) => {
        return Promise.reject(error)
    }
)

// Response interceptor to handle auth errors
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('access_token')
            window.location.href = '/login'
        }
        return Promise.reject(error)
    }
)

// API service functions
export const dashboardAPI = {
    // System status
    getSystemStatus: () => apiClient.get('/dashboard/status'),

    // Network topology
    getNetworkTopology: () => apiClient.get('/dashboard/topology'),

    // Actions
    getActions: (params?: any) => apiClient.get('/actions', { params }),
    getActionStatus: (actionId: string) => apiClient.get(`/actions/${actionId}`),
    cancelAction: (actionId: string) => apiClient.delete(`/actions/${actionId}`),
    getActionsProgress: () => apiClient.get('/dashboard/actions/progress'),

    // Metrics
    getDashboardMetrics: () => apiClient.get('/dashboard/metrics'),

    // Logs
    getLogs: (params?: any) => apiClient.get('/dashboard/logs', { params }),

    // Alerts
    getAlerts: (params?: any) => apiClient.get('/dashboard/alerts', { params }),
    acknowledgeAlert: (alertId: string) => apiClient.post(`/dashboard/alerts/${alertId}/acknowledge`),

    // Health
    getHealth: () => apiClient.get('/health'),
}

export default apiClient