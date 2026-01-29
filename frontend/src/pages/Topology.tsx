import React, { useState, useEffect } from 'react'
import {
    Box,
    Paper,
    Typography,
    IconButton,
    Alert,
    Card,
    CardContent,
    Grid,
} from '@mui/material'
import {
    Refresh as RefreshIcon,
} from '@mui/icons-material'
import { dashboardAPI } from '../services/api'

interface NetworkTopology {
    switches: any[]
    links: any[]
    hosts: any[]
    flows: any[]
    last_updated: string
}

const Topology: React.FC = () => {
    const [topology, setTopology] = useState<NetworkTopology | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const fetchTopology = async () => {
        try {
            setLoading(true)
            const response = await dashboardAPI.getNetworkTopology()
            setTopology(response.data)
            setError(null)
        } catch (err) {
            setError('Failed to fetch network topology')
            console.error('Topology fetch error:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchTopology()
    }, [])

    return (
        <Box sx={{ flexGrow: 1 }}>
            {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                    {error}
                </Alert>
            )}

            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h4" component="h1">
                    Network Topology
                </Typography>
                <IconButton onClick={fetchTopology} disabled={loading}>
                    <RefreshIcon />
                </IconButton>
            </Box>

            <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                Switches
                            </Typography>
                            <Typography variant="h4">
                                {topology?.switches.length || 0}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12} md={6}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                Hosts
                            </Typography>
                            <Typography variant="h4">
                                {topology?.hosts.length || 0}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid item xs={12}>
                    <Paper sx={{ p: 2, height: 400 }}>
                        <Typography variant="h6" gutterBottom>
                            Network Visualization
                        </Typography>
                        <Box sx={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            height: '100%',
                            color: 'text.secondary'
                        }}>
                            Network topology visualization would be implemented here using D3.js or similar
                        </Box>
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    )
}

export default Topology