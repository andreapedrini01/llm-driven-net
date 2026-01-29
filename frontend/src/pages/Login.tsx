import React, { useState } from 'react'
import {
    Box,
    Card,
    CardContent,
    TextField,
    Button,
    Typography,
    Alert,
    CircularProgress,
    Container,
} from '@mui/material'
import { useAuth } from '../contexts/AuthContext'

const Login: React.FC = () => {
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [mfaToken, setMfaToken] = useState('')
    const [showMfa, setShowMfa] = useState(false)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    const { login } = useAuth()

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setLoading(true)
        setError('')

        try {
            const success = await login(username, password, mfaToken)
            if (!success) {
                setError('Invalid credentials')
                // Check if MFA is required (this would come from the API response)
                // setShowMfa(true)
            }
        } catch (err) {
            setError('Login failed. Please try again.')
        } finally {
            setLoading(false)
        }
    }

    return (
        <Container component="main" maxWidth="sm">
            <Box
                sx={{
                    marginTop: 8,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                }}
            >
                <Card sx={{ width: '100%', maxWidth: 400 }}>
                    <CardContent sx={{ p: 4 }}>
                        <Typography component="h1" variant="h4" align="center" gutterBottom>
                            Northbound Dashboard
                        </Typography>
                        <Typography variant="body2" align="center" color="text.secondary" sx={{ mb: 3 }}>
                            Sign in to access the network management dashboard
                        </Typography>

                        {error && (
                            <Alert severity="error" sx={{ mb: 2 }}>
                                {error}
                            </Alert>
                        )}

                        <Box component="form" onSubmit={handleSubmit} sx={{ mt: 1 }}>
                            <TextField
                                margin="normal"
                                required
                                fullWidth
                                id="username"
                                label="Username"
                                name="username"
                                autoComplete="username"
                                autoFocus
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                disabled={loading}
                            />
                            <TextField
                                margin="normal"
                                required
                                fullWidth
                                name="password"
                                label="Password"
                                type="password"
                                id="password"
                                autoComplete="current-password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                disabled={loading}
                            />

                            {showMfa && (
                                <TextField
                                    margin="normal"
                                    required
                                    fullWidth
                                    name="mfaToken"
                                    label="MFA Token"
                                    id="mfaToken"
                                    value={mfaToken}
                                    onChange={(e) => setMfaToken(e.target.value)}
                                    disabled={loading}
                                    helperText="Enter the 6-digit code from your authenticator app"
                                />
                            )}

                            <Button
                                type="submit"
                                fullWidth
                                variant="contained"
                                sx={{ mt: 3, mb: 2 }}
                                disabled={loading}
                            >
                                {loading ? (
                                    <CircularProgress size={24} />
                                ) : (
                                    'Sign In'
                                )}
                            </Button>
                        </Box>
                    </CardContent>
                </Card>
            </Box>
        </Container>
    )
}

export default Login