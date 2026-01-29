import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Box } from '@mui/material'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Actions from './pages/Actions'
import Topology from './pages/Topology'
import Logs from './pages/Logs'
import Alerts from './pages/Alerts'
import Settings from './pages/Settings'
import Login from './pages/Login'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { WebSocketProvider } from './contexts/WebSocketContext'

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { isAuthenticated } = useAuth()
    return isAuthenticated ? <>{children}</> : <Navigate to="/login" />
}

const AppRoutes: React.FC = () => {
    const { isAuthenticated } = useAuth()

    if (!isAuthenticated) {
        return (
            <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="*" element={<Navigate to="/login" />} />
            </Routes>
        )
    }

    return (
        <WebSocketProvider>
            <Layout>
                <Routes>
                    <Route path="/" element={<Navigate to="/dashboard" />} />
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/actions" element={<Actions />} />
                    <Route path="/topology" element={<Topology />} />
                    <Route path="/logs" element={<Logs />} />
                    <Route path="/alerts" element={<Alerts />} />
                    <Route path="/settings" element={<Settings />} />
                    <Route path="*" element={<Navigate to="/dashboard" />} />
                </Routes>
            </Layout>
        </WebSocketProvider>
    )
}

const App: React.FC = () => {
    return (
        <AuthProvider>
            <Box sx={{ display: 'flex', minHeight: '100vh' }}>
                <AppRoutes />
            </Box>
        </AuthProvider>
    )
}

export default App