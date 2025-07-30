import { fetchEventSource } from '@microsoft/fetch-event-source';
import { authService } from './auth';

// Backend-powered Gemini service that replaces frontend SDK
export class BackendGeminiService {
  private backendUrl: string;
  private sessionId: string | null = null;

  constructor(backendUrl: string = 'http://localhost:8000') {
    this.backendUrl = backendUrl;
  }

  private async getHeaders(): Promise<Record<string, string>> {
    const authHeaders = await authService.getAuthHeaders();
    return {
      'Content-Type': 'application/json',
      ...authHeaders
    };
  }

  async createChat(systemInstruction: string): Promise<string | null> {
    try {
      const headers = await this.getHeaders();
      const response = await fetch(`${this.backendUrl}/api/gemini/chat/create`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ system_instruction: systemInstruction }),
      });

      if (!response.ok) {
        console.error('Failed to create Gemini chat session:', response.statusText);
        return null;
      }

      const data = await response.json();
      this.sessionId = data.session_id;
      return this.sessionId;
    } catch (error) {
      console.error('Error creating Gemini chat session:', error);
      return null;
    }
  }

  async sendMessageStream(
    message: string,
    onChunk: (chunk: string) => void,
    onStatus?: (status: string) => void,
    onError?: (error: string) => void,
    onComplete?: () => void
  ): Promise<void> {
    if (!this.sessionId) {
      onError?.('No active chat session');
      return;
    }

    try {
      const authHeaders = await authService.getAuthHeaders();
      await fetchEventSource(
        `${this.backendUrl}/api/gemini/chat/stream?session_id=${this.sessionId}&message=${encodeURIComponent(message)}`,
        {
          method: 'GET',
          headers: {
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
            ...authHeaders
          },
          openWhenHidden: true,
          onmessage(event) {
            try {
              const data = JSON.parse(event.data);

              if (data.type === 'status') {
                onStatus?.(data.message);
              } else if (data.type === 'response') {
                onChunk(data.text);
              } else if (data.type === 'error') {
                onError?.(data.message);
              } else if (data.type === 'done') {
                onComplete?.();
                return;
              }
            } catch (parseError) {
              console.error('Error parsing Gemini stream data:', parseError);
              onError?.('Error parsing response');
            }
          },
          onerror(error) {
            console.error('Gemini stream error:', error);
            onError?.('Failed to connect to Gemini service');
            throw error;
          },
          onclose() {
            onComplete?.();
          },
        }
      );
    } catch (error) {
      console.error('Error setting up Gemini stream:', error);
      onError?.('Failed to connect to Gemini service');
    }
  }

  async sendMessage(message: string): Promise<string | null> {
    if (!this.sessionId) {
      console.error('No active chat session');
      return null;
    }

    try {
      const headers = await this.getHeaders();
      const response = await fetch(`${this.backendUrl}/api/gemini/chat/message`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message,
          session_id: this.sessionId,
        }),
      });

      if (!response.ok) {
        console.error('Failed to send message to Gemini:', response.statusText);
        return null;
      }

      const data = await response.json();
      return data.response;
    } catch (error) {
      console.error('Error sending message to Gemini:', error);
      return null;
    }
  }

  async cleanup(): Promise<void> {
    if (!this.sessionId) return;

    try {
      await fetch(`${this.backendUrl}/api/gemini/chat/${this.sessionId}`, {
        method: 'DELETE',
      });
      this.sessionId = null;
    } catch (error) {
      console.error('Error cleaning up Gemini session:', error);
    }
  }

  getSessionId(): string | null {
    return this.sessionId;
  }
}

// Factory function to create and initialize a backend Gemini service
export const createBackendChat = async (
  systemInstruction: string,
  backendUrl?: string
): Promise<BackendGeminiService | null> => {
  const service = new BackendGeminiService(backendUrl);
  const sessionId = await service.createChat(systemInstruction);
  
  if (!sessionId) {
    console.error('Failed to initialize backend Gemini chat');
    return null;
  }
  
  return service;
};