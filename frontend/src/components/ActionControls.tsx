import React, { useState } from 'react'
import {
    Box,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    Typography,
    Alert,
    Chip,
    List,
    ListItem,
    ListItemText,
    Checkbox,
    FormControlLabel,
    Slider,
} from '@mui/material'
import {
    Cancel as CancelIcon,
    Warning as WarningIcon,
    PriorityHigh as PriorityIcon,
    Stop as EmergencyStopIcon,
} from '@mui/icons-material'
import { apiClient } from '../services/api'

interface ActionControlsProps {
    selectedActions: string[]
    onActionsUpdated: () => void
}

const ActionControls: React.FC<ActionControlsProps> = ({
    selectedActions,
    onActionsUpdated,
}) => {
    const [bulkCancelOpen, setBulkCancelOpen] = useState(false)
    const [priorityDialogOpen, setPriorityDialogOpen] = useState(false)
    const [emergencyStopOpen, setEmergencyStopOpen] = useState(false)
    const [newPriority, setNewPriority] = useState(5)
    const [confirmEmergencyStop, setConfirmEmergencyStop] = useState(false)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const handleBulkCancel = async () => {
        try {
            setLoading(true)
            setError(null)

            const response = await apiClient.post('/dashboard/actions/bulk-cancel', selectedActions)

            setBulkCancelOpen(false)
            onActionsUpdated()

            // Show success message with details
            console.log('Bulk cancel result:', response.data)
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to cancel actions')
        } finally {
            setLoading(false)
        }
    }

    const handleUpdatePriority = async () => {
        try {
            setLoading(true)
            setError(null)

            // Update priority for each selected action
            const promises = selectedActions.map(actionId =>
                apiClient.post(`/dashboard/actions/${actionId}/priority`, { priority: newPriority })
            )

            await Promise.all(promises)

            setPriorityDialogOpen(false)
            onActionsUpdated()
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to update priority')
        } finally {
            setLoading(false)
        }
    }

    const handleEmergencyStop = async () => {
        if (!confirmEmergencyStop) {
            setError('Please confirm emergency stop by checking the checkbox')
            return
        }

        try {
            setLoading(true)
            setError(null)

            const response = await apiClient.post('/dashboard/system/emergency-stop')

            setEmergencyStopOpen(false)
            setConfirmEmergencyStop(false)
            onActionsUpdated()

            console.log('Emergency stop result:', response.data)
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to execute emergency stop')
        } finally {
            setLoading(false)
        }
    }

    const getPriorityLabel = (value: number) => {
        if (value <= 2) return 'Low'
        if (value <= 4) return 'Normal'
        if (value <= 7) return 'High'
        return 'Critical'
    }

    const getPriorityColor = (value: number) => {
        if (value <= 2) return 'info'
        if (value <= 4) return 'success'
        if (value <= 7) return 'warning'
        return 'error'
    }

    return (
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {error && (
                <Alert severity="error" sx={{ width: '100%', mb: 2 }}>
                    {error}
                </Alert>
            )}

            <Button
                variant="outlined"
                color="warning"
                startIcon={<CancelIcon />}
                onClick={() => setBulkCancelOpen(true)}
                disabled={selectedActions.length === 0}
            >
                Cancel Selected ({selectedActions.length})
            </Button>

            <Button
                variant="outlined"
                startIcon={<PriorityIcon />}
                onClick={() => setPriorityDialogOpen(true)}
                disabled={selectedActions.length === 0}
            >
                Set Priority
            </Button>

            <Button
                variant="outlined"
                color="error"
                startIcon={<EmergencyStopIcon />}
                onClick={() => setEmergencyStopOpen(true)}
            >
                Emergency Stop
            </Button>

            {/* Bulk Cancel Dialog */}
            <Dialog
                open={bulkCancelOpen}
                onClose={() => setBulkCancelOpen(false)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <WarningIcon color="warning" />
                    Confirm Bulk Cancellation
                </DialogTitle>
                <DialogContent>
                    <Typography paragraph>
                        Are you sure you want to cancel {selectedActions.length} selected actions?
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        This action cannot be undone. Only pending and executing actions will be cancelled.
                    </Typography>

                    {selectedActions.length > 0 && (
                        <Box sx={{ mt: 2 }}>
                            <Typography variant="subtitle2" gutterBottom>
                                Selected Actions:
                            </Typography>
                            <List dense>
                                {selectedActions.slice(0, 5).map((actionId) => (
                                    <ListItem key={actionId} sx={{ py: 0 }}>
                                        <ListItemText
                                            primary={
                                                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                                                    {actionId.substring(0, 8)}...
                                                </Typography>
                                            }
                                        />
                                    </ListItem>
                                ))}
                                {selectedActions.length > 5 && (
                                    <ListItem sx={{ py: 0 }}>
                                        <ListItemText
                                            primary={
                                                <Typography variant="body2" color="text.secondary">
                                                    ... and {selectedActions.length - 5} more
                                                </Typography>
                                            }
                                        />
                                    </ListItem>
                                )}
                            </List>
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setBulkCancelOpen(false)}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleBulkCancel}
                        variant="contained"
                        color="warning"
                        disabled={loading}
                    >
                        {loading ? 'Cancelling...' : 'Confirm Cancellation'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Priority Update Dialog */}
            <Dialog
                open={priorityDialogOpen}
                onClose={() => setPriorityDialogOpen(false)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle>
                    Update Action Priority
                </DialogTitle>
                <DialogContent>
                    <Typography paragraph>
                        Set new priority for {selectedActions.length} selected actions:
                    </Typography>

                    <Box sx={{ mt: 3, mb: 2 }}>
                        <Typography gutterBottom>
                            Priority Level: {newPriority} - {getPriorityLabel(newPriority)}
                        </Typography>
                        <Slider
                            value={newPriority}
                            onChange={(_, value) => setNewPriority(value as number)}
                            min={1}
                            max={10}
                            step={1}
                            marks={[
                                { value: 1, label: 'Low' },
                                { value: 3, label: 'Normal' },
                                { value: 6, label: 'High' },
                                { value: 10, label: 'Critical' },
                            ]}
                            valueLabelDisplay="auto"
                        />
                    </Box>

                    <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
                        <Chip
                            label={`Priority ${newPriority} - ${getPriorityLabel(newPriority)}`}
                            color={getPriorityColor(newPriority) as any}
                        />
                    </Box>

                    <Typography variant="body2" color="text.secondary">
                        Higher priority actions will be processed first. Only pending actions can have their priority updated.
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setPriorityDialogOpen(false)}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleUpdatePriority}
                        variant="contained"
                        disabled={loading}
                    >
                        {loading ? 'Updating...' : 'Update Priority'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Emergency Stop Dialog */}
            <Dialog
                open={emergencyStopOpen}
                onClose={() => setEmergencyStopOpen(false)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <EmergencyStopIcon color="error" />
                    Emergency Stop System
                </DialogTitle>
                <DialogContent>
                    <Alert severity="error" sx={{ mb: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            WARNING: EMERGENCY STOP
                        </Typography>
                        <Typography>
                            This will immediately cancel ALL active and pending actions in the system.
                            Use only in emergency situations.
                        </Typography>
                    </Alert>

                    <Typography paragraph>
                        Emergency stop will:
                    </Typography>
                    <List dense>
                        <ListItem>
                            <ListItemText primary="• Cancel all pending actions" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="• Terminate all executing actions" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="• Prevent new actions from starting" />
                        </ListItem>
                        <ListItem>
                            <ListItemText primary="• Notify all connected users" />
                        </ListItem>
                    </List>

                    <FormControlLabel
                        control={
                            <Checkbox
                                checked={confirmEmergencyStop}
                                onChange={(e) => setConfirmEmergencyStop(e.target.checked)}
                                color="error"
                            />
                        }
                        label="I understand the consequences and want to proceed with emergency stop"
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setEmergencyStopOpen(false)}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleEmergencyStop}
                        variant="contained"
                        color="error"
                        disabled={loading || !confirmEmergencyStop}
                    >
                        {loading ? 'Stopping...' : 'EMERGENCY STOP'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    )
}

export default ActionControls