import React, { useState, useEffect } from 'react'
import {
    Grid,
    Paper,
    Typography,
    Box,
    Card,
    CardContent,
    LinearProgress,
    Chip,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    IconButton,
    Alert,
} from '@mui/material'
import {
    Refresh as RefreshIcon,
    Computer as SystemIcon,
    PlayArrow as ActionIcon,
    Warning as AlertIcon,
    CheckCircle as SuccessIcon,
    Error as ErrorIcon,
} from '@mui/icons-material'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { dashboardAPI } from '../services/api'
import { useWebSocket } from '../contexts/WebSocketContext'

interface SystemStatus {
    status: string
    uptime_seconds: number
    total_actions: number
    active_actions: number
    error_rate: number
    cpu_usage: number
    memory_usage: number
    network_connections: number
    last_updated: string
}

interface DashboardMetrics {
    actions_per_minute: number
    average_response_time: number
    success_rate: number
    active_users: number
    queue_size: number
    alerts_count: number
    timestamp: string
}

interface ActionProgress {
    action_id: string
    status: string
    progress_percent: number
    estimated_completion?: string
    elapsed_time_seconds: number
    remaining_time_seconds?: number
    current_step: string
    total_steps: number
}

const Dashboard: React.FC = () => {
    const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
    const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
    const [actionProgress, setActionProgress] = useState<ActionProgress[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const { lastMessage } = useWebSocket()

    const fetchData = async () => {
        try {
            setLoading(true)
            const [statusRes, metricsRes, progressRes] = await Promise.all([
                dashboardAPI.getSystemStatus(),
                dashboardAPI.getDashboardMetrics(),
                dashboardAPI.getActionsProgress(),
            ])

            setSystemStatus(statusRes.data)
            setMetrics(metricsRes.data)
            setActionProgress(progressRes.data)
            setError(null)
        } catch (err) {
            setError('Failed to fetch dashboard data')
            console.error('Dashboard fetch error:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchData()
        const interval = setInterval(fetchData, 30000) // Refresh every 30 seconds
        return () => clearInterval(interval)
    }, [])

    // Handle real-time updates
    useEffect(() => {
        if (lastMessage) {
            if (lastMessage.type === 'metrics_update') {
                // Update metrics from WebSocket
                fetchData()
            } else if (lastMessage.type === 'action_update') {
                // Update specific action progress
                fetchData()
            }
        }
    }, [lastMessage])

    const formatUptime = (seconds: number) => {
        const days = Math.floor(seconds / 86400)
        const hours = Math.floor((seconds % 86400) / 3600)
        const minutes = Math.floor((seconds % 3600) / 60)
        return `${days}d ${hours}h ${minutes}m`
    }

    const getStatusColor = (status: string) => {
        switch (status.toLowerCase()) {
            case 'healthy': return 'success'
            case 'warning': return 'warning'
            case 'error': return 'error'
            default: return 'default'
        }
    }

    const getActionStatusColor = (status: string) => {
        switch (status.toLowerCase()) {
            case 'completed': return 'success'
            case 'executing': return 'primary'
            case 'failed': return 'error'
            case 'cancelled': return 'default'
            default: return 'warning'
        }
    }

    // Mock data for charts
    const performanceData = [
        { time: '00:00', cpu: 45, memory: 62, actions: 12 },
        { time: '04:00', cpu: 52, memory: 58, actions: 8 },
        { time: '08:00', cpu: 78, memory: 71, actions: 25 },
        { time: '12:00', cpu: 65, memory: 69, actions: 18 },
        { time: '16:00', cpu: 71, memory: 74, actions: 22 },
        { time: '20:00', cpu: 58, memory: 66, actions: 15 },
    ]

    const actionStatusData = [
        { name: 'Completed', value: 85, color: '#4caf50' },
        { name: 'Failed', value: 10, color: '#f44336' },
        { name: 'In Progress', value: 5, color: '#2196f3' },
    ]

    if (loading && !systemStatus) {
        return (
            <Box sx={{ width: '100%', mt: 2 }}>
                <LinearProgress />
                <Typography sx={{ mt: 2 }}>Loading dashboard...</Typography>
            </Box>
        )
    }

    return (
        <Box sx={{ flexGrow: 1 }}>
            {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                    {error}
                </Alert>
            )}

            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" component="h1">
                    System Dashboard
                </Typography>
                <IconButton onClick={fetchData} disabled={loading}>
                    <RefreshIcon />
                </IconButton>
            </Box>

            <Grid container spacing={3}>
                {/* System Status Cards */}
                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                <SystemIcon sx={{ mr: 1 }} />
                                <Typography variant="h6">System Status</Typography>
                            </Box>
                            <Chip
                                label={systemStatus?.status || 'Unknown'}
                                color={getStatusColor(systemStatus?.status || 'unknown') as any}
                                sx={{ mb: 1 }}
                            />
                            <Typography variant="body2" color="text.secondary">
                                Uptime: {systemStatus ? formatUptime(systemStatus.uptime_seconds) : 'N/A'}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                <ActionIcon sx={{ mr: 1 }} />
                                <Typography variant="h6">Actions</Typography>
                            </Box>
                            <Typography variant="h4">
                                {systemStatus?.total_actions || 0}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                                {systemStatus?.active_actions || 0} active
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                <SuccessIcon sx={{ mr: 1 }} />
                                <Typography variant="h6">Success Rate</Typography>
                            </Box>
                            <Typography variant="h4">
                                {metrics ? `${(100 - (systemStatus?.error_rate || 0)).toFixed(1)}%` : 'N/A'}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                                {metrics?.actions_per_minute || 0} actions/min
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                <AlertIcon sx={{ mr: 1 }} />
                                <Typography variant="h6">Alerts</Typography>
                            </Box>
                            <Typography variant="h4">
                                {metrics?.alerts_count || 0}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                                Active alerts
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                {/* Performance Chart */}
                <Grid item xs={12} md={8}>
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            System Performance
                        </Typography>
                        <ResponsiveContainer width="100%" height={300}>
                            <LineChart data={performanceData}>
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="time" />
                                <YAxis />
                                <Tooltip />
                                <Line type="monotone" dataKey="cpu" stroke="#8884d8" name="CPU %" />
                                <Line type="monotone" dataKey="memory" stroke="#82ca9d" name="Memory %" />
                                <Line type="monotone" dataKey="actions" stroke="#ffc658" name="Actions" />
                            </LineChart>
                        </ResponsiveContainer>
                    </Paper>
                </Grid>

                {/* Action Status Distribution */}
                <Grid item xs={12} md={4}>
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            Action Status Distribution
                        </Typography>
                        <ResponsiveContainer width="100%" height={300}>
                            <PieChart>
                                <Pie
                                    data={actionStatusData}
                                    cx="50%"
                                    cy="50%"
                                    outerRadius={80}
                                    fill="#8884d8"
                                    dataKey="value"
                                    label={({ name, value }) => `${name}: ${value}%`}
                                >
                                    {actionStatusData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Pie>
                                <Tooltip />
                            </PieChart>
                        </ResponsiveContainer>
                    </Paper>
                </Grid>

                {/* Active Actions Progress */}
                <Grid item xs={12}>
                    <Paper sx={{ p: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            Active Actions Progress
                        </Typography>
                        {actionProgress.length === 0 ? (
                            <Typography color="text.secondary">No active actions</Typography>
                        ) : (
                            <List>
                                {actionProgress.map((action) => (
                                    <ListItem key={action.action_id}>
                                        <ListItemIcon>
                                            {action.status === 'completed' ? (
                                                <SuccessIcon color="success" />
                                            ) : action.status === 'failed' ? (
                                                <ErrorIcon color="error" />
                                            ) : (
                                                <ActionIcon color="primary" />
                                            )}
                                        </ListItemIcon>
                                        <ListItemText
                                            primary={
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                                    <Typography variant="body1">
                                                        Action {action.action_id.substring(0, 8)}...
                                                    </Typography>
                                                    <Chip
                                                        label={action.status}
                                                        color={getActionStatusColor(action.status) as any}
                                                        size="small"
                                                    />
                                                </Box>
                                            }
                                            secondary={
                                                <Box sx={{ mt: 1 }}>
                                                    <Typography variant="body2" color="text.secondary">
                                                        {action.current_step} ({action.progress_percent.toFixed(1)}%)
                                                    </Typography>
                                                    <LinearProgress
                                                        variant="determinate"
                                                        value={action.progress_percent}
                                                        sx={{ mt: 1 }}
                                                    />
                                                    {action.remaining_time_seconds && (
                                                        <Typography variant="caption" color="text.secondary">
                                                            Est. {Math.ceil(action.remaining_time_seconds / 60)} minutes remaining
                                                        </Typography>
                                                    )}
                                                </Box>
                                            }
                                        />
                                    </ListItem>
                                ))}
                            </List>
                        )}
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    )
}

export default Dashboard