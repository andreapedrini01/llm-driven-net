import React, { useState, useEffect } from 'react'
import {
    Snackbar,
    Alert,
    AlertTitle,
    Button,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Typography,
    Box,
    Chip,
    IconButton,
    Collapse,
} from '@mui/material'
import {
    Error as ErrorIcon,
    Warning as WarningIcon,
    Info as InfoIcon,
    Close as CloseIcon,
    ExpandMore as ExpandMoreIcon,
    ExpandLess as ExpandLessIcon,
} from '@mui/icons-material'
import { useWebSocket } from '../contexts/WebSocketContext'
import { format } from 'date-fns'

interface CriticalError {
    type: string
    severity: 'critical' | 'warning' | 'info'
    title: string
    message: string
    component?: string
    timestamp: string
    reported_by?: string
    details?: any
}

const CriticalErrorNotification: React.FC = () => {
    const [errors, setErrors] = useState<CriticalError[]>([])
    const [currentError, setCurrentError] = useState<CriticalError | null>(null)
    const [snackbarOpen, setSnackbarOpen] = useState(false)
    const [dialogOpen, setDialogOpen] = useState(false)
    const [detailsExpanded, setDetailsExpanded] = useState(false)
    const { lastMessage } = useWebSocket()

    useEffect(() => {
        if (lastMessage) {
            if (lastMessage.type === 'critical_error' ||
                lastMessage.type === 'system_alert' ||
                lastMessage.type === 'emergency_stop') {

                const error: CriticalError = {
                    type: lastMessage.type,
                    severity: lastMessage.severity || 'critical',
                    title: lastMessage.title || lastMessage.alert?.title || 'System Alert',
                    message: lastMessage.message || lastMessage.alert?.message || 'A system event occurred',
                    component: lastMessage.component || lastMessage.alert?.component,
                    timestamp: lastMessage.timestamp,
                    reported_by: lastMessage.reported_by || lastMessage.initiated_by,
                    details: lastMessage
                }

                setErrors(prev => [error, ...prev.slice(0, 9)]) // Keep last 10 errors
                setCurrentError(error)
                setSnackbarOpen(true)

                // Auto-open dialog for critical errors
                if (error.severity === 'critical' || lastMessage.type === 'emergency_stop') {
                    setDialogOpen(true)
                }
            }
        }
    }, [lastMessage])

    const handleSnackbarClose = () => {
        setSnackbarOpen(false)
    }

    const handleDialogClose = () => {
        setDialogOpen(false)
        setDetailsExpanded(false)
    }

    const handleViewDetails = () => {
        setDialogOpen(true)
        setSnackbarOpen(false)
    }

    const getSeverityIcon = (severity: string) => {
        switch (severity) {
            case 'critical': return <ErrorIcon />
            case 'warning': return <WarningIcon />
            case 'info': return <InfoIcon />
            default: return <ErrorIcon />
        }
    }

    const getSeverityColor = (severity: string) => {
        switch (severity) {
            case 'critical': return 'error'
            case 'warning': return 'warning'
            case 'info': return 'info'
            default: return 'error'
        }
    }

    const getTypeLabel = (type: string) => {
        switch (type) {
            case 'critical_error': return 'Critical Error'
            case 'system_alert': return 'System Alert'
            case 'emergency_stop': return 'Emergency Stop'
            default: return 'System Event'
        }
    }

    return (
        <>
            {/* Snackbar Notification */}
            <Snackbar
                open={snackbarOpen}
                autoHideDuration={currentError?.severity === 'critical' ? null : 6000}
                onClose={handleSnackbarClose}
                anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
            >
                <Alert
                    severity={getSeverityColor(currentError?.severity || 'error') as any}
                    action={
                        <Box sx={{ display: 'flex', gap: 1 }}>
                            <Button
                                color="inherit"
                                size="small"
                                onClick={handleViewDetails}
                            >
                                Details
                            </Button>
                            <IconButton
                                size="small"
                                color="inherit"
                                onClick={handleSnackbarClose}
                            >
                                <CloseIcon fontSize="small" />
                            </IconButton>
                        </Box>
                    }
                >
                    <AlertTitle>{currentError?.title}</AlertTitle>
                    {currentError?.message}
                </Alert>
            </Snackbar>

            {/* Detailed Error Dialog */}
            <Dialog
                open={dialogOpen}
                onClose={handleDialogClose}
                maxWidth="md"
                fullWidth
            >
                <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {currentError && getSeverityIcon(currentError.severity)}
                    {currentError?.title}
                </DialogTitle>
                <DialogContent>
                    {currentError && (
                        <Box>
                            <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                                <Chip
                                    label={getTypeLabel(currentError.type)}
                                    color={getSeverityColor(currentError.severity) as any}
                                    size="small"
                                />
                                <Chip
                                    label={currentError.severity.toUpperCase()}
                                    color={getSeverityColor(currentError.severity) as any}
                                    variant="outlined"
                                    size="small"
                                />
                                {currentError.component && (
                                    <Chip
                                        label={`Component: ${currentError.component}`}
                                        variant="outlined"
                                        size="small"
                                    />
                                )}
                            </Box>

                            <Typography variant="body1" paragraph>
                                {currentError.message}
                            </Typography>

                            <Box sx={{ mb: 2 }}>
                                <Typography variant="body2" color="text.secondary">
                                    <strong>Time:</strong> {format(new Date(currentError.timestamp), 'PPpp')}
                                </Typography>
                                {currentError.reported_by && (
                                    <Typography variant="body2" color="text.secondary">
                                        <strong>Reported by:</strong> {currentError.reported_by}
                                    </Typography>
                                )}
                            </Box>

                            {/* Emergency Stop Specific Information */}
                            {currentError.type === 'emergency_stop' && (
                                <Alert severity="error" sx={{ mb: 2 }}>
                                    <AlertTitle>Emergency Stop Activated</AlertTitle>
                                    <Typography>
                                        All system actions have been stopped.
                                        {currentError.details?.stopped_count &&
                                            ` ${currentError.details.stopped_count} actions were cancelled.`
                                        }
                                    </Typography>
                                </Alert>
                            )}

                            {/* Expandable Details */}
                            {currentError.details && (
                                <Box>
                                    <Button
                                        onClick={() => setDetailsExpanded(!detailsExpanded)}
                                        startIcon={detailsExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                                        size="small"
                                    >
                                        Technical Details
                                    </Button>
                                    <Collapse in={detailsExpanded}>
                                        <Box sx={{ mt: 1, p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
                                            <Typography variant="body2" component="pre" sx={{
                                                fontFamily: 'monospace',
                                                fontSize: '0.75rem',
                                                whiteSpace: 'pre-wrap',
                                                wordBreak: 'break-word'
                                            }}>
                                                {JSON.stringify(currentError.details, null, 2)}
                                            </Typography>
                                        </Box>
                                    </Collapse>
                                </Box>
                            )}

                            {/* Recent Errors History */}
                            {errors.length > 1 && (
                                <Box sx={{ mt: 3 }}>
                                    <Typography variant="h6" gutterBottom>
                                        Recent Events ({errors.length - 1} more)
                                    </Typography>
                                    <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
                                        {errors.slice(1, 6).map((error, index) => (
                                            <Box key={index} sx={{ mb: 1, p: 1, bgcolor: 'grey.50', borderRadius: 1 }}>
                                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                                                    <Chip
                                                        label={error.severity}
                                                        color={getSeverityColor(error.severity) as any}
                                                        size="small"
                                                    />
                                                    <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                                                        {error.title}
                                                    </Typography>
                                                </Box>
                                                <Typography variant="caption" color="text.secondary">
                                                    {format(new Date(error.timestamp), 'MMM dd, HH:mm:ss')}
                                                </Typography>
                                            </Box>
                                        ))}
                                    </Box>
                                </Box>
                            )}
                        </Box>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleDialogClose}>
                        Close
                    </Button>
                    {currentError?.severity === 'critical' && (
                        <Button
                            variant="contained"
                            color="primary"
                            onClick={() => {
                                // TODO: Implement acknowledge or escalate action
                                handleDialogClose()
                            }}
                        >
                            Acknowledge
                        </Button>
                    )}
                </DialogActions>
            </Dialog>
        </>
    )
}

export default CriticalErrorNotification