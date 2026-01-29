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
    FormControl,
    InputLabel,
    Select,
    OutlinedInput,
    Alert,
    Switch,
    FormControlLabel,
} from '@mui/material'
import {
    DataGrid,
    GridColDef,
    GridActionsCellItem,
    GridRowParams,
} from '@mui/x-data-grid'
import {
    Edit as EditIcon,
    PersonOff as DisableIcon,
    PersonAdd as AddIcon,
    Refresh as RefreshIcon,
} from '@mui/icons-material'
import { apiClient } from '../services/api'
import { format } from 'date-fns'

interface User {
    id: string
    username: string
    email: string
    roles: string[]
    is_active: boolean
    created_at: string
    last_login?: string
}

const UserManagement: React.FC = () => {
    const [users, setUsers] = useState<User[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [editDialogOpen, setEditDialogOpen] = useState(false)
    const [selectedUser, setSelectedUser] = useState<User | null>(null)
    const [editRoles, setEditRoles] = useState<string[]>([])

    const availableRoles = ['admin', 'operator', 'viewer']

    const fetchUsers = async () => {
        try {
            setLoading(true)
            const response = await apiClient.get('/dashboard/users')
            setUsers(response.data)
            setError(null)
        } catch (err) {
            setError('Failed to fetch users')
            console.error('Users fetch error:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchUsers()
    }, [])

    const handleToggleUserStatus = async (userId: string) => {
        try {
            await apiClient.post(`/dashboard/users/${userId}/toggle-status`)
            fetchUsers()
        } catch (err) {
            console.error('Failed to toggle user status:', err)
        }
    }

    const handleEditUser = (user: User) => {
        setSelectedUser(user)
        setEditRoles(user.roles)
        setEditDialogOpen(true)
    }

    const handleSaveUserRoles = async () => {
        if (!selectedUser) return

        try {
            await apiClient.put(`/dashboard/users/${selectedUser.id}/roles`, editRoles)
            setEditDialogOpen(false)
            fetchUsers()
        } catch (err) {
            console.error('Failed to update user roles:', err)
        }
    }

    const getRoleColor = (role: string) => {
        switch (role) {
            case 'admin': return 'error'
            case 'operator': return 'warning'
            case 'viewer': return 'info'
            default: return 'default'
        }
    }

    const columns: GridColDef[] = [
        {
            field: 'username',
            headerName: 'Username',
            width: 150,
        },
        {
            field: 'email',
            headerName: 'Email',
            width: 200,
        },
        {
            field: 'roles',
            headerName: 'Roles',
            width: 200,
            renderCell: (params) => (
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                    {params.value.map((role: string) => (
                        <Chip
                            key={role}
                            label={role}
                            color={getRoleColor(role) as any}
                            size="small"
                        />
                    ))}
                </Box>
            ),
        },
        {
            field: 'is_active',
            headerName: 'Status',
            width: 100,
            renderCell: (params) => (
                <Chip
                    label={params.value ? 'Active' : 'Disabled'}
                    color={params.value ? 'success' : 'default'}
                    size="small"
                />
            ),
        },
        {
            field: 'last_login',
            headerName: 'Last Login',
            width: 180,
            renderCell: (params) => (
                params.value ? (
                    <Typography variant="body2">
                        {format(new Date(params.value), 'MMM dd, HH:mm')}
                    </Typography>
                ) : (
                    <Typography variant="body2" color="text.secondary">
                        Never
                    </Typography>
                )
            ),
        },
        {
            field: 'actions',
            type: 'actions',
            headerName: 'Actions',
            width: 120,
            getActions: (params: GridRowParams) => [
                <GridActionsCellItem
                    icon={<EditIcon />}
                    label="Edit Roles"
                    onClick={() => handleEditUser(params.row)}
                />,
                <GridActionsCellItem
                    icon={<DisableIcon />}
                    label={params.row.is_active ? 'Disable' : 'Enable'}
                    onClick={() => handleToggleUserStatus(params.row.id)}
                />,
            ],
        },
    ]

    return (
        <Box>
            {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                    {error}
                </Alert>
            )}

            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h6">
                    User Management
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                    <IconButton onClick={fetchUsers} disabled={loading}>
                        <RefreshIcon />
                    </IconButton>
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={() => {/* TODO: Implement add user */ }}
                    >
                        Add User
                    </Button>
                </Box>
            </Box>

            <Paper sx={{ height: 400, width: '100%' }}>
                <DataGrid
                    rows={users}
                    columns={columns}
                    loading={loading}
                    pageSizeOptions={[10, 25, 50]}
                    initialState={{
                        pagination: {
                            paginationModel: { page: 0, pageSize: 10 },
                        },
                    }}
                    disableRowSelectionOnClick
                />
            </Paper>

            {/* Edit User Roles Dialog */}
            <Dialog
                open={editDialogOpen}
                onClose={() => setEditDialogOpen(false)}
                maxWidth="sm"
                fullWidth
            >
                <DialogTitle>
                    Edit User Roles - {selectedUser?.username}
                </DialogTitle>
                <DialogContent>
                    <FormControl fullWidth sx={{ mt: 2 }}>
                        <InputLabel>Roles</InputLabel>
                        <Select
                            multiple
                            value={editRoles}
                            onChange={(e) => setEditRoles(e.target.value as string[])}
                            input={<OutlinedInput label="Roles" />}
                            renderValue={(selected) => (
                                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                    {selected.map((value) => (
                                        <Chip
                                            key={value}
                                            label={value}
                                            color={getRoleColor(value) as any}
                                            size="small"
                                        />
                                    ))}
                                </Box>
                            )}
                        >
                            {availableRoles.map((role) => (
                                <MenuItem key={role} value={role}>
                                    {role}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setEditDialogOpen(false)}>
                        Cancel
                    </Button>
                    <Button onClick={handleSaveUserRoles} variant="contained">
                        Save
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    )
}

export default UserManagement