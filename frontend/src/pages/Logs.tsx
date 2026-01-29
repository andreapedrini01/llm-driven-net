import React, { useState, useEffect } from 'react'
import {
    Box,
    Paper,
    Typography,
    TextField,
    MenuItem,
    IconButton,
    Alert,
    Chip,
} from '@mui/material'
import {
    Refresh as RefreshIcon,
} from '@mui/icons-material'
import { DataGrid, GridColDef } from '@mui/x-data-grid'
import { dashboardAPI } from '../services/api'
import { format } from 'date-fns'

interface LogEntry {
    timestamp: string
    level: string
    component: string
    message: string
    action_id?: string
    user_id?: string
}

const Logs: React.FC = () => {
    const [logs, setLogs] = useState<LogEntry[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [levelFilter, setLevelFilter] = useState('')
    const [componentFilter, setComponentFilter] = useState('')

    const fetchLogs = async () => {
        try {
            setLoading(true)
            const response = await dashboardAPI.getLogs({
                level: levelFilter || undefined,
                component: componentFilter || undefined,
                limit: 100,
            })
            setLogs(response.data)
            setError(null)
        } catch (err) {
            setError('Failed to fetch logs')
            console.error('Logs fetch error:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchLogs()
    }, [levelFilter, componentFilter])

    const getLevelColor = (level: string) => {
        switch (level.toLowerCase()) {
            case 'error': return 'error'
            case 'warning': return 'warning'
            case 'info': return 'info'
            case 'debug': return 'default'
            default: return 'default'
        }
    }

    const columns: GridColDef[] = [
        {
            field: 'timestamp',
            headerName: 'Timestamp',
            width: 180,
            renderCell: (params) => (
                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                    {format(new Date(params.value), 'MMM dd, HH:mm:ss.SSS')}
                </Typography>
            ),
        },
        {
            field: 'level',
            headerName: 'Level',
            width: 100,
            renderCell: (params) => (
                <Chip
                    label={params.value}
                    color={getLevelColor(params.value) as any}
                    size="small"
                />
            ),
        },
        {
            field: 'component',
            headerName: 'Component',
            width: 150,
        },
        {
            field: 'message',
            headerName: 'Message',
            flex: 1,
            minWidth: 300,
        },
        {
            field: 'action_id',
            headerName: 'Action ID',
            width: 120,
            renderCell: (params) => (
                params.value ? (
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {params.value.substring(0, 8)}...
                    </Typography>
                ) : null
            ),
        },
    ]

    return (
        <Box sx={{ height: '100%', width: '100%' }}>
            {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                    {error}
                </Alert>
            )}

            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" component="h1">
                    System Logs
                </Typography>
                <Box sx={{ display: 'flex', gap: 2 }}>
                    <TextField
                        select
                        size="small"
                        label="Level"
                        value={levelFilter}
                        onChange={(e) => setLevelFilter(e.target.value)}
                        sx={{ minWidth: 120 }}
                    >
                        <MenuItem value="">All</MenuItem>
                        <MenuItem value="error">Error</MenuItem>
                        <MenuItem value="warning">Warning</MenuItem>
                        <MenuItem value="info">Info</MenuItem>
                        <MenuItem value="debug">Debug</MenuItem>
                    </TextField>
                    <TextField
                        select
                        size="small"
                        label="Component"
                        value={componentFilter}
                        onChange={(e) => setComponentFilter(e.target.value)}
                        sx={{ minWidth: 150 }}
                    >
                        <MenuItem value="">All</MenuItem>
                        <MenuItem value="api_gateway">API Gateway</MenuItem>
                        <MenuItem value="northbound">Northbound</MenuItem>
                        <MenuItem value="monitoring">Monitoring</MenuItem>
                    </TextField>
                    <IconButton onClick={fetchLogs} disabled={loading}>
                        <RefreshIcon />
                    </IconButton>
                </Box>
            </Box>

            <Paper sx={{ height: 600, width: '100%' }}>
                <DataGrid
                    rows={logs}
                    columns={columns}
                    getRowId={(row, index) => index}
                    loading={loading}
                    pageSizeOptions={[25, 50, 100]}
                    initialState={{
                        pagination: {
                            paginationModel: { page: 0, pageSize: 25 },
                        },
                    }}
                    disableRowSelectionOnClick
                />
            </Paper>
        </Box>
    )
}

export default Logs