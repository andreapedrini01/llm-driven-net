import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { apiClient } from '../services/api'

interface User {
    username: string
    email?: string
    roles: string[]
    isActive: boolean
}

interface AuthContextType {
    user: User | null
    isAuthenticated: boolean
    login: (username: string, password: string, mfaToken?: string) => Promise<boolean>
    logout: () => void
    loading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const useAuth = () => {
    const context = useContext(AuthContext)
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider')
    }
    return context
}

interface AuthProviderProps {
    children: ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        // Check if user is already logged in
        const token = localStorage.getItem('access_token')
        if (token) {
            // Validate token and get user info
            apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`
            // You would typically validate the token here
            // For now, we'll assume it's valid if it exists
            setUser({
                username: 'admin', // This should come from token validation
                roles: ['admin'],
                isActive: true
            })
        }
        setLoading(false)
    }, [])

    const login = async (username: string, password: string, mfaToken?: string): Promise<boolean> => {
        try {
            const response = await apiClient.post('/auth/login', {
                username,
                password,
                mfa_token: mfaToken
            })

            const { access_token, user_info } = response.data

            // Store token
            localStorage.setItem('access_token', access_token)
            apiClient.defaults.headers.common['Authorization'] = `Bearer ${access_token}`

            // Set user
            setUser(user_info)

            return true
        } catch (error) {
            console.error('Login failed:', error)
            return false
        }
    }

    const logout = () => {
        localStorage.removeItem('access_token')
        delete apiClient.defaults.headers.common['Authorization']
        setUser(null)
    }

    const value: AuthContextType = {
        user,
        isAuthenticated: !!user,
        login,
        logout,
        loading
    }

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    )
}