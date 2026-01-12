// --- Function/Class Map ---
// Function: getOrCreateSessionId
//   Role: Persist a stable session id for A2UI streaming requests.
//   Called from: components/generativeUiDashboard/GenerativeUIPage.tsx.
//   Invokes: localStorage, crypto.randomUUID.
//   Why: Enables backend session-memory features tied to a browser session.
// --- End Function/Class Map ---
/**
 * Session utilities for A2UI streaming.
 */

const SESSION_STORAGE_KEY = 'a2ui_session_id';

export function getOrCreateSessionId(): string {
    try {
        if (typeof window === 'undefined') {
            return 'server-session';
        }

        const existing = window.localStorage.getItem(SESSION_STORAGE_KEY);
        if (existing) {
            return existing;
        }

        const sessionId = window.crypto.randomUUID();
        window.localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
        return sessionId;
    } catch {
        return 'session-unavailable';
    }
}
