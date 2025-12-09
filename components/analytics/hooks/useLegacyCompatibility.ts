import { REVISION_EVENT_ALIASES } from './useAnalyticsUtils';
import { coerceBoolean, coerceString } from './useDataTransformers';

/*
Function: normalizeLegacyEnvelope — called from useAnalyticsMemoryStream to adapt mixed legacy/lightweight SSE envelopes. Resolves event type aliases, pulls data into a consistent shape, and normalizes revision context (id + lanes) so downstream routing stays stable. Invokes coerceBoolean/coerceString only.
*/
export type LegacyRevisionContext = { id?: string; lanes: string[]; focus?: string };

export type LegacyEventEnvelope = {
  eventType: any;
  eventData: any;
  rawThoughtId?: string;
  isThinkingEvent: boolean;
  isRevisionEvent: boolean;
  revisionContext: LegacyRevisionContext;
  effectiveRevisionId?: string;
  effectiveRevisionLanes: string[];
  fallbackSessionId?: string;
  eventVisibility: string;
};

export const normalizeLegacyEnvelope = (
  data: any,
  currentRevisionContext: LegacyRevisionContext,
): LegacyEventEnvelope => {
  const rawEventType = data.event || data.type;
  const eventType =
    typeof rawEventType === 'string' ? REVISION_EVENT_ALIASES[rawEventType] ?? rawEventType : rawEventType;
  const eventData = data.data || data;
  const rawThoughtId = coerceString(eventData.thought_id ?? data.thought_id);
  const eventVisibility = typeof data.event_type === 'string' ? data.event_type : 'user';
  const isThinkingEvent = eventVisibility === 'thinking';

  const revisionId = coerceString(data.revision_id ?? eventData.revision_id);
  const revisionLanesRaw =
    Array.isArray(data.revision_lanes)
      ? data.revision_lanes
      : Array.isArray(eventData.revision_lanes)
        ? eventData.revision_lanes
        : undefined;
  const normalizedRevisionLanes = Array.isArray(revisionLanesRaw)
    ? (revisionLanesRaw as unknown[])
      .map((lane) => (typeof lane === 'string' ? lane.toLowerCase() : ''))
      .filter((lane): lane is string => lane.length > 0)
    : [];

  const revisionContext = {
    id: revisionId ?? currentRevisionContext.id,
    lanes: normalizedRevisionLanes.length ? normalizedRevisionLanes : currentRevisionContext.lanes,
    focus: currentRevisionContext.focus,
  };

  const revisionFlag = coerceBoolean(data.revision ?? eventData.revision);
  const revisionEventFlag =
    coerceBoolean(data.revision_event ?? eventData.revision_event) ||
    (typeof rawEventType === 'string' && Object.prototype.hasOwnProperty.call(REVISION_EVENT_ALIASES, rawEventType));
  const isRevisionEvent = Boolean(revisionFlag || revisionEventFlag || revisionId);
  const effectiveRevisionId = revisionId ?? currentRevisionContext.id;
  const fallbackSessionId = coerceString(eventData.session_id ?? data.session_id);

  return {
    eventType,
    eventData,
    rawThoughtId,
    isThinkingEvent,
    isRevisionEvent,
    revisionContext,
    effectiveRevisionId,
    effectiveRevisionLanes: revisionContext.lanes ?? [],
    fallbackSessionId,
    eventVisibility,
  };
};

