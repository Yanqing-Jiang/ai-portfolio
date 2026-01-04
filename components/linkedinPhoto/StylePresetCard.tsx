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
    id: 'fortune_500',
    title: 'The Fortune 500',
    description: 'Boardroom-ready executive presence',
    prompt: 'The Fortune 500: Boardroom, window-lit, navy suit, professional corporate.',
    gradientFrom: '#0B1120',
    gradientTo: '#1e3a5f',
    expansionMode: 'fixed',
  },
  {
    id: 'silicon_valley',
    title: 'The Silicon Valley Founder',
    description: 'Minimalist tech-founder aesthetic',
    prompt: 'The Silicon Valley Founder: Grey hoodie, blurred tech-office, innovative approachable.',
    gradientFrom: '#1a1a2e',
    gradientTo: '#4a4a6a',
    expansionMode: 'fixed',
  },
  {
    id: 'creative_director',
    title: 'The Creative Director',
    description: 'Bold editorial studio lighting',
    prompt: 'The Creative Director: Contrast-heavy, editorial studio lighting, artistic.',
    gradientFrom: '#2d1b4e',
    gradientTo: '#6b3fa0',
    expansionMode: 'fixed',
  },
  {
    id: 'custom',
    title: 'Custom Style',
    description: 'Build your own look',
    prompt: '',
    gradientFrom: '#D4AF37',
    gradientTo: '#b8860b',
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
