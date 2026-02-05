/**
 * MCP (Model Context Protocol) server for DeepSeek API.
 * Set DEEPSEEK_API_KEY in .env in this folder or in Cursor MCP server env.
 */

import path from "path";
import { fileURLToPath } from "url";
import dotenv from "dotenv";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { ListToolsRequestSchema, CallToolRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import OpenAI from "openai";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.join(__dirname, ".env") });

const apiKey = process.env.DEEPSEEK_API_KEY;
if (!apiKey) {
  console.error("[mcp-deepseek] DEEPSEEK_API_KEY is not set. Set it in .env or in Cursor MCP server env.");
}

const openai = new OpenAI({
  apiKey: apiKey || "placeholder",
  baseURL: "https://api.deepseek.com",
});

const server = new Server(
  {
    name: "deepseek-mcp-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

const TOOLS = [
  {
    name: "deepseek_chat",
    description: "Отправить запрос к модели DeepSeek (чат или код)",
    inputSchema: {
      type: "object",
      properties: {
        message: { type: "string", description: "Сообщение для модели DeepSeek" },
        model: {
          type: "string",
          description: "Модель: deepseek-chat или deepseek-coder",
          enum: ["deepseek-chat", "deepseek-coder"],
          default: "deepseek-chat",
        },
        temperature: { type: "number", minimum: 0, maximum: 2, default: 0.7 },
        max_tokens: { type: "number", default: 2000 },
      },
      required: ["message"],
    },
  },
  {
    name: "deepseek_code_completion",
    description: "Завершение кода с помощью DeepSeek Coder",
    inputSchema: {
      type: "object",
      properties: {
        code: { type: "string", description: "Частичный код для завершения" },
        language: { type: "string", default: "python" },
        temperature: { type: "number", minimum: 0, maximum: 2, default: 0.2 },
        max_tokens: { type: "number", default: 1000 },
      },
      required: ["code"],
    },
  },
];

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === "deepseek_chat") {
    try {
      const message = args?.message ?? "";
      const model = args?.model ?? "deepseek-chat";
      const temperature = args?.temperature ?? 0.7;
      const max_tokens = args?.max_tokens ?? 2000;

      const response = await openai.chat.completions.create({
        model,
        messages: [{ role: "user", content: message }],
        temperature,
        max_tokens,
        stream: false,
      });

      const text = response.choices?.[0]?.message?.content ?? "Нет ответа";
      return { content: [{ type: "text", text }] };
    } catch (err) {
      return {
        content: [{ type: "text", text: `Ошибка: ${err.message}` }],
        isError: true,
      };
    }
  }

  if (name === "deepseek_code_completion") {
    try {
      const code = args?.code ?? "";
      const language = args?.language ?? "python";
      const temperature = args?.temperature ?? 0.2;
      const max_tokens = args?.max_tokens ?? 1000;
      const prompt = `Заверши следующий код на ${language}:\n\n${code}\n\nЗавершение:`;

      const response = await openai.chat.completions.create({
        model: "deepseek-coder",
        messages: [{ role: "user", content: prompt }],
        temperature,
        max_tokens,
        stream: false,
      });

      const text = response.choices?.[0]?.message?.content ?? "";
      return { content: [{ type: "text", text }] };
    } catch (err) {
      return {
        content: [{ type: "text", text: `Ошибка: ${err.message}` }],
        isError: true,
      };
    }
  }

  return {
    content: [{ type: "text", text: `Unknown tool: ${name}` }],
    isError: true,
  };
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("DeepSeek MCP server running");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
