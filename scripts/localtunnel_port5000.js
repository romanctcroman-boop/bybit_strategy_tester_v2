#!/usr/bin/env node
/**
 * Запуск localtunnel на порт 5000 и вывод публичного URL.
 * Использование: node scripts/localtunnel_port5000.js
 * Или: npx localtunnel --port 5000
 */
const { spawn } = require('child_process');
const path = require('path');

const lt = spawn('npx', ['--yes', 'localtunnel', '--port', '5000'], {
  cwd: path.join(__dirname, '..'),
  stdio: ['ignore', 'pipe', 'pipe'],
});

let url = null;
lt.stdout.setEncoding('utf8');
lt.stderr.setEncoding('utf8');

lt.stdout.on('data', (data) => {
  process.stdout.write(data);
  const m = data.match(/https:\/\/[^\s]+/);
  if (m) url = m[0];
});

lt.stderr.on('data', (data) => {
  process.stderr.write(data);
  const m = data.match(/https:\/\/[^\s]+/);
  if (m) url = m[0];
});

lt.on('close', (code) => process.exit(code || 0));
