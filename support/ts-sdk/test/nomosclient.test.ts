import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import nock, { type DataMatcherMap } from 'nock';
import { NomosClient, ChatRequest, ChatResponse, SessionResponse, NomosAuthError, AuthConfig } from '../src/index.js';

describe('NomosClient', () => {
  const base = 'http://localhost:8000';
  let client: NomosClient;

  beforeEach(() => {
    client = new NomosClient(base);
    nock.cleanAll();
  });

  afterEach(() => {
    nock.cleanAll();
  });

  describe('Basic functionality', () => {
    it('createSession sends proper request', async () => {
      const resp: SessionResponse = { session_id: '1', message: { ok: true } };
      nock(base).post('/session').reply(200, resp);
      const result = await client.createSession();
      expect(result).toEqual(resp);
    });

    it('chat sends request body', async () => {
      const req: ChatRequest = { user_input: 'hi' };
      const resp: ChatResponse = {
        response: { action: 'answer', response: 'hello' },
        tool_output: null,
        session_data: { session_id: '1', current_step_id: 'start', history: [] }
      };
      nock(base).post('/chat', req as unknown as DataMatcherMap).reply(200, resp);
      const result = await client.chat(req);
      expect(result).toEqual(resp);
    });

    it('sendMessage posts message content', async () => {
      const resp: SessionResponse = { session_id: '1', message: { ok: true } };
      nock(base)
        .post('/session/1/message', { content: 'hello' } as unknown as DataMatcherMap)
        .reply(200, resp);
      const result = await client.sendMessage('1', 'hello');
      expect(result).toEqual(resp);
    });

    it('endSession deletes session', async () => {
      const resp = { message: 'ended' };
      nock(base).delete('/session/1').reply(200, resp);
      const result = await client.endSession('1');
      expect(result).toEqual(resp);
    });

    it('getSessionHistory returns history', async () => {
      const resp = { session_id: '1', history: [{ role: 'user', content: 'hi' }] };
      nock(base).get('/session/1/history').reply(200, resp);
      const result = await client.getSessionHistory('1');
      expect(result).toEqual(resp);
    });

    it('healthCheck returns server status', async () => {
      const resp = { status: 'healthy', timestamp: 1234567890 };
      nock(base).get('/health').reply(200, resp);
      const result = await client.healthCheck();
      expect(result).toEqual(resp);
    });
  });

  describe('Authentication', () => {
    it('initializes with auth config object', () => {
      const authConfig: AuthConfig = { type: 'jwt', token: 'test-token' };
      const authClient = new NomosClient({
        baseUrl: base,
        auth: authConfig
      });
      expect(authClient).toBeDefined();
    });

    it('sends Authorization header with JWT auth', async () => {
      const authConfig: AuthConfig = { type: 'jwt', token: 'test-jwt-token' };
      client.setAuth(authConfig);

      const resp: SessionResponse = { session_id: '1', message: { ok: true } };
      nock(base)
        .post('/session')
        .matchHeader('Authorization', 'Bearer test-jwt-token')
        .reply(200, resp);

      const result = await client.createSession();
      expect(result).toEqual(resp);
    });

    it('sends Authorization header with API key auth', async () => {
      const authConfig: AuthConfig = { type: 'api_key', token: 'test-api-key' };
      client.setAuth(authConfig);

      const resp: SessionResponse = { session_id: '1', message: { ok: true } };
      nock(base)
        .post('/session')
        .matchHeader('Authorization', 'Bearer test-api-key')
        .reply(200, resp);

      const result = await client.createSession();
      expect(result).toEqual(resp);
    });

    it('throws NomosAuthError on 401 response', async () => {
      const scope = nock(base).post('/session').reply(401, { detail: 'Authentication required' });

      await expect(client.createSession()).rejects.toThrow(NomosAuthError);
      expect(scope.isDone()).toBe(true);
    });

    it('throws NomosAuthError on 403 response', async () => {
      const scope = nock(base).post('/session').reply(403, { detail: 'Access forbidden' });

      await expect(client.createSession()).rejects.toThrow(NomosAuthError);
      expect(scope.isDone()).toBe(true);
    });

    it('throws NomosAuthError on 429 response', async () => {
      const scope = nock(base).post('/session').reply(429, { detail: 'Rate limit exceeded' });

      await expect(client.createSession()).rejects.toThrow(NomosAuthError);
      expect(scope.isDone()).toBe(true);
    });

    it('clears auth when clearAuth is called', async () => {
      const authConfig: AuthConfig = { type: 'jwt', token: 'test-token' };
      client.setAuth(authConfig);
      client.clearAuth();

      const resp: SessionResponse = { session_id: '1', message: { ok: true } };
      nock(base)
        .post('/session')
        .matchHeader('Authorization', (val) => val === undefined)
        .reply(200, resp);

      const result = await client.createSession();
      expect(result).toEqual(resp);
    });

    it('generates JWT token for development', async () => {
      const tokenResp = { access_token: 'generated-token', token_type: 'bearer' };
      nock(base)
        .post('/auth/token', { user_id: 'test' } as unknown as DataMatcherMap)
        .reply(200, tokenResp);

      const result = await client.generateToken({ user_id: 'test' });
      expect(result).toEqual(tokenResp);
    });
  });

  describe('Chat with verbose option', () => {
    it('chat sends verbose parameter when true', async () => {
      const req: ChatRequest = { user_input: 'hi' };
      const resp: ChatResponse = {
        response: { action: 'answer', response: 'hello' },
        tool_output: 'debug info',
        session_data: { session_id: '1', current_step_id: 'start', history: [] }
      };
      nock(base)
        .post('/chat?verbose=true', req as unknown as DataMatcherMap)
        .reply(200, resp);

      const result = await client.chat(req, true);
      expect(result).toEqual(resp);
    });
  });
});
