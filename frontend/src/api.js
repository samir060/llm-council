/**
 * API client for the LLM Council backend.
 */

const configuredApiBase = import.meta.env.VITE_API_URL;
const configuredApiHost = import.meta.env.VITE_API_HOST;

const API_BASE = configuredApiBase
  ? configuredApiBase.replace(/\/$/, '')
  : configuredApiHost
    ? `https://${configuredApiHost.replace(/\/$/, '')}`
    : 'http://localhost:8001';

const KEY_STORAGE = 'llm_council_openrouter_key';

function getStoredKey() {
  return (localStorage.getItem(KEY_STORAGE) || '').trim();
}

function authHeaders() {
  const key = getStoredKey();
  return key ? { 'X-OpenRouter-Key': key } : {};
}

export const api = {
  getOpenRouterKey() {
    return getStoredKey();
  },

  setOpenRouterKey(key) {
    const clean = (key || '').trim();
    if (clean) localStorage.setItem(KEY_STORAGE, clean);
    else localStorage.removeItem(KEY_STORAGE);
  },

  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`);
    if (!response.ok) throw new Error('Failed to list conversations');
    return response.json();
  },

  async createConversation() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (!response.ok) throw new Error('Failed to create conversation');
    return response.json();
  },

  async getConversation(conversationId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}`);
    if (!response.ok) throw new Error('Failed to get conversation');
    return response.json();
  },

  async sendMessage(conversationId, content) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify({ content }),
      }
    );
    if (!response.ok) throw new Error('Failed to send message');
    return response.json();
  },

  async sendMessageStream(conversationId, content, onEvent) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify({ content }),
      }
    );

    if (!response.ok) throw new Error('Failed to send message');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffered = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffered += decoder.decode(value, { stream: true });
      const lines = buffered.split('\n');
      buffered = lines.pop() ?? '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }

    const tail = buffered.trim();
    if (tail.startsWith('data: ')) {
      try {
        const event = JSON.parse(tail.slice(6));
        onEvent(event.type, event);
      } catch (e) {
        console.error('Failed to parse final SSE event:', e);
      }
    }
  },
};
