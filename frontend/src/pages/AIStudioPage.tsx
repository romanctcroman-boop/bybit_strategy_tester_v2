/**
 * AIStudioPage Component - AI-Powered Strategy Assistant
 * Copilot ↔ Perplexity AI ↔ Copilot Integration via MCP Server
 *
 * Features:
 * - Chat Interface for AI queries
 * - Live Results Panel with streaming responses
 * - Workflow History (saved queries & results)
 * - Strategy Code Generation
 * - Backtest Analysis & Recommendations
 * - Parameter Optimization Suggestions
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Paper,
  CircularProgress,
  Chip,
  Grid,
  IconButton,
  Divider,
  List,
  ListItem,
  ListItemText,
  Tab,
  Tabs,
} from '@mui/material';
import {
  Send,
  Psychology,
  Code,
  Assessment,
  AutoAwesome,
  ContentCopy,
  Download,
  History,
} from '@mui/icons-material';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  type?: 'text' | 'code' | 'analysis';
}

interface WorkflowItem {
  id: string;
  query: string;
  response: string;
  timestamp: Date;
  tokens: number;
}

const AIStudioPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content:
        '👋 Welcome to AI Studio! I can help you with:\n\n• Strategy code generation\n• Backtest analysis\n• Parameter optimization\n• Trading insights from Perplexity AI\n\nWhat would you like to work on today?',
      timestamp: new Date(),
      type: 'text',
    },
  ]);
  const [inputValue, setInputValue] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [workflowHistory, setWorkflowHistory] = useState<WorkflowItem[]>([]);
  const [activeTab, setActiveTab] = useState<number>(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load workflow history from localStorage
  useEffect(() => {
    const savedHistory = localStorage.getItem('ai_workflow_history');
    if (savedHistory) {
      try {
        const parsed = JSON.parse(savedHistory);
        setWorkflowHistory(
          parsed.map((item: WorkflowItem) => ({
            ...item,
            timestamp: new Date(item.timestamp),
          }))
        );
      } catch (e) {
        console.error('Failed to load workflow history:', e);
      }
    }
  }, []);

  // Send message to MCP Bridge
  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date(),
      type: 'text',
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setLoading(true);

    try {
      // Call MCP Bridge endpoint
      const response = await axios.post(`${API_BASE_URL}/api/ai/query`, {
        query: inputValue,
        context: {
          session_id: sessionStorage.getItem('session_id') || 'default',
          history: messages.slice(-5), // Last 5 messages for context
        },
      });

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.data.response,
        timestamp: new Date(),
        type: response.data.type || 'text',
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Save to workflow history
      const workflowItem: WorkflowItem = {
        id: Date.now().toString(),
        query: inputValue,
        response: response.data.response,
        timestamp: new Date(),
        tokens: response.data.tokens || 0,
      };

      const updatedHistory = [workflowItem, ...workflowHistory].slice(0, 50); // Keep last 50
      setWorkflowHistory(updatedHistory);
      localStorage.setItem('ai_workflow_history', JSON.stringify(updatedHistory));
    } catch (error) {
      console.error('AI query failed:', error);

      // Mock response for development
      const mockResponse: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `🤖 **AI Response** (Mock - API unavailable)\n\nI understand you're asking about: "${inputValue}"\n\nHere's what I can help with:\n\n1. **Strategy Code Generation**: I can create custom trading strategies based on your requirements.\n2. **Backtest Analysis**: Analyze backtest results and provide optimization suggestions.\n3. **Parameter Tuning**: Recommend optimal parameters using ML-based optimization.\n\nPlease make sure the MCP Server is running:\n\`\`\`bash\ncd mcp-server\npython server.py\n\`\`\`\n\nThen retry your query.`,
        timestamp: new Date(),
        type: 'text',
      };

      setMessages((prev) => [...prev, mockResponse]);
    } finally {
      setLoading(false);
    }
  };

  // Copy message content to clipboard
  const handleCopyMessage = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  // Quick action buttons
  const quickActions = [
    {
      label: 'Generate Strategy',
      icon: <Code />,
      prompt: 'Generate a mean reversion strategy with RSI and Bollinger Bands',
    },
    {
      label: 'Analyze Backtest',
      icon: <Assessment />,
      prompt: 'Analyze my latest backtest results and suggest improvements',
    },
    {
      label: 'Optimize Parameters',
      icon: <AutoAwesome />,
      prompt: 'What are the optimal parameters for SR Mean Reversion strategy?',
    },
  ];

  const handleQuickAction = (prompt: string) => {
    setInputValue(prompt);
  };

  // Render message based on type
  const renderMessage = (message: Message) => {
    const isUser = message.role === 'user';

    return (
      <Box
        key={message.id}
        sx={{
          display: 'flex',
          justifyContent: isUser ? 'flex-end' : 'flex-start',
          mb: 2,
        }}
      >
        <Paper
          elevation={1}
          sx={{
            maxWidth: '75%',
            p: 2,
            backgroundColor: isUser ? '#1976d2' : '#f5f5f5',
            color: isUser ? '#fff' : '#000',
            borderRadius: 2,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
            {!isUser && <Psychology sx={{ mr: 1, fontSize: 20 }} />}
            <Typography variant="caption" sx={{ opacity: 0.7 }}>
              {message.timestamp.toLocaleTimeString()}
            </Typography>
            <IconButton
              size="small"
              sx={{ ml: 'auto' }}
              onClick={() => handleCopyMessage(message.content)}
            >
              <ContentCopy sx={{ fontSize: 16 }} />
            </IconButton>
          </Box>
          <Typography
            variant="body2"
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {message.content}
          </Typography>
          {message.type === 'code' && (
            <Chip label="Code" size="small" sx={{ mt: 1 }} color="primary" />
          )}
        </Paper>
      </Box>
    );
  };

  return (
    <Box sx={{ display: 'flex', height: 'calc(100vh - 64px)', backgroundColor: '#f5f5f5' }}>
      {/* Main Chat Area (70%) */}
      <Box sx={{ flex: '0 0 70%', display: 'flex', flexDirection: 'column', p: 2 }}>
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Typography
              variant="h5"
              gutterBottom
              sx={{ fontWeight: 600, display: 'flex', alignItems: 'center' }}
            >
              <Psychology sx={{ mr: 1, color: '#9c27b0' }} />
              AI Studio - Copilot ↔ Perplexity AI
            </Typography>
            <Typography variant="body2" color="text.secondary">
              AI-powered strategy assistant via MCP Server integration
            </Typography>
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Grid container spacing={1} sx={{ mb: 2 }}>
          {quickActions.map((action, index) => (
            <Grid item xs={12} sm={4} key={index}>
              <Button
                fullWidth
                variant="outlined"
                startIcon={action.icon}
                onClick={() => handleQuickAction(action.prompt)}
                sx={{ py: 1 }}
              >
                {action.label}
              </Button>
            </Grid>
          ))}
        </Grid>

        {/* Messages Container */}
        <Card sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <CardContent sx={{ flex: 1, overflowY: 'auto', p: 3 }}>
            {messages.map((message) => renderMessage(message))}
            {loading && (
              <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}>
                <CircularProgress size={24} />
                <Typography variant="body2" sx={{ ml: 2 }}>
                  AI is thinking...
                </Typography>
              </Box>
            )}
            <div ref={messagesEndRef} />
          </CardContent>

          <Divider />

          {/* Input Area */}
          <Box sx={{ p: 2, backgroundColor: '#fafafa' }}>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField
                fullWidth
                multiline
                maxRows={4}
                placeholder="Ask AI anything about trading strategies, backtests, or optimizations..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                disabled={loading}
              />
              <Button
                variant="contained"
                onClick={handleSendMessage}
                disabled={loading || !inputValue.trim()}
                sx={{ px: 3 }}
              >
                <Send />
              </Button>
            </Box>
          </Box>
        </Card>
      </Box>

      {/* Workflow History Sidebar (30%) */}
      <Box sx={{ flex: '0 0 30%', p: 2, pl: 0 }}>
        <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Tabs value={activeTab} onChange={(_, v) => setActiveTab(v)}>
              <Tab label="History" icon={<History />} iconPosition="start" />
              <Tab label="Export" icon={<Download />} iconPosition="start" />
            </Tabs>
          </Box>

          {/* History Tab */}
          {activeTab === 0 && (
            <Box sx={{ flex: 1, overflowY: 'auto', p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Workflow History
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block' }}>
                {workflowHistory.length} saved conversations
              </Typography>
              <List>
                {workflowHistory.map((item) => (
                  <ListItem
                    key={item.id}
                    sx={{
                      flexDirection: 'column',
                      alignItems: 'flex-start',
                      borderBottom: '1px solid #e0e0e0',
                      cursor: 'pointer',
                      '&:hover': { backgroundColor: '#f5f5f5' },
                    }}
                    onClick={() => setInputValue(item.query)}
                  >
                    <ListItemText
                      primary={item.query}
                      secondary={item.timestamp.toLocaleString()}
                      primaryTypographyProps={{
                        variant: 'body2',
                        noWrap: true,
                        sx: { fontWeight: 600 },
                      }}
                      secondaryTypographyProps={{ variant: 'caption' }}
                    />
                    <Typography variant="caption" color="text.secondary">
                      {item.tokens} tokens
                    </Typography>
                  </ListItem>
                ))}
              </List>
            </Box>
          )}

          {/* Export Tab */}
          {activeTab === 1 && (
            <Box sx={{ flex: 1, p: 2 }}>
              <Typography variant="h6" gutterBottom>
                Export Options
              </Typography>
              <Button
                fullWidth
                variant="outlined"
                startIcon={<Download />}
                sx={{ mb: 2 }}
                onClick={() => {
                  const data = JSON.stringify(workflowHistory, null, 2);
                  const blob = new Blob([data], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `ai_workflow_${Date.now()}.json`;
                  a.click();
                }}
              >
                Export as JSON
              </Button>
              <Button
                fullWidth
                variant="outlined"
                startIcon={<Download />}
                onClick={() => {
                  const text = workflowHistory
                    .map((item) => `Q: ${item.query}\n\nA: ${item.response}\n\n---\n\n`)
                    .join('');
                  const blob = new Blob([text], { type: 'text/plain' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `ai_workflow_${Date.now()}.txt`;
                  a.click();
                }}
              >
                Export as Text
              </Button>
            </Box>
          )}
        </Card>
      </Box>
    </Box>
  );
};

export default AIStudioPage;
