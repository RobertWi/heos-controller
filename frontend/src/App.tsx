import { useEffect, useState } from 'react';
import { Container, Title, Text, Box, Button, Group, Badge } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { heosApi } from './api/heosApi';

interface DeviceInfo {
  name: string;
  model: string;
  version?: string;
  serial?: string;
  network?: string;
  pid?: number;
}

interface Device {
  ip: string;
  info: DeviceInfo;
  status: 'ready' | 'error' | 'initializing';
  error?: string;
}

function getDeviceKey(device: Device): string {
  // Convert pid to string, handling null/undefined
  const pid = device.info?.pid !== undefined && device.info?.pid !== null 
    ? device.info.pid.toString() 
    : 'unknown';
  // Add serial number to make the key even more unique
  const serial = device.info?.serial || '';
  return `${device.ip}-${pid}-${serial}`;
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'ready':
      return 'blue';
    case 'error':
      return 'red';
    case 'initializing':
      return 'yellow';
    default:
      return 'gray';
  }
}

function App() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchDevices = async () => {
    setLoading(true);
    try {
      const response = await heosApi.discover();
      console.log('Discovered devices:', response.devices);
      setDevices(response.devices);
      notifications.show({
        title: 'Success',
        message: `Found ${response.devices.length} devices`,
        color: 'blue',
      });
    } catch (error) {
      console.error('Error discovering devices:', error);
      notifications.show({
        title: 'Error',
        message: error instanceof Error ? error.message : 'Failed to discover devices',
        color: 'red',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDevices();
  }, []);

  return (
    <Box style={{ backgroundColor: '#1A1B1E', minHeight: '100vh', color: 'white' }}>
      <Container size="lg" py="xl">
        <Group position="apart" mb="xl">
          <Title order={1}>HEOS Controller</Title>
          <Button 
            onClick={fetchDevices} 
            loading={loading}
            variant="light"
          >
            Refresh Devices
          </Button>
        </Group>

        {devices.map(device => (
          <Box 
            key={getDeviceKey(device)}
            p="md" 
            mb="md" 
            style={{ 
              backgroundColor: '#25262B',
              borderRadius: '8px',
              border: '1px solid #373A40'
            }}
          >
            <Group position="apart" mb="xs">
              <div>
                <Text size="lg" weight={500}>{device.info?.name || 'Unknown Device'}</Text>
                <Text size="sm" color="dimmed">{device.info?.model || 'Unknown Model'}</Text>
              </div>
              <Badge 
                color={getStatusColor(device.status)}
                variant="light"
                size="lg"
              >
                {device.status}
              </Badge>
            </Group>
            
            <Text size="sm" color="dimmed">IP: {device.ip}</Text>
            {device.info?.pid && (
              <Text size="sm" color="dimmed">Player ID: {device.info.pid}</Text>
            )}
            
            {device.error && (
              <Text size="sm" color="red" mt="xs">
                Error: {device.error}
              </Text>
            )}
          </Box>
        ))}
        
        {devices.length === 0 && !loading && (
          <Text align="center" color="dimmed" size="lg" mt="xl">
            No devices found. Make sure your HEOS devices are powered on and connected to the network.
          </Text>
        )}
      </Container>
    </Box>
  );
}

export default App;
