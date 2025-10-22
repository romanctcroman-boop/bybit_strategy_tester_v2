import React from 'react';
import { List, ListItem, ListItemText, Pagination, Stack } from '@mui/material';

export interface PaginatedListProps<T> {
  items: T[];
  total?: number;
  limit: number;
  offset: number;
  renderItem: (item: T) => React.ReactNode;
  onPageChange: (page: number) => void;
}

export default function PaginatedList<T>(props: PaginatedListProps<T>) {
  const { items, total = items.length, limit, offset, renderItem, onPageChange } = props;
  const page = Math.floor(offset / limit) + 1;
  const count = Math.max(1, Math.ceil((total || 0) / limit));
  return (
    <>
      <List>
        {items.map((it, idx) => (
          <React.Fragment key={(it as any)?.id ?? idx}>{renderItem(it)}</React.Fragment>
        ))}
      </List>
      <Stack direction="row" justifyContent="center" sx={{ mt: 2 }}>
        <Pagination page={page} count={count} onChange={(_, p) => onPageChange(p)} />
      </Stack>
    </>
  );
}
