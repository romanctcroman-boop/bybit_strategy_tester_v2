import React from 'react';
import { Box, Button, Container, Stack, TextField, Typography } from '@mui/material';

type Rule = { id: string; condition: string };

const AlgoBuilderPage: React.FC = () => {
  const [rules, setRules] = React.useState<Rule[]>([
    { id: '1', condition: 'RSI(14) < 30' },
    { id: '2', condition: 'EMA(12) > EMA(26)' },
  ]);

  const addRule = () => setRules((r) => [...r, { id: String(r.length + 1), condition: '' }]);
  const save = () => {
    // Later: POST /strategies/blockly/save
    console.log('save rules', rules);
  };

  return (
    <Container maxWidth="md" sx={{ py: 3 }}>
      <Typography variant="h5" sx={{ fontWeight: 700, mb: 2 }}>Конструктор алгоритма (макет)</Typography>
      <Stack spacing={1.25}>
        {rules.map((r, i) => (
          <TextField key={r.id} label={`Условие ${i + 1}`} value={r.condition} onChange={(e) => setRules(rules.map((x) => (x.id === r.id ? { ...x, condition: e.target.value } : x)))} />
        ))}
        <Box>
          <Button onClick={addRule}>Добавить условие</Button>
          <Button variant="contained" sx={{ ml: 1 }} onClick={save}>Сохранить (мок)</Button>
        </Box>
        <Box sx={{ p: 2, border: '1px dashed', borderColor: 'divider', borderRadius: 1 }}>
          <Typography variant="subtitle2">JSON</Typography>
          <pre style={{ margin: 0 }}>{JSON.stringify({ rules }, null, 2)}</pre>
        </Box>
      </Stack>
    </Container>
  );
};

export default AlgoBuilderPage;
