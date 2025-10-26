const toTitleCase = (input: string) =>
  input
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');

const buildClassificationMessage = (payload: any): string | undefined => {
  if (!payload || typeof payload !== 'object') {
    return undefined;
  }

  const decline =
    typeof (payload as any).polite_decline_message === 'string'
      ? (payload as any).polite_decline_message.trim()
      : '';
  const rephrase =
    typeof (payload as any).suggested_rephrase === 'string'
      ? (payload as any).suggested_rephrase.trim()
      : '';
  const topic =
    typeof (payload as any).topic_category === 'string'
      ? toTitleCase((payload as any).topic_category.trim())
      : '';
  const confidenceValue =
    typeof (payload as any).confidence === 'number' && Number.isFinite((payload as any).confidence)
      ? Math.round((payload as any).confidence * 100)
      : undefined;
  const flaggedFinancial =
    typeof (payload as any).is_financial_query === 'boolean'
      ? (payload as any).is_financial_query
      : undefined;

  const fragments: string[] = [];

  if (decline) {
    fragments.push(decline.endsWith('.') ? decline : `${decline}.`);
  }
  if (rephrase) {
    const text = rephrase.endsWith('.') ? rephrase : `${rephrase}.`;
    fragments.push(`Suggested rephrase: ${text}`);
  }

  const meta: string[] = [];

  if (topic) {
    meta.push(topic);
  }
  if (flaggedFinancial === true) {
    meta.push('Financial analytics query');
  } else if (flaggedFinancial === false) {
    meta.push('Outside financial analytics');
  }
  if (confidenceValue !== undefined) {
    meta.push(`${confidenceValue}% confidence`);
  }

  if (!fragments.length && meta.length) {
    fragments.push(`${meta.join(', ')}.`);
  } else if (meta.length) {
    fragments.push(`(${meta.join(', ')})`);
  }

  if (!fragments.length) {
    const serialized = (() => {
      try {
        return JSON.stringify(payload);
      } catch {
        return '';
      }
    })();
    return serialized || undefined;
  }

  return fragments.join(' ').replace(/\s+/g, ' ').trim();
};

export const sanitizeStructuredText = (input?: string): string | undefined => {
  if (typeof input !== 'string') {
    return undefined;
  }
  const trimmed = input.trim();
  if (!trimmed) {
    return undefined;
  }
  if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
    try {
      const parsed = JSON.parse(trimmed);
      const message = buildClassificationMessage(parsed);
      if (message) {
        return message;
      }
    } catch {
      // fall back to original text when parsing fails
    }
  }
  return input;
};

export const sanitizeStructuredList = (entries?: string[]): string[] | undefined => {
  if (!Array.isArray(entries) || entries.length === 0) {
    return undefined;
  }
  const sanitized = entries
    .map((entry) => sanitizeStructuredText(entry))
    .filter((entry): entry is string => Boolean(entry && entry.trim().length));
  return sanitized.length ? sanitized : undefined;
};
