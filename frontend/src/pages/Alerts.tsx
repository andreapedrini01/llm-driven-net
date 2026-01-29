import React, { useState, useEffect } from 'react'
import {
    Box,
    Paper,
    Typography,
    Button,
    Chip,
    IconButton,
    Alert,
    TextField,
    MenuItem,
} from '@mui/material'
import {
    DataGrid,
    GridColDef,
    GridActionsCellItem,
    GridRowParams,
} from '@mui/x-data-grid'
import {
    Refresh as RefreshIcon,
    Check as AckIcon,
} from '@mui/icons-material'
import { dashboardAPI } from '../services/api'
import { format } from 'date-fns'

interface AlertInfo {
    alert_id: string
    severity: string
    title: string
    message: string
    created_at: string
    acknowledged: boolean
    acknowledged_by?: string
}

const Alerts: React.FC = () => {
    const [alerts, setAlerts] = useState<AlertInfo[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [severityFilter, setSeverityFilter] = useState('')
    const [acknowledgedFilter, setAcknowledgedFilter] = useState('')

    const fetchAlerts = async () => {
        try {
            setLoading(true)
            const response = await dashboardAPI.getAlerts({
                severity: severityFilter || undefined,
                acknowledged: acknowledgedFilter !== '' ? acknowledgedFilter === 'true' : undefined,
            })
            setAlerts(response.data)
            setError(null)
        } catch (err) {
            setError('Failed to fetch alerts')
            console.error('Alerts fetch error:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchAlerts()
    }, [severityFilter, acknowledgedFilter])

    const handleAcknowledgeAlert = async (alertId: string) => {
        try {
            await dashboardAPI.acknowledgeAlert(alertId)
            fetchAlerts() // Refresh the list
        } catch (err) {
            console.error('Failed to acknowledge alert:', err)
        }
    }

    const getSeverityColor = (severity: string) => {
        switch (severity.toLowerCase()) {
            case 'critical': return 'error'
            case 'warning': return 'warning'
            case 'info': return 'info'
            default: return 'default'
        }
    }

    const columns: GridColDef[] = [
        {
            field: 'severity',
            headerName: 'Severity',
            width: 120,
            renderCell: (params) => (
                <Chip
                    label={params.value}
                    color={getSeverityColor(params.value) as any}
                    size="small"
                />
            ),
        },
        {
            field: 'title',
            headerName: 'Title',
            width: 200,
        },
        {
            field: 'message',
            headerName: 'Message',
            flex: 1,
            minWidth: 300,
        },
        {
            field: 'created_at',
            headerName: 'Created',
            width: 180,
            renderCell: (params) => (
                <Typography variant="body2">
                    {format(new Date(params.value), 'MMM dd, HH:mm:ss')}
                </Typography>
            ),
        },
        {
            field: 'acknowledged',
            headerName: 'Status',
            width: 120,
            renderCell: (params) => (
                <Chip
                    label={params.value ? 'Acknowledged' : 'Active'}
                    color={params.value ? 'success' : 'warning'}
                    size="small"
                />
            ),
        },
        {
            field: 'actions',
            type: 'actions',
            headerName: 'Actions',
            width: 100,
            getActions: (params: GridRowParams) => [
                <GridActionsCellItem
                    icon={<AckIcon />}
                    label="Acknowledge"
                    onClick={() => handleAcknowledgeAlert(params.row.alert_id)}
                    disabled={params.row.acknowledged}
                />,
            ],
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
                    System Alerts
                </Typography>
                <Box sx={{ display: 'flex', gap: 2 }}>
                    <TextField
                        select
                        size="small"
                        label="Severity"
                        value={severityFilter}
                        onChange={(e) => setSeverityFilter(e.target.value)}
                        sx={{ minWidth: 120 }}
                    >
                        <MenuItem value="">All</MenuItem>
                        <MenuItem value="critical">Critical</MenuItem>
                        <MenuItem value="warning">Warning</MenuItem>
                        <MenuItem value="info">Info</MenuItem>
                    </TextField>
                    <TextField
                        select
                        size="small"
                        label="Status"
                        value={acknowledgedFilter}
                        onChange={(e) => setAcknowledgedFilter(e.target.value)}
                        sx={{ minWidth: 120 }}
                    >
                        <MenuItem value="">All</MenuItem>
                        <MenuItem value="false">Active</MenuItem>
                        <MenuItem value="true">Acknowledged</MenuItem>
                    </TextField>
                    <IconButton onClick={fetchAlerts} disabled={loading}>
                        <RefreshIcon />
                    </IconButton>
                </Box>
            </Box>

            <Paper sx={{ height: 600, width: '100%' }}>
                <DataGrid
                    rows={alerts}
                    columns={columns}
                    getRowId={(row) => row.alert_id}
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

export default Alerts