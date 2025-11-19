import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

export interface StylePreset {
  id: string;
  title: string;
  description: string;
  prompt: string;
  gradientFrom: string;
  gradientTo: string;
  expansionMode: 'fixed' | 'expand';
}

export const INITIAL_STYLE_PRESETS: StylePreset[] = [
  {
    id: 'professional',
    title: 'Professional Corporate',
    description: 'Classic business look with neutral tones',
    prompt: 'Professional studio portrait, neutral gray gradient backdrop, navy blazer, confident expression, soft key light.',
    gradientFrom: '#1e293b',
    gradientTo: '#64748b',
    expansionMode: 'fixed',
  },
  {
    id: 'creative',
    title: 'Creative Editorial',
    description: 'Bold and modern with vibrant colors',
    prompt: 'Editorial style headshot with vibrant gel lighting, bold wardrobe accents, magazine-quality retouching.',
    gradientFrom: '#0891b2',
    gradientTo: '#6366f1',
    expansionMode: 'fixed',
  },
  {
    id: 'warm',
    title: 'Warm Approachable',
    description: 'Friendly and inviting atmosphere',
    prompt: 'Warm, approachable portrait with golden-hour tones, soft smile, blurred office backdrop.',
    gradientFrom: '#ea580c',
    gradientTo: '#facc15',
    expansionMode: 'fixed',
  },
  {
    id: 'custom',
    title: 'Custom Style',
    description: 'Write your own prompt',
    prompt: '',
    gradientFrom: '#6b7280',
    gradientTo: '#9ca3af',
    expansionMode: 'expand',
  },
];

interface StylePresetCardProps {
  preset: StylePreset;
  isSelected: boolean;
  onClick: () => void;
  disabled?: boolean;
}

export const StylePresetCard: React.FC<StylePresetCardProps> = ({ preset, isSelected, onClick, disabled }) => {
  return (
    <Card
      className={cn(
        'cursor-pointer transition-all duration-200 hover:shadow-md hover:scale-105',
        isSelected && 'ring-2 ring-primary ring-offset-2',
        disabled && 'pointer-events-none opacity-50'
      )}
      onClick={disabled ? undefined : onClick}
    >
      <CardContent className="p-4">
        <div
          className="w-full h-24 rounded-md mb-3"
          style={{
            background: `linear-gradient(135deg, ${preset.gradientFrom} 0%, ${preset.gradientTo} 100%)`,
          }}
        />
        <h3 className="font-semibold text-sm mb-1">{preset.title}</h3>
        <p className="text-xs text-muted-foreground">{preset.description}</p>
      </CardContent>
    </Card>
  );
};
