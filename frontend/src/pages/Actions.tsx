import React, { useState, useEffect } from 'react'
import {
    Box,
    Paper,
    Typography,
    Button,
    Chip,
    IconButton,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    MenuItem,
    Alert,
} from '@mui/material'
import {
    DataGrid,
    GridColDef,
    GridActionsCellItem,
    GridRowParams,
    GridRowSelectionModel,
} from '@mui/x-data-grid'
import {
    Refresh as RefreshIcon,
    Cancel as CancelIcon,
    Visibility as ViewIcon,
    Add as AddIcon,
} from '@mui/icons-material'
import { dashboardAPI } from '../services/api'
import { format } from 'date-fns'
import ActionControls from '../components/ActionControls'

interface Action {
    action_id: string
    type: string
    target: string
    status: string
    created_at: string
    created_by: string
}

const Actions: React.FC = () => {
    const [actions, setActions] = useState<Action[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [selectedAction, setSelectedAction] = useState<Action | null>(null)
    const [detailsOpen, setDetailsOpen] = useState(false)
    const [statusFilter, setStatusFilter] = useState('')
    const [selectedActions, setSelectedActions] = useState<GridRowSelectionModel>([])

    const fetchActions = async () => {
        try {
            setLoading(true)
            const response = await dashboardAPI.getActions({
                status: statusFilter || undefined,
                limit: 100,
            })
            setActions(response.data)
            setError(null)
        } catch (err) {
            setError('Failed to fetch actions')
            console.error('Actions fetch error:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchActions()
    }, [statusFilter])

    const handleCancelAction = async (actionId: string) => {
        try {
            await dashboardAPI.cancelAction(actionId)
            fetchActions() // Refresh the list
        } catch (err) {
            console.error('Failed to cancel action:', err)
        }
    }

    const handleViewDetails = async (action: Action) => {
        try {
            const response = await dashboardAPI.getActionStatus(action.action_id)
            setSelectedAction(response.data)
            setDetailsOpen(true)
        } catch (err) {
            console.error('Failed to get action details:', err)
        }
    }

    const getStatusColor = (status: string) => {
        switch (status.toLowerCase()) {
            case 'completed': return 'success'
            case 'executing': return 'primary'
            case 'failed': return 'error'
            case 'cancelled': return 'default'
            case 'pending': return 'warning'
            default: return 'default'
        }
    }

    const columns: GridColDef[] = [
        {
            field: 'action_id',
            headerName: 'Action ID',
            width: 120,
            renderCell: (params) => (
                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                    {params.value.substring(0, 8)}...
                </Typography>
            ),
        },
        {
            field: 'type',
            headerName: 'Type',
            width: 150,
        },
        {
            field: 'target',
            headerName: 'Target',
            width: 200,
        },
        {
            field: 'status',
            headerName: 'Status',
            width: 120,
            renderCell: (params) => (
                <Chip
                    label={params.value}
                    color={getStatusColor(params.value) as any}
                    size="small"
                />
            ),
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
            field: 'created_by',
            headerName: 'Created By',
            width: 120,
        },
        {
            field: 'actions',
            type: 'actions',
            headerName: 'Actions',
            width: 120,
            getActions: (params: GridRowParams) => [
                <GridActionsCellItem
                    icon={<ViewIcon />}
                    label="View Details"
                    onClick={() => handleViewDetails(params.row)}
                />,
                <GridActionsCellItem
                    icon={<CancelIcon />}
                    label="Cancel"
                    onClick={() => handleCancelAction(params.row.action_id)}
                    disabled={!['pending', 'executing'].includes(params.row.status)}
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

            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" component="h1">
                    Network Actions
                </Typography>
                <Box sx={{ display: 'flex', gap: 2 }}>
                    <TextField
                        select
                        size="small"
                        label="Status Filter"
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                        sx={{ minWidth: 120 }}
                    >
                        <MenuItem value="">All</MenuItem>
                        <MenuItem value="pending">Pending</MenuItem>
                        <MenuItem value="executing">Executing</MenuItem>
                        <MenuItem value="completed">Completed</MenuItem>
                        <MenuItem value="failed">Failed</MenuItem>
                        <MenuItem value="cancelled">Cancelled</MenuItem>
                    </TextField>
                    <IconButton onClick={fetchActions} disabled={loading}>
                        <RefreshIcon />
                    </IconButton>
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={() => {/* TODO: Implement add action */ }}
                    >
                        New Action
                    </Button>
                </Box>
            </Box>

            {/* Action Controls */}
            <Box sx={{ mb: 2 }}>
                <ActionControls
                    selectedActions={selectedActions as string[]}
                    onActionsUpdated={fetchActions}
                />
            </Box>

            {/* Actions Table */}
            <Paper sx={{ height: 600, width: '100%' }}>
                <DataGrid
                    rows={actions}
                    columns={columns}
                    getRowId={(row) => row.action_id}
                    loading={loading}
                    pageSizeOptions={[25, 50, 100]}
                    initialState={{
                        pagination: {
                            paginationModel: { page: 0, pageSize: 25 },
                        },
                    }}
                    checkboxSelection
                    onRowSelectionModelChange={setSelectedActions}
                    rowSelectionModel={selectedActions}
                    disableRowSelectionOnClick
                />
            </Paper>

            {/* Action Details Dialog */}
            <Dialog
                open={detailsOpen}
                onClose={() => setDetailsOpen(false)}
                maxWidth="md"
                fullWidth
            >
                <DialogTitle>
                    Action Details
                </DialogTitle>
                <DialogContent>
                    {selectedAction && (
                        <Box sx={{ mt: 1 }}>
                            <Typography variant="subtitle2" gutterBottom>
                                Action ID: {selectedAction.action_id}
                            </Typography>
                            <Typography variant="body2" paragraph>
                                Type: {selectedAction.type}
                            </Typography>
                            <Typography variant="body2" paragraph>
                                Target: {selectedAction.target}
                            </Typography>
                            <Typography variant="body2" paragraph>
                                Status: <Chip label={selectedAction.status} color={getStatusColor(selectedAction.status) as any} size="small" />
                            </Typography>
                            <Typography variant="body2" paragraph>
                                Created: {format(new Date(selectedAction.created_at), 'PPpp')}
                            </Typography>
                            <Typography variant="body2" paragraph>
                                Created By: {selectedAction.created_by}
                            </Typography>
                            {/* Add more details as needed */}
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setDetailsOpen(false)}>
                        Close
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    )
}

export default Actions