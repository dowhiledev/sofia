import fetch from 'node-fetch';
import type { RequestInit, Response } from 'node-fetch';

export interface Message {
  role: string;
  content: string;
}

export interface Summary {
  summary: string[];
}

export interface StepIdentifier {
  step_id: string;
}

export interface FlowContext {
  flow_id: string;
  [key: string]: unknown;
}

export interface FlowState {
  flow_id: string;
  flow_context: FlowContext;
  flow_memory_context: Array<Message | Summary | StepIdentifier>;
}

export interface SessionResponse {
  session_id: string;
  message: Record<string, unknown>;
}

export interface SessionData {
  session_id: string;
  current_step_id: string;
  history: Array<Message | Summary | StepIdentifier>;
  flow_state?: FlowState;
}

export interface ChatRequest {
  user_input?: string;
  session_data?: SessionData;
}

export interface ChatResponse {
  response: Record<string, unknown>;
  tool_output?: string | null;
  session_data: SessionData;
}

export interface AuthConfig {
  type: 'jwt' | 'api_key';
  token: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface NomosClientConfig {
  baseUrl?: string;
  auth?: AuthConfig;
}

export class NomosAuthError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
    this.name = 'NomosAuthError';
  }
}

export class NomosClient {
  private baseUrl: string;
  private auth?: AuthConfig;

  constructor(config: NomosClientConfig | string = {}) {
    if (typeof config === 'string') {
      this.baseUrl = config;
    } else {
      this.baseUrl = config.baseUrl || 'http://localhost:8000';
      this.auth = config.auth;
    }
  }

  /**
   * Set authentication configuration
   */
  setAuth(auth: AuthConfig): void {
    this.auth = auth;
  }

  /**
   * Clear authentication configuration
   */
  clearAuth(): void {
    this.auth = undefined;
  }

  /**
   * Get authorization headers for authenticated requests
   */
  private getAuthHeaders(): Record<string, string> {
    const headers: Record<string, string> = {};

    if (this.auth) {
      headers['Authorization'] = `Bearer ${this.auth.token}`;
    }

    return headers;
  }

  /**
   * Make an authenticated request with proper error handling
   */
  private async makeRequest<T>(url: string, options: RequestInit = {}): Promise<T> {
    const authHeaders = this.getAuthHeaders();
    const headers = {
      ...options.headers,
      ...authHeaders,
    };

    const response: Response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new NomosAuthError('Authentication failed', 401);
      } else if (response.status === 403) {
        throw new NomosAuthError('Access forbidden', 403);
      } else if (response.status === 429) {
        throw new NomosAuthError('Rate limit exceeded', 429);
      } else {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
    }

    return await response.json() as T;
  }

  /**
   * Generate a JWT token (for development/testing purposes only)
   * Note: This endpoint should be disabled in production environments
   */
  async generateToken(payload: Record<string, unknown>): Promise<TokenResponse> {
    const url = new URL('/auth/token', this.baseUrl);
    return this.makeRequest<TokenResponse>(url.toString(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  /**
   * Check server health (no authentication required)
   */
  async healthCheck(): Promise<{ status: string; timestamp: number }> {
    const url = new URL('/health', this.baseUrl);
    const response = await fetch(url.toString());
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json() as { status: string; timestamp: number };
  }

  async createSession(initiate = false): Promise<SessionResponse> {
    const url = new URL('/session', this.baseUrl);
    if (initiate) url.searchParams.set('initiate', 'true');
    return this.makeRequest<SessionResponse>(url.toString(), { method: 'POST' });
  }

  async sendMessage(sessionId: string, message: string): Promise<SessionResponse> {
    const url = new URL(`/session/${sessionId}/message`, this.baseUrl);
    return this.makeRequest<SessionResponse>(url.toString(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: message }),
    });
  }

  async endSession(sessionId: string): Promise<{ message: string }> {
    const url = new URL(`/session/${sessionId}`, this.baseUrl);
    return this.makeRequest<{ message: string }>(url.toString(), { method: 'DELETE' });
  }

  async getSessionHistory(sessionId: string): Promise<{ session_id: string; history: Array<Message | Summary | StepIdentifier> }> {
    const url = new URL(`/session/${sessionId}/history`, this.baseUrl);
    return this.makeRequest<{ session_id: string; history: Array<Message | Summary | StepIdentifier> }>(url.toString());
  }

  async chat(request: ChatRequest, verbose = false): Promise<ChatResponse> {
    const url = new URL('/chat', this.baseUrl);
    if (verbose) url.searchParams.set('verbose', 'true');
    return this.makeRequest<ChatResponse>(url.toString(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
  }
}
