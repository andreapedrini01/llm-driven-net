# Northbound Dashboard Frontend

React-based dashboard for the Northbound Script Generator system.

## Features

- **Real-time Dashboard**: System status, metrics, and action progress
- **Action Management**: View, monitor, and cancel network actions
- **Network Topology**: Visualization of network components
- **Log Viewer**: Advanced filtering and search of system logs
- **Alert Management**: View and acknowledge system alerts
- **Authentication**: JWT-based authentication with MFA support
- **Real-time Updates**: WebSocket integration for live updates

## Technology Stack

- **React 18** with TypeScript
- **Material-UI (MUI)** for UI components
- **Vite** for build tooling
- **Recharts** for data visualization
- **React Router** for navigation
- **Axios** for API communication
- **WebSocket** for real-time updates

## Development

### Prerequisites

- Node.js 16+ and npm/yarn
- Backend API running on port 8000

### Installation

```bash
cd frontend
npm install
```

### Development Server

```bash
npm run dev
```

The application will be available at http://localhost:3000

### Build for Production

```bash
npm run build
```

## Project Structure

```
frontend/
├── src/
│   ├── components/          # Reusable UI components
│   │   └── Layout.tsx       # Main application layout
│   ├── contexts/            # React contexts
│   │   ├── AuthContext.tsx  # Authentication state
│   │   └── WebSocketContext.tsx # WebSocket connection
│   ├── pages/               # Page components
│   │   ├── Dashboard.tsx    # Main dashboard
│   │   ├── Actions.tsx      # Action management
│   │   ├── Topology.tsx     # Network topology
│   │   ├── Logs.tsx         # Log viewer
│   │   ├── Alerts.tsx       # Alert management
│   │   ├── Settings.tsx     # Settings page
│   │   └── Login.tsx        # Login page
│   ├── services/            # API services
│   │   └── api.ts           # API client and endpoints
│   ├── App.tsx              # Main application component
│   └── main.tsx             # Application entry point
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## API Integration

The frontend communicates with the backend API through:

- **REST API**: Standard CRUD operations
- **WebSocket**: Real-time updates for dashboard metrics and action status
- **Authentication**: JWT tokens with automatic refresh

## Features Implementation Status

- ✅ Dashboard with system status and metrics
- ✅ Action management and progress tracking
- ✅ Log viewer with filtering
- ✅ Alert management
- ✅ Authentication system
- ✅ Real-time updates via WebSocket
- 🔄 Network topology visualization (basic structure)
- 🔄 Advanced settings management

## Configuration

The frontend is configured to proxy API requests to the backend:

- API requests to `/api/*` are proxied to `http://localhost:8000`
- WebSocket connections to `/ws` are proxied to `ws://localhost:8000`

## Deployment

For production deployment:

1. Build the application: `npm run build`
2. Serve the `dist` folder using a web server
3. Configure the web server to proxy API requests to the backend
4. Ensure WebSocket connections are properly configured

## Contributing

1. Follow TypeScript and React best practices
2. Use Material-UI components consistently
3. Implement proper error handling
4. Add loading states for async operations
5. Ensure responsive design for mobile devices