/** Shared intake constants — single source for the 4 fortune wizards. */

export const EARTHLY_BRANCHES = [
  { branch: '子', time: '23-01', hour: '23:00' },
  { branch: '丑', time: '01-03', hour: '01:00' },
  { branch: '寅', time: '03-05', hour: '03:00' },
  { branch: '卯', time: '05-07', hour: '05:00' },
  { branch: '辰', time: '07-09', hour: '07:00' },
  { branch: '巳', time: '09-11', hour: '09:00' },
  { branch: '午', time: '11-13', hour: '11:00' },
  { branch: '未', time: '13-15', hour: '13:00' },
  { branch: '申', time: '15-17', hour: '15:00' },
  { branch: '酉', time: '17-19', hour: '17:00' },
  { branch: '戌', time: '19-21', hour: '19:00' },
  { branch: '亥', time: '21-23', hour: '21:00' },
] as const;

export const GENDER_OPTIONS = [
  { id: 'male', label: 'Male', icon: '♂' },
  { id: 'female', label: 'Female', icon: '♀' },
  { id: 'unknown', label: 'Prefer not to say', icon: '—' },
] as const;

export type GenderId = (typeof GENDER_OPTIONS)[number]['id'];

export interface IntakeProfile {
  birthDate: string;
  birthTime: string | null;
  timeUnknown: boolean;
  gender: string;
}

export const EMPTY_INTAKE_PROFILE: IntakeProfile = {
  birthDate: '',
  birthTime: null,
  timeUnknown: false,
  gender: 'unknown',
};

export function isProfileComplete(p: IntakeProfile | null | undefined): boolean {
  if (!p?.birthDate) return false;
  return Boolean(p.timeUnknown || p.birthTime);
}

export function formatProfileSummary(p: IntakeProfile | null | undefined): string {
  if (!p?.birthDate) return 'Incomplete';
  const time = p.timeUnknown ? 'time unknown' : p.birthTime || '—';
  const gender =
    GENDER_OPTIONS.find((g) => g.id === p.gender)?.label ?? p.gender ?? '—';
  return `${p.birthDate} · ${time} · ${gender}`;
}
