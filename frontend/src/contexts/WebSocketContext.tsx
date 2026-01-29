import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { io, Socket } from 'socket.io-client'

interface WebSocketContextType {
    socket: Socket | null
    connected: boolean
    lastMessage: any
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined)

export const useWebSocket = () => {
    const context = useContext(WebSocketContext)
    if (context === undefined) {
        throw new Error('useWebSocket must be used within a WebSocketProvider')
    }
    return context
}

interface WebSocketProviderProps {
    children: ReactNode
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children }) => {
    const [socket, setSocket] = useState<Socket | null>(null)
    const [connected, setConnected] = useState(false)
    const [lastMessage, setLastMessage] = useState<any>(null)

    useEffect(() => {
        // Create WebSocket connection
        const ws = new WebSocket('ws://localhost:8000/api/v1/dashboard/ws')

        ws.onopen = () => {
            console.log('WebSocket connected')
            setConnected(true)
        }

        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data)
                setLastMessage(message)
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error)
            }
        }

        ws.onclose = () => {
            console.log('WebSocket disconnected')
            setConnected(false)
        }

        ws.onerror = (error) => {
            console.error('WebSocket error:', error)
            setConnected(false)
        }

        // Store WebSocket reference (note: Socket.IO not used here, using native WebSocket)
        // setSocket(ws as any)

        return () => {
            ws.close()
        }
    }, [])

    const value: WebSocketContextType = {
        socket,
        connected,
        lastMessage
    }

    return (
        <WebSocketContext.Provider value={value}>
            {children}
        </WebSocketContext.Provider>
    )
}