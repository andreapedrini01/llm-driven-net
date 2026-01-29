import React from 'react'
import {
    Box,
    Paper,
    Typography,
    Card,
    CardContent,
    Grid,
    Tabs,
    Tab,
} from '@mui/material'
import UserManagement from '../components/UserManagement'

interface TabPanelProps {
    children?: React.ReactNode
    index: number
    value: number
}

function TabPanel(props: TabPanelProps) {
    const { children, value, index, ...other } = props

    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`settings-tabpanel-${index}`}
            aria-labelledby={`settings-tab-${index}`}
            {...other}
        >
            {value === index && (
                <Box sx={{ p: 3 }}>
                    {children}
                </Box>
            )}
        </div>
    )
}

const Settings: React.FC = () => {
    const [tabValue, setTabValue] = React.useState(0)

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setTabValue(newValue)
    }

    return (
        <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h4" component="h1" gutterBottom>
                Settings
            </Typography>

            <Paper sx={{ width: '100%' }}>
                <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                    <Tabs value={tabValue} onChange={handleTabChange}>
                        <Tab label="User Management" />
                        <Tab label="System Configuration" />
                        <Tab label="Notifications" />
                    </Tabs>
                </Box>

                <TabPanel value={tabValue} index={0}>
                    <UserManagement />
                </TabPanel>

                <TabPanel value={tabValue} index={1}>
                    <Grid container spacing={3}>
                        <Grid item xs={12} md={6}>
                            <Card>
                                <CardContent>
                                    <Typography variant="h6" gutterBottom>
                                        System Configuration
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        System configuration options would be implemented here
                                    </Typography>
                                </CardContent>
                            </Card>
                        </Grid>

                        <Grid item xs={12} md={6}>
                            <Card>
                                <CardContent>
                                    <Typography variant="h6" gutterBottom>
                                        Performance Settings
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Performance tuning options would be implemented here
                                    </Typography>
                                </CardContent>
                            </Card>
                        </Grid>
                    </Grid>
                </TabPanel>

                <TabPanel value={tabValue} index={2}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                Notification Settings
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                                Notification preferences and alert configuration would be implemented here
                            </Typography>
                        </CardContent>
                    </Card>
                </TabPanel>
            </Paper>
        </Box>
    )
}

export default Settings