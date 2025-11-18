"use strict";
/**
 * Agent-to-Agent Communication Bridge VS Code Extension
 * Связывает GitHub Copilot с DeepSeek/Perplexity агентами через WebSocket
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const ws_1 = __importDefault(require("ws"));
class AgentBridge {
    constructor(context) {
        this.context = context;
        this.ws = null;
        this.reconnectTimer = null;
        this.clientId = `vscode-${Date.now()}`;
        this.statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
        this.outputChannel = vscode.window.createOutputChannel('Agent Bridge');
        this.config = vscode.workspace.getConfiguration('agentBridge');
        this.statusBarItem.command = 'agent-bridge.toggleConnection';
        this.updateStatusBar('disconnected');
        this.statusBarItem.show();
        if (this.config.get('autoConnect', true)) {
            this.connect();
        }
    }
    /**
     * Подключение к WebSocket серверу
     */
    connect() {
        const serverUrl = this.config.get('serverUrl', 'ws://localhost:8000/api/v1/agent/ws');
        const fullUrl = `${serverUrl}/${this.clientId}`;
        this.outputChannel.appendLine(`🔌 Connecting to ${fullUrl}...`);
        try {
            this.ws = new ws_1.default(fullUrl);
            this.ws.on('open', () => {
                this.outputChannel.appendLine('✅ Connected to Agent-to-Agent server');
                this.updateStatusBar('connected');
                this.showNotification('Connected to Agent Bridge', 'info');
                // Отправить ping для проверки
                this.sendCommand({ command: 'ping' });
            });
            this.ws.on('message', (data) => {
                this.handleMessage(data.toString());
            });
            this.ws.on('error', (error) => {
                this.outputChannel.appendLine(`❌ WebSocket error: ${error.message}`);
                this.updateStatusBar('error');
            });
            this.ws.on('close', () => {
                this.outputChannel.appendLine('🔌 Disconnected from Agent Bridge');
                this.updateStatusBar('disconnected');
                this.scheduleReconnect();
            });
        }
        catch (error) {
            this.outputChannel.appendLine(`❌ Connection failed: ${error.message}`);
            this.updateStatusBar('error');
            this.scheduleReconnect();
        }
    }
    /**
     * Отключение от сервера
     */
    disconnect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.updateStatusBar('disconnected');
        this.outputChannel.appendLine('🔌 Manually disconnected');
    }
    /**
     * Переключение состояния подключения
     */
    toggleConnection() {
        if (this.ws && this.ws.readyState === ws_1.default.OPEN) {
            this.disconnect();
        }
        else {
            this.connect();
        }
    }
    /**
     * Планирование переподключения
     */
    scheduleReconnect() {
        if (this.reconnectTimer) {
            return;
        }
        this.outputChannel.appendLine('🔄 Reconnecting in 5 seconds...');
        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.connect();
        }, 5000);
    }
    /**
     * Обработка входящих сообщений
     */
    handleMessage(data) {
        try {
            const message = JSON.parse(data);
            this.outputChannel.appendLine(`📥 Received: ${JSON.stringify(message, null, 2)}`);
            switch (message.type) {
                case 'pong':
                    this.outputChannel.appendLine('💓 Server is alive');
                    break;
                case 'subscribed':
                    this.outputChannel.appendLine(`📡 Subscribed to conversation ${message.conversation_id}`);
                    break;
                case 'message_response':
                    this.handleAgentResponse(message);
                    break;
                case 'message_sent':
                    this.outputChannel.appendLine(`📨 Message sent: ${message.message_id}`);
                    break;
                default:
                    this.outputChannel.appendLine(`📦 Unknown message type: ${message.type}`);
            }
        }
        catch (error) {
            this.outputChannel.appendLine(`❌ Error parsing message: ${error.message}`);
        }
    }
    /**
     * Обработка ответа агента
     */
    handleAgentResponse(message) {
        const agent = message.from_agent;
        const content = message.content;
        const truncated = this.truncateResponse(content);
        this.outputChannel.appendLine(`\n${'='.repeat(80)}`);
        this.outputChannel.appendLine(`🤖 Response from ${agent}:`);
        this.outputChannel.appendLine(`${'='.repeat(80)}`);
        this.outputChannel.appendLine(content);
        this.outputChannel.appendLine(`${'='.repeat(80)}\n`);
        // Показать уведомление
        this.showNotification(`Response from ${agent}`, 'info');
        // Показать в новом редакторе
        this.showInNewEditor(content, agent);
    }
    /**
     * Отправка команды через WebSocket
     */
    sendCommand(command) {
        if (!this.ws || this.ws.readyState !== ws_1.default.OPEN) {
            vscode.window.showErrorMessage('Not connected to Agent Bridge');
            return false;
        }
        try {
            this.ws.send(JSON.stringify(command));
            this.outputChannel.appendLine(`📤 Sent: ${JSON.stringify(command, null, 2)}`);
            return true;
        }
        catch (error) {
            this.outputChannel.appendLine(`❌ Send error: ${error.message}`);
            vscode.window.showErrorMessage(`Failed to send: ${error.message}`);
            return false;
        }
    }
    /**
     * Отправка текста агенту
     */
    async sendToAgent(text, targetAgent) {
        const conversationId = `vscode-${Date.now()}`;
        const success = this.sendCommand({
            command: 'send_message',
            from_agent: 'copilot',
            to_agent: targetAgent,
            content: text,
            conversation_id: conversationId
        });
        if (success) {
            // Подписаться на ответы
            this.sendCommand({
                command: 'subscribe',
                conversation_id: conversationId
            });
            this.outputChannel.show();
            this.outputChannel.appendLine(`\n📨 Sent to ${targetAgent}:\n${text}\n`);
            vscode.window.showInformationMessage(`Sent to ${targetAgent}. Check Output panel for response.`);
        }
    }
    /**
     * Обновление статус бара
     */
    updateStatusBar(status) {
        const icons = {
            connected: '$(broadcast)',
            disconnected: '$(debug-disconnect)',
            error: '$(error)'
        };
        const colors = {
            connected: undefined,
            disconnected: new vscode.ThemeColor('statusBarItem.warningBackground'),
            error: new vscode.ThemeColor('statusBarItem.errorBackground')
        };
        this.statusBarItem.text = `${icons[status]} Agent Bridge`;
        this.statusBarItem.backgroundColor = colors[status];
        this.statusBarItem.tooltip = `Agent-to-Agent Bridge: ${status}`;
    }
    /**
     * Показать уведомление
     */
    showNotification(message, type) {
        if (!this.config.get('showNotifications', true)) {
            return;
        }
        switch (type) {
            case 'info':
                vscode.window.showInformationMessage(message);
                break;
            case 'warning':
                vscode.window.showWarningMessage(message);
                break;
            case 'error':
                vscode.window.showErrorMessage(message);
                break;
        }
    }
    /**
     * Обрезка длинного ответа
     */
    truncateResponse(text) {
        const maxLength = this.config.get('maxResponseLength', 5000);
        if (text.length <= maxLength) {
            return text;
        }
        return text.substring(0, maxLength) + '\n\n... (truncated)';
    }
    /**
     * Показать ответ в новом редакторе
     */
    async showInNewEditor(content, agent) {
        const doc = await vscode.workspace.openTextDocument({
            content: content,
            language: 'markdown'
        });
        await vscode.window.showTextDocument(doc, {
            preview: false,
            viewColumn: vscode.ViewColumn.Beside
        });
    }
    /**
     * Очистка ресурсов
     */
    dispose() {
        this.disconnect();
        this.statusBarItem.dispose();
        this.outputChannel.dispose();
    }
}
// Глобальный экземпляр моста
let agentBridge = null;
/**
 * Активация расширения
 */
function activate(context) {
    console.log('Agent-to-Agent Bridge extension is activating...');
    // Создание моста
    agentBridge = new AgentBridge(context);
    context.subscriptions.push(agentBridge);
    // Регистрация команд
    context.subscriptions.push(vscode.commands.registerCommand('agent-bridge.sendToDeepSeek', async () => {
        await sendSelectedTextToAgent('deepseek');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('agent-bridge.sendToPerplexity', async () => {
        await sendSelectedTextToAgent('perplexity');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('agent-bridge.startConversation', async () => {
        await startAgentConversation();
    }));
    context.subscriptions.push(vscode.commands.registerCommand('agent-bridge.getConsensus', async () => {
        await getMultiAgentConsensus();
    }));
    context.subscriptions.push(vscode.commands.registerCommand('agent-bridge.toggleConnection', () => {
        agentBridge?.toggleConnection();
    }));
    console.log('✅ Agent-to-Agent Bridge extension is now active');
}
/**
 * Отправка выделенного текста агенту
 */
async function sendSelectedTextToAgent(agent) {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showErrorMessage('No active editor');
        return;
    }
    const selection = editor.selection;
    let text = editor.document.getText(selection);
    if (!text) {
        // Если нет выделения - взять весь документ
        const useFullDocument = await vscode.window.showQuickPick(['Yes', 'No'], { placeHolder: 'No text selected. Send entire document?' });
        if (useFullDocument === 'Yes') {
            text = editor.document.getText();
        }
        else {
            return;
        }
    }
    // Опционально добавить контекст
    const addContext = await vscode.window.showQuickPick(['Just send text', 'Add analysis request', 'Add optimization request', 'Custom prompt'], { placeHolder: 'How to send this text?' });
    let finalText = text;
    switch (addContext) {
        case 'Add analysis request':
            finalText = `Проанализируй этот код и дай рекомендации:\n\n${text}`;
            break;
        case 'Add optimization request':
            finalText = `Оптимизируй этот код:\n\n${text}`;
            break;
        case 'Custom prompt':
            const prompt = await vscode.window.showInputBox({
                prompt: 'Enter your prompt',
                placeHolder: 'What do you want the agent to do?'
            });
            if (prompt) {
                finalText = `${prompt}\n\n${text}`;
            }
            break;
    }
    agentBridge?.sendToAgent(finalText, agent);
}
/**
 * Запуск разговора между агентами
 */
async function startAgentConversation() {
    const question = await vscode.window.showInputBox({
        prompt: 'Enter topic for agent conversation',
        placeHolder: 'What should the agents discuss?'
    });
    if (!question) {
        return;
    }
    vscode.window.showInformationMessage('Agent conversation feature requires REST API call. Use HTTP client or implement REST endpoint.');
    // TODO: Implement via HTTP request to /api/v1/agent/conversation
}
/**
 * Получение консенсуса от нескольких агентов
 */
async function getMultiAgentConsensus() {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showErrorMessage('No active editor');
        return;
    }
    const selection = editor.selection;
    const text = editor.document.getText(selection);
    if (!text) {
        vscode.window.showErrorMessage('Please select text first');
        return;
    }
    const question = await vscode.window.showInputBox({
        prompt: 'What question should agents answer about this text?',
        placeHolder: 'e.g., "What are the potential issues here?"'
    });
    if (!question) {
        return;
    }
    const fullPrompt = `${question}\n\nContext:\n${text}`;
    // Отправить и DeepSeek и Perplexity параллельно
    vscode.window.showInformationMessage('Getting consensus from DeepSeek and Perplexity...');
    agentBridge?.sendToAgent(fullPrompt, 'deepseek');
    // Небольшая задержка перед вторым запросом
    setTimeout(() => {
        agentBridge?.sendToAgent(fullPrompt, 'perplexity');
    }, 1000);
}
/**
 * Деактивация расширения
 */
function deactivate() {
    agentBridge?.dispose();
    agentBridge = null;
    console.log('Agent-to-Agent Bridge extension is deactivated');
}
//# sourceMappingURL=extension.js.map