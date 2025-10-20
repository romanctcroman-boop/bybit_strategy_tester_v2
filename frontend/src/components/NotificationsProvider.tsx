import React, { createContext, useContext, useState } from 'react';
import { Snackbar, Alert } from '@mui/material';

type Severity = 'success' | 'info' | 'warning' | 'error';

interface Notification {
  message: string;
  severity?: Severity;
}

const NotificationsContext = createContext<(n: Notification) => void>(() => {});

export const useNotify = () => {
  const setState = useContext(NotificationsContext);
  if (!setState) throw new Error('useNotify must be used within NotificationsProvider');
  return setState;
};

const NotificationsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState<Notification | null>(null);

  const notify = (n: Notification) => {
    setNote(n);
    setOpen(true);
  };

  return (
    <NotificationsContext.Provider value={notify}>
      {children}
      <Snackbar open={open} autoHideDuration={6000} onClose={() => setOpen(false)}>
        <Alert severity={note?.severity || 'info'} onClose={() => setOpen(false)}>
          {note?.message}
        </Alert>
      </Snackbar>
    </NotificationsContext.Provider>
  );
};

export default NotificationsProvider;
