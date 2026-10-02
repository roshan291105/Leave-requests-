'use strict';

const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');
const { test } = require('node:test');
const { createServer } = require('../server');

async function listen(server, context) {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  context.after(() => new Promise((resolve) => {
    server.close(resolve);
    server.closeAllConnections();
  }));
  return `http://127.0.0.1:${server.address().port}`;
}

function request(url, { method = 'GET', headers = {}, body = '' } = {}) {
  return new Promise((resolve, reject) => {
    const outgoing = http.request(url, { method, headers }, (response) => {
      const chunks = [];
      response.on('data', (chunk) => chunks.push(chunk));
      response.on('error', reject);
      response.on('end', () => resolve({
        status: response.statusCode,
        headers: response.headers,
        body: Buffer.concat(chunks),
      }));
    });
    outgoing.on('error', reject);
    outgoing.end(body);
  });
}

test('forwards login, cookies, redirects, query strings and backend data', async (context) => {
  let receivedHost;
  const backend = await listen(http.createServer(async (incoming, response) => {
    receivedHost = incoming.headers.host;
    if (incoming.method === 'POST' && incoming.url === '/') {
      let body = '';
      for await (const chunk of incoming) body += chunk;
      assert.equal(body, 'username=admin&password=test-password');
      assert.equal(incoming.headers['content-type'], 'application/x-www-form-urlencoded');
      response.writeHead(302, { Location: '/dashboard', 'Set-Cookie': ['session=test; HttpOnly; Path=/'] });
      response.end();
      return;
    }
    if (incoming.headers.cookie !== 'session=test') {
      response.writeHead(302, { Location: '/' });
      response.end();
      return;
    }
    assert.equal(incoming.url, '/admin/postgres-leave-requests?page=2');
    response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
    response.end('<table><tr><td>Leave request from database</td></tr></table>');
  }), context);
  const origin = await listen(createServer({ backendUrl: backend }), context);
  const anonymous = await request(`${origin}/admin/postgres-leave-requests`);
  assert.equal(anonymous.status, 302);
  assert.equal(anonymous.headers.location, '/');

  const login = await request(origin, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'username=admin&password=test-password',
  });
  assert.equal(login.status, 302);
  assert.equal(login.headers.location, '/dashboard');
  assert.deepEqual(login.headers['set-cookie'], ['session=test; HttpOnly; Path=/']);

  const data = await request(`${origin}/admin/postgres-leave-requests?page=2`, {
    headers: { Cookie: 'session=test' },
  });
  assert.equal(data.status, 200);
  assert.equal(data.headers['cache-control'], 'no-store');
  assert.match(data.body.toString(), /Leave request from database/);
  assert.equal(receivedHost, new URL(origin).host);
});

test('streams static assets without changing bytes or content type', async (context) => {
  const asset = Buffer.from([0, 255, 137, 80, 78, 71]);
  const backend = await listen(http.createServer((incoming, response) => {
    assert.equal(incoming.url, '/static/logo.png');
    response.writeHead(200, { 'Content-Type': 'image/png', 'Content-Length': asset.length });
    response.end(asset);
  }), context);
  const origin = await listen(createServer({ backendUrl: backend }), context);
  const result = await request(`${origin}/static/logo.png`);
  assert.equal(result.headers['content-type'], 'image/png');
  assert.deepEqual(result.body, asset);
});

test('passes backend errors through and strips connection-specific headers', async (context) => {
  const backend = await listen(http.createServer((incoming, response) => {
    assert.equal(incoming.headers['x-request-hop'], undefined);
    response.writeHead(503, {
      Connection: 'close, X-Response-Hop',
      'X-Response-Hop': 'private',
      'Content-Type': 'text/plain',
    });
    response.end('Database unavailable');
  }), context);
  const origin = await listen(createServer({ backendUrl: backend }), context);
  const result = await request(origin, {
    headers: { Connection: 'close, X-Request-Hop', 'X-Request-Hop': 'private' },
  });
  assert.equal(result.status, 503);
  assert.equal(result.body.toString(), 'Database unavailable');
  assert.equal(result.headers['x-response-hop'], undefined);
});

test('reports an unavailable backend without leaking connection details', async (context) => {
  const backendServer = http.createServer();
  const backend = await listen(backendServer, context);
  await new Promise((resolve) => backendServer.close(resolve));
  const origin = await listen(createServer({ backendUrl: backend }), context);
  const result = await request(origin);
  assert.equal(result.status, 502);
  assert.equal(result.headers['cache-control'], 'no-store');
  assert.match(result.body.toString(), /Start web\/app.py/);
  assert.ok(!result.body.toString().includes(backend));
});

test('returns a gateway timeout when the backend stalls', async (context) => {
  const backend = await listen(http.createServer(() => {}), context);
  const origin = await listen(createServer({ backendUrl: backend, timeout: 50 }), context);
  const result = await request(origin);
  assert.equal(result.status, 504);
  assert.match(result.body.toString(), /too long/);
});

test('rejects unsupported or credential-bearing backend URLs', () => {
  for (const backendUrl of ['file:///tmp/data', 'http://user:secret@localhost', 'http://localhost/path', 'http://localhost?token=secret']) {
    assert.throws(() => createServer({ backendUrl }), /BACKEND_URL/);
  }
});
