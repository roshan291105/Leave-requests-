'use strict';

// Serve the existing website and its database-backed pages through Node.js.
// Start the Flask backend first: .\web\.venv\Scripts\python.exe web/app.py
const http = require('node:http');
const https = require('node:https');

const HOP_HEADERS = new Set([
  'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'proxy-connection', 'te', 'trailer', 'transfer-encoding', 'upgrade',
]);

function forwardedHeaders(headers) {
  const excluded = new Set(HOP_HEADERS);
  for (const name of (headers.connection || '').split(',')) {
    excluded.add(name.trim().toLowerCase());
  }
  return Object.fromEntries(Object.entries(headers).filter(([name]) => !excluded.has(name)));
}

function createServer({ backendUrl = 'http://127.0.0.1:5000', timeout = 30000 } = {}) {
  const backend = new URL(backendUrl);
  if (!['http:', 'https:'].includes(backend.protocol)
      || backend.username || backend.password || backend.pathname !== '/'
      || backend.search || backend.hash) {
    throw new Error('BACKEND_URL must be an HTTP(S) origin, for example http://127.0.0.1:5000.');
  }
  const transport = backend.protocol === 'https:' ? https : http;

  return http.createServer((request, response) => {
    // Keep the destination fixed; never use a client-supplied URL as the host.
    const upstream = transport.request({
      protocol: backend.protocol,
      hostname: backend.hostname.replace(/^\[|\]$/g, ''),
      port: backend.port || (backend.protocol === 'https:' ? 443 : 80),
      method: request.method,
      path: request.url,
      // Preserve the browser's Host and cookies so Flask redirects and sessions
      // continue to work on the Node server's port.
      headers: forwardedHeaders(request.headers),
    }, (backendResponse) => {
      response.writeHead(backendResponse.statusCode, forwardedHeaders(backendResponse.headers));
      backendResponse.on('error', () => response.destroy());
      backendResponse.pipe(response);
    });

    let timedOut = false;
    upstream.setTimeout(timeout, () => {
      timedOut = true;
      upstream.destroy();
    });
    upstream.on('error', () => {
      if (response.destroyed) return;
      if (response.headersSent) {
        response.destroy();
        return;
      }
      response.writeHead(timedOut ? 504 : 502, {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'no-store',
      });
      response.end(timedOut
        ? 'The backend took too long to respond. Please try again.\n'
        : 'The Flask backend is unavailable. Start web/app.py and check BACKEND_URL.\n');
    });
    request.on('aborted', () => upstream.destroy());
    request.on('error', () => upstream.destroy());
    response.on('close', () => upstream.destroy());
    request.pipe(upstream);
  });
}

if (require.main === module) {
  const host = process.env.HOST || '127.0.0.1';
  const rawPort = process.env.PORT || '3000';
  const port = Number(rawPort);
  if (!/^\d+$/.test(rawPort) || !Number.isInteger(port) || port < 1 || port > 65535) {
    console.error('PORT must be an integer between 1 and 65535.');
    process.exit(1);
  }

  let server;
  try {
    server = createServer({ backendUrl: process.env.BACKEND_URL || 'http://127.0.0.1:5000' });
  } catch {
    console.error('BACKEND_URL must be an HTTP(S) origin, for example http://127.0.0.1:5000.');
    process.exit(1);
  }
  server.on('error', (error) => {
    console.error(`Could not start the Node server (${error.code || 'unknown error'}). Check HOST and PORT.`);
    process.exitCode = 1;
  });
  server.listen(port, host, () => {
    const displayHost = host.includes(':') ? `[${host}]` : host;
    console.log(`Dayora website: http://${displayHost}:${port}`);
    console.log(`PostgreSQL data (administrator login): http://${displayHost}:${port}/admin/postgres-leave-requests`);
    console.log('Keep the Flask backend running. Press Ctrl+C to stop this Node server.');
  });
  for (const signal of ['SIGINT', 'SIGTERM']) {
    process.once(signal, () => {
      server.close();
      setTimeout(() => server.closeAllConnections(), 5000).unref();
    });
  }
}

module.exports = { createServer };
