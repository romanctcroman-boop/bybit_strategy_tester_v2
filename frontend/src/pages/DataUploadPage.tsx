import React, { useState } from 'react';
import { Container, Typography, Button } from '@mui/material';
import { useDataUploadStore } from '../store/dataUpload';
import { useNotify } from '../components/NotificationsProvider';

const DataUploadPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const { upload, uploading } = useDataUploadStore();
  const notify = useNotify();

  const submit = async () => {
    if (!file) return notify({ message: 'Select a file', severity: 'warning' });
    const fd = new FormData();
    fd.append('file', file);
    try {
      await upload(fd);
      notify({ message: 'Upload complete', severity: 'success' });
    } catch {
      notify({ message: 'Upload failed', severity: 'error' });
    }
  };

  return (
    <Container>
      <Typography variant="h4">Upload Market Data</Typography>
      <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      <Button variant="contained" onClick={submit} disabled={uploading} sx={{ ml: 2 }}>
        Upload
      </Button>
    </Container>
  );
};

export default DataUploadPage;
