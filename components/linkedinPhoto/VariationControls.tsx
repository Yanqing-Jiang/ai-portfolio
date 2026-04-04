import React, { useMemo, useState } from 'react';
import { Wand2 } from 'lucide-react';

import { Button } from '@/components/ui/button';

export interface VariationRequestOptions {
  background: string;
  expression: string;
  pose: string;
  prop: string;
}

interface VariationControlsProps {
  disabled?: boolean;
  isSubmitting?: boolean;
  /** Use 'embedded' when wrapped in an external container (e.g. <details>) to avoid double-box */
  variant?: 'default' | 'embedded';
  onCreateVariation: (options: VariationRequestOptions) => Promise<void> | void;
}

const BACKGROUND_OPTIONS = [
  { value: 'original', label: 'Keep current background' },
  { value: 'charcoal gradient backdrop with smooth falloff', label: 'Charcoal gradient' },
  { value: 'soft silver seamless backdrop with gentle falloff', label: 'Soft silver' },
  { value: 'warm taupe seamless backdrop with subtle texture', label: 'Warm taupe' },
  { value: 'deep teal wash with a subtle vignette', label: 'Deep teal wash' },
];

const EXPRESSION_OPTIONS = [
  { value: 'original', label: 'Keep primary expression' },
  { value: 'confident smile with relaxed jaw and bright eyes', label: 'Confident smile' },
  { value: 'calm neutral confidence with softened gaze', label: 'Calm neutral' },
  { value: 'approachable grin with subtle laugh lines', label: 'Approachable grin' },
];

const POSE_OPTIONS = [
  { value: 'original', label: 'Keep current pose' },
  { value: 'three-quarter stance with relaxed shoulders', label: 'Three-quarter stance' },
  { value: 'head-and-shoulders leaning slightly toward camera', label: 'Lean forward' },
  { value: 'arms crossed at mid-chest with relaxed hands', label: 'Arms crossed' },
  { value: 'hands gently clasped at waist, body angled left', label: 'Hands clasped' },
];

const PROP_OPTIONS = [
  { value: 'none', label: 'No additional prop' },
  { value: 'holding a tablet at waist height', label: 'Tablet in hand' },
  { value: 'holding a coffee mug close to torso', label: 'Coffee mug' },
  { value: 'holding a slim notebook and pen at chest level', label: 'Notebook and pen' },
];

export const VariationControls: React.FC<VariationControlsProps> = ({
  disabled = false,
  isSubmitting = false,
  variant = 'default',
  onCreateVariation,
}) => {
  const [background, setBackground] = useState<string>('original');
  const [expression, setExpression] = useState<string>('original');
  const [pose, setPose] = useState<string>('original');
  const [prop, setProp] = useState<string>('none');

  const summaryText = useMemo(() => {
    const parts: string[] = [];
    if (background !== 'original') {
      parts.push(`Switch background to ${BACKGROUND_OPTIONS.find((opt) => opt.value === background)?.label?.toLowerCase()}.`);
    }
    if (expression !== 'original') {
      parts.push(`Guide expression toward ${EXPRESSION_OPTIONS.find((opt) => opt.value === expression)?.label?.toLowerCase()}.`);
    }
    if (pose !== 'original') {
      parts.push(`Adjust pose for ${POSE_OPTIONS.find((opt) => opt.value === pose)?.label?.toLowerCase()}.`);
    }
    if (prop !== 'none') {
      parts.push(`Introduce ${PROP_OPTIONS.find((opt) => opt.value === prop)?.label?.toLowerCase()}.`);
    }

    if (parts.length === 0) {
      return 'Refresh this portrait subtly while preserving lighting balance, wardrobe, and identity.';
    }

    return parts.join(' ');
  }, [background, expression, pose, prop]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (disabled || isSubmitting) {
      return;
    }

    await onCreateVariation({
      background,
      expression,
      pose,
      prop,
    });
  };

  const isControlDisabled = disabled || isSubmitting;

  return (
    <div className={variant === 'embedded' ? 'p-0' : 'rounded-2xl border border-border/40 bg-secondary/40 p-6 shadow-inner shadow-black/30'}>
      {variant !== 'embedded' && (
        <div className="flex items-start gap-3 text-foreground">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/15 text-primary">
            <Wand2 className="h-5 w-5" />
          </div>
          <div className="space-y-1">
            <p className="text-base font-semibold">Guided Variation Builder</p>
            <p className="text-sm text-muted-foreground">
              Iterate like a creative director—tweak the background, expression, pose, or props to request a new
              single portrait from the latest prompt.
            </p>
          </div>
        </div>
      )}

      <form className={variant === 'embedded' ? 'space-y-6' : 'mt-6 space-y-6'} onSubmit={handleSubmit}>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="space-y-2 text-sm">
            <span className="font-medium text-muted-foreground">Background</span>
            <select
              className="w-full rounded-lg border border-border/50 bg-background/80 px-3 py-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/60 disabled:cursor-not-allowed disabled:opacity-60"
              value={background}
              onChange={(event) => setBackground(event.target.value)}
              disabled={isControlDisabled}
            >
              {BACKGROUND_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2 text-sm">
            <span className="font-medium text-muted-foreground">Facial Expression</span>
            <select
              className="w-full rounded-lg border border-border/50 bg-background/80 px-3 py-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/60 disabled:cursor-not-allowed disabled:opacity-60"
              value={expression}
              onChange={(event) => setExpression(event.target.value)}
              disabled={isControlDisabled}
            >
              {EXPRESSION_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2 text-sm">
            <span className="font-medium text-muted-foreground">Pose</span>
            <select
              className="w-full rounded-lg border border-border/50 bg-background/80 px-3 py-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/60 disabled:cursor-not-allowed disabled:opacity-60"
              value={pose}
              onChange={(event) => setPose(event.target.value)}
              disabled={isControlDisabled}
            >
              {POSE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2 text-sm">
            <span className="font-medium text-muted-foreground">Prop or Object</span>
            <select
              className="w-full rounded-lg border border-border/50 bg-background/80 px-3 py-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/60 disabled:cursor-not-allowed disabled:opacity-60"
              value={prop}
              onChange={(event) => setProp(event.target.value)}
              disabled={isControlDisabled}
            >
              {PROP_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {summaryText}
          </p>
          <Button
            type="submit"
            className="w-full h-12 text-base font-semibold"
            disabled={isControlDisabled}
          >
            {isSubmitting ? 'Applying adjustments…' : 'Add Guided Variation'}
          </Button>
        </div>
      </form>
    </div>
  );
};

export default VariationControls;
