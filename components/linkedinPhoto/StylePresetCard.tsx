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
}

export const STYLE_PRESETS: StylePreset[] = [
  {
    id: 'professional',
    title: 'Professional Corporate',
    description: 'Classic business look with neutral tones',
    prompt: 'professional business attire, charcoal blazer over crisp white shirt, soft studio lighting with gradient backdrop transitioning from light gray to white, confident and approachable expression',
    gradientFrom: '#1e293b',
    gradientTo: '#64748b',
  },
  {
    id: 'creative',
    title: 'Creative Editorial',
    description: 'Bold and modern with vibrant colors',
    prompt: 'contemporary professional style, jewel-toned backdrop with rich blues and teals, editorial lighting with dramatic contrast, modern blazer, confident creative professional vibe',
    gradientFrom: '#0891b2',
    gradientTo: '#6366f1',
  },
  {
    id: 'warm',
    title: 'Warm Approachable',
    description: 'Friendly and inviting atmosphere',
    prompt: 'approachable professional setting, warm natural lighting, soft earth-toned backdrop with subtle texture, smart casual blazer, genuine welcoming smile, relaxed yet polished demeanor',
    gradientFrom: '#ea580c',
    gradientTo: '#facc15',
  },
  {
    id: 'custom',
    title: 'Custom Style',
    description: 'Write your own prompt',
    prompt: '',
    gradientFrom: '#6b7280',
    gradientTo: '#9ca3af',
  },
];

interface StylePresetCardProps {
  preset: StylePreset;
  isSelected: boolean;
  onClick: () => void;
}

export const StylePresetCard: React.FC<StylePresetCardProps> = ({ preset, isSelected, onClick }) => {
  return (
    <Card
      className={cn(
        'cursor-pointer transition-all duration-200 hover:shadow-md hover:scale-105',
        isSelected && 'ring-2 ring-primary ring-offset-2'
      )}
      onClick={onClick}
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
