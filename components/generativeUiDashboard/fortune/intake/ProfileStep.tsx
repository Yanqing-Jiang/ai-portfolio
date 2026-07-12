/**
 * Shared birth-profile editor used by all 4 fortune intake wizards.
 * Preserves existing markup patterns (BirthdayScrollPicker + earthly-branch
 * time pills + gender). Accent can be an rgb triple string ("234, 179, 8")
 * or a CSS color for selected state.
 */
import React from 'react';
import { BirthdayScrollPicker } from '../../BirthdayScrollPicker';
import {
  EARTHLY_BRANCHES,
  GENDER_OPTIONS,
  type IntakeProfile,
} from './constants';

export interface ProfileStepProps {
  value: IntakeProfile;
  onChange: (next: IntakeProfile) => void;
  /** RGB triple like "244, 63, 94" — preferred for LuckyDay-style accents. */
  accentRgb?: string;
  /** Direct CSS colors when accentRgb is not used (compatibility A/B). */
  accentColor?: string;
  accentBg?: string;
  accentBorder?: string;
  /** Optional gender label hint (compatibility shows "(for luck cycle)"). */
  genderHint?: string;
  timeUnknownLabel?: string;
}

export const ProfileStep: React.FC<ProfileStepProps> = ({
  value,
  onChange,
  accentRgb = '212, 175, 55',
  accentColor,
  accentBg,
  accentBorder,
  genderHint,
  timeUnknownLabel = "I don't know the birth time",
}) => {
  const selectedBg = accentBg ?? `rgba(${accentRgb}, 0.9)`;
  const selectedBorder = accentBorder ?? `1px solid rgba(${accentRgb}, 1)`;
  const selectedColor = accentColor ?? '#fff';
  const softSelectedBg = accentBg ?? `rgba(${accentRgb}, 0.14)`;
  const softSelectedBorder = accentBorder ?? `1px solid rgba(${accentRgb}, 0.55)`;
  const softSelectedColor = accentColor ?? `rgb(${accentRgb})`;
  // When CSS color props are provided (compat), use soft selected styling;
  // when only rgb triple is provided (lucky-day/luck/wish), use solid fill.
  const useSoft = Boolean(accentColor || accentBg || accentBorder);

  return (
    <div className="space-y-4">
      <div>
        <label className="mb-1.5 block text-sm font-medium text-slate-300">Birthday</label>
        <BirthdayScrollPicker
          value={value.birthDate}
          onChange={(d) => onChange({ ...value, birthDate: d })}
        />
      </div>

      <div>
        <label className="mb-1.5 block text-sm font-medium text-slate-300">Birth Time</label>
        <div className="grid grid-cols-4 gap-1.5 sm:grid-cols-6">
          {EARTHLY_BRANCHES.map((eb) => {
            const selected = value.birthTime === eb.hour && !value.timeUnknown;
            return (
              <button
                key={eb.branch}
                type="button"
                aria-pressed={selected}
                aria-label={`${eb.branch} ${eb.time}`}
                className="flex min-h-[44px] flex-col items-center justify-center rounded-lg px-1 py-1.5 text-center transition-colors"
                style={{
                  background: selected
                    ? useSoft
                      ? softSelectedBg
                      : selectedBg
                    : 'rgba(148, 163, 184, 0.08)',
                  border: selected
                    ? useSoft
                      ? softSelectedBorder
                      : selectedBorder
                    : '1px solid rgba(148, 163, 184, 0.15)',
                  color: selected
                    ? useSoft
                      ? softSelectedColor
                      : selectedColor
                    : '#cbd5e1',
                }}
                onClick={() =>
                  onChange({
                    ...value,
                    birthTime: eb.hour,
                    timeUnknown: false,
                  })
                }
              >
                <span
                  className="text-base leading-none"
                  style={{ fontFamily: 'var(--ming-font-chinese)' }}
                >
                  {eb.branch}
                </span>
                <span className="mt-0.5 text-[10px] opacity-60">{eb.time}</span>
              </button>
            );
          })}
        </div>
        <button
          type="button"
          aria-pressed={value.timeUnknown}
          className="mt-2 w-full min-h-[44px] rounded-lg px-3 py-2 text-sm transition-colors"
          style={{
            background: value.timeUnknown
              ? 'rgba(148, 163, 184, 0.2)'
              : 'rgba(148, 163, 184, 0.06)',
            border: value.timeUnknown
              ? '1px solid rgba(148, 163, 184, 0.4)'
              : '1px solid rgba(148, 163, 184, 0.1)',
            color: '#94a3b8',
          }}
          onClick={() =>
            onChange({
              ...value,
              timeUnknown: !value.timeUnknown,
              birthTime: value.timeUnknown ? value.birthTime : null,
            })
          }
        >
          {value.timeUnknown ? '✓ Birth time unknown' : timeUnknownLabel}
        </button>
      </div>

      <div>
        <label className="mb-1.5 block text-sm font-medium text-slate-300">
          Gender
          {genderHint ? (
            <span className="font-normal text-slate-500"> {genderHint}</span>
          ) : null}
        </label>
        <div className="grid grid-cols-3 gap-1.5">
          {GENDER_OPTIONS.map((g) => {
            const selected = value.gender === g.id;
            return (
              <button
                key={g.id}
                type="button"
                aria-pressed={selected}
                className="flex min-h-[44px] items-center justify-center gap-1.5 rounded-lg px-2 py-2 text-sm transition-colors"
                style={{
                  background: selected
                    ? useSoft
                      ? softSelectedBg
                      : selectedBg
                    : 'rgba(148, 163, 184, 0.08)',
                  border: selected
                    ? useSoft
                      ? softSelectedBorder
                      : selectedBorder
                    : '1px solid rgba(148, 163, 184, 0.15)',
                  color: selected
                    ? useSoft
                      ? softSelectedColor
                      : selectedColor
                    : '#cbd5e1',
                }}
                onClick={() => onChange({ ...value, gender: g.id })}
              >
                <span className="text-base leading-none">{g.icon}</span>
                <span className="text-xs font-medium">{g.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
