/**
 * Outlook selector — turns the generated future guidance into compact cards.
 *
 * Source of truth: `narrative.yearPredictions` (the writer's dated actions).
 * Ages, possible events, risks and alternatives come from the retained
 * `harness.brief.findings` and are only attached when a finding's validated
 * calendar window covers the year. Nothing here derives an age, a year or a
 * probability that the backend did not already supply.
 */

import type { FortuneDataModel, FortuneFinding, YearPrediction } from '../../lib/fortuneTypes';

export interface OutlookStep {
  year: number;
  text: string;
}

export interface OutlookEntry {
  id: string;
  /** Emoji from the matching generated insight, when there is one. */
  icon?: string;
  /** "2027" or "2028–2029" — always a window the backend supplied. */
  yearLabel: string;
  /** "Age 38–39", optionally prefixed with the person, when the brief has it. */
  ageLabel?: string;
  /** Finding topic without its year prefix. */
  title?: string;
  /** First sentence of the finding's opportunity — the possible event. */
  possible?: string;
  risk?: string;
  alternative?: string;
  steps: OutlookStep[];
  /** Mean interpretive support of the member years, 0–1. */
  support: number;
}

export interface SupportBand {
  label: string;
  percent: number;
}

/** Interpretive support, not a probability. Wording is deliberate. */
export function supportBand(support: number): SupportBand {
  const percent = Math.round(Math.min(Math.max(support, 0), 1) * 100);
  if (percent >= 80) return { label: 'Strong support', percent };
  if (percent >= 65) return { label: 'Moderate support', percent };
  return { label: 'Limited support', percent };
}

export const SUPPORT_FOOTNOTE =
  'Support is interpretive, not a probability. Ages show birthdays reached in these years.';

const YEAR_PREFIX = /^\s*\d{4}(\s*[–—-]\s*\d{4})?\s*[:：]\s*/;

function stripYearPrefix(topic: string): string {
  const text = topic.replace(YEAR_PREFIX, '').trim();
  if (!text) return topic.trim();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function firstSentence(text: string | undefined): string | undefined {
  const value = (text || '').trim();
  if (!value) return undefined;
  const match = value.match(/^[^.!?]+[.!?]/);
  return (match ? match[0] : value).trim();
}

function ageLabel(finding: FortuneFinding, fromYear: number, toYear: number, personLabel?: string): string | undefined {
  const ages = finding.age_at_birthday;
  if (!ages || ages.length !== 2) return undefined;
  // A prediction may cover only part of the finding window. Use supplied
  // endpoint ages only; never attach its full age range to a shorter year span.
  const from = fromYear === finding.start_year ? ages[0] : fromYear === finding.end_year ? ages[1] : undefined;
  const to = toYear === finding.end_year ? ages[1] : toYear === finding.start_year ? ages[0] : undefined;
  if (!Number.isFinite(from) || !Number.isFinite(to)) return undefined;
  const range = from === to ? `${from}` : `${from}–${to}`;
  return personLabel ? `${personLabel} age ${range}` : `Age ${range}`;
}

function findingForYear(findings: FortuneFinding[], year: number): FortuneFinding | undefined {
  return findings.find(
    (finding) =>
      typeof finding.start_year === 'number' &&
      typeof finding.end_year === 'number' &&
      year >= finding.start_year &&
      year <= finding.end_year,
  );
}

export interface BuildOutlookOptions {
  /** Compatibility labels whose birthday ages these are. */
  personLabel?: string;
  /** Cap the rendered windows; the rest stay in the explorer. */
  limit?: number;
}

/**
 * Group the year predictions into the finding windows that support them, so a
 * two-year finding renders as one card with the brief's own age range.
 */
export function buildOutlook(
  dataModel: FortuneDataModel | null | undefined,
  options: BuildOutlookOptions = {},
): OutlookEntry[] {
  const predictions = (dataModel?.narrative?.yearPredictions || []) as YearPrediction[];
  if (predictions.length === 0) return [];
  const findings = (dataModel?.harness?.brief?.findings || []) as FortuneFinding[];
  const insights = dataModel?.narrative?.insights || [];

  const ordered = [...predictions]
    .filter((item) => Number.isFinite(item.year))
    .sort((a, b) => a.year - b.year);

  const entries: OutlookEntry[] = [];
  const groups: Array<{ finding?: FortuneFinding; items: YearPrediction[] }> = [];

  for (const item of ordered) {
    const finding = findingForYear(findings, item.year);
    const last = groups[groups.length - 1];
    if (last && finding && last.finding === finding) last.items.push(item);
    else groups.push({ finding, items: [item] });
  }

  for (const group of groups) {
    const years = group.items.map((item) => item.year);
    const from = years[0];
    const to = years[years.length - 1];
    const supports = group.items
      .map((item) => (typeof item.confidence === 'number' ? item.confidence : 0))
      .filter((value) => value > 0);
    // The writer's insights cite the same evidence paths as its year
    // predictions; reuse that link for an icon and a title where the brief
    // has no dated finding of its own.
    const refs = new Set(group.items.flatMap((item) => item.evidenceRefs || []));
    const insight = insights.find((item) => (item.citations || []).some((ref) => refs.has(ref)));
    entries.push({
      id: `outlook-${from}-${to}`,
      icon: insight?.icon && insight.icon.length <= 4 ? insight.icon : undefined,
      yearLabel: from === to ? `${from}` : `${from}–${to}`,
      ageLabel: group.finding ? ageLabel(group.finding, from, to, options.personLabel) : undefined,
      title: group.finding ? stripYearPrefix(group.finding.topic) : insight?.tagline?.trim(),
      possible: group.finding ? firstSentence(group.finding.opportunity) : undefined,
      risk: group.finding?.risk?.trim() || undefined,
      alternative: group.finding?.alternative?.trim() || undefined,
      steps: group.items.map((item) => ({ year: item.year, text: item.prediction })),
      support: supports.length
        ? supports.reduce((sum, value) => sum + value, 0) / supports.length
        : 0,
    });
  }

  return options.limit ? entries.slice(0, options.limit) : entries;
}
