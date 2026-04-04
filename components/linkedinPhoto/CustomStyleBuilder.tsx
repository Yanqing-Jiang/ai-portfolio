/**
 * CustomStyleBuilder - Guided builder for Custom Style preset
 *
 * Provides visual card-based interface for selecting:
 * - Clothing style
 * - Expression/vibe
 * - Background
 * - Pose/framing
 *
 * Each parameter has curated preset options with defaults
 */

import React from 'react';
import { StyleParameterCard } from './StyleParameterCard';
import { Shirt, Smile, Image, User } from 'lucide-react';

export interface CustomStyleParams {
  clothing: string | null;
  expression: string | null;
  background: string | null;
  pose: string | null;
}

interface CustomStyleBuilderProps {
  params: CustomStyleParams;
  onChange: (params: CustomStyleParams) => void;
}

// Preset options data
const CLOTHING_OPTIONS = [
  {
    id: 'corporate',
    icon: '👔',
    title: 'Professional Corporate',
    description: 'Navy/charcoal suit, white shirt',
    promptText: 'wearing a professional navy or charcoal suit with crisp white dress shirt',
  },
  {
    id: 'smart-casual',
    icon: '🧥',
    title: 'Smart Casual',
    description: 'Blazer, no tie, softer colors',
    promptText: 'wearing a smart casual blazer without tie, in soft earth tones',
  },
  {
    id: 'creative',
    icon: '🎨',
    title: 'Creative Professional',
    description: 'Unique textures, bold colors',
    promptText: 'wearing creative professional attire with unique textures and thoughtful color choices',
  },
  {
    id: 'minimal',
    icon: '➖',
    title: 'Minimal Clean',
    description: 'Simple solid colors, modern cut',
    promptText: 'wearing minimal clean attire in solid colors with modern tailoring',
  },
];

const EXPRESSION_OPTIONS = [
  {
    id: 'confident',
    icon: '😊',
    title: 'Confident & Approachable',
    description: 'Warm smile, direct gaze',
    promptText: 'with a confident warm smile and approachable direct gaze',
  },
  {
    id: 'serious',
    icon: '😐',
    title: 'Professional & Serious',
    description: 'Neutral, composed',
    promptText: 'with a professional neutral expression, composed and serious',
  },
  {
    id: 'friendly',
    icon: '😄',
    title: 'Friendly & Energetic',
    description: 'Bright smile, engaging',
    promptText: 'with a friendly energetic smile, bright and engaging',
  },
  {
    id: 'calm',
    icon: '🙂',
    title: 'Calm & Trustworthy',
    description: 'Slight smile, relaxed',
    promptText: 'with a calm trustworthy expression, slight smile, relaxed demeanor',
  },
];

const BACKGROUND_OPTIONS = [
  {
    id: 'gradient',
    icon: '🌑',
    title: 'Studio Gradient',
    description: 'Charcoal to gray',
    promptText: 'against a professional studio gradient background from charcoal to light gray',
  },
  {
    id: 'neutral',
    icon: '🟤',
    title: 'Soft Neutral',
    description: 'Warm beige/taupe',
    promptText: 'against a soft neutral background in warm beige or taupe tones',
  },
  {
    id: 'office',
    icon: '🏢',
    title: 'Modern Office',
    description: 'Blurred office setting',
    promptText: 'with a modern office setting softly blurred in the background',
  },
  {
    id: 'white',
    icon: '⬜',
    title: 'Clean White',
    description: 'Pure white seamless',
    promptText: 'against a clean pure white seamless background',
  },
  {
    id: 'deep',
    icon: '🌊',
    title: 'Deep Professional',
    description: 'Navy/teal gradient',
    promptText: 'against a deep professional gradient background in navy or teal tones',
  },
];

const POSE_OPTIONS = [
  {
    id: 'classic',
    icon: '👤',
    title: 'Classic Headshot',
    description: 'Shoulders up, straight-on',
    promptText: 'in a classic headshot pose, shoulders up, facing straight toward camera',
  },
  {
    id: 'three-quarter',
    icon: '🔄',
    title: 'Three-Quarter Turn',
    description: 'Slight angle, dynamic',
    promptText: 'in a three-quarter turn pose, body slightly angled for dynamic composition',
  },
  {
    id: 'relaxed',
    icon: '🤝',
    title: 'Relaxed Stance',
    description: 'Leaning slightly, approachable',
    promptText: 'in a relaxed stance, leaning slightly forward for an approachable feel',
  },
  {
    id: 'executive',
    icon: '✊',
    title: 'Executive',
    description: 'Arms crossed or hands clasped',
    promptText: 'in an executive pose with arms crossed or hands clasped confidently',
  },
];

export const CustomStyleBuilder: React.FC<CustomStyleBuilderProps> = ({
  params,
  onChange,
}) => {
  const handleSelect = (category: keyof CustomStyleParams, id: string) => {
    onChange({
      ...params,
      [category]: params[category] === id ? null : id, // Toggle selection
    });
  };

  return (
    <div className="space-y-5 sm:space-y-8 p-3 sm:p-6 bg-muted/50 rounded-xl border border-border">
      <div className="text-center mb-4">
        <h3 className="text-lg font-semibold text-foreground mb-1">
          Customize Your Professional Headshot
        </h3>
        <p className="text-sm text-muted-foreground">
          Select options below to guide the style (all optional)
        </p>
      </div>

      {/* Clothing Style Section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Shirt className="w-5 h-5 text-muted-foreground" />
          <h4 className="font-semibold text-foreground">Clothing Style</h4>
          {params.clothing && (
            <button
              onClick={() => onChange({ ...params, clothing: null })}
              className="ml-auto text-xs text-blue-600 hover:text-blue-700"
            >
              Clear
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-3">
          {CLOTHING_OPTIONS.map((option) => (
            <StyleParameterCard
              key={option.id}
              icon={option.icon}
              title={option.title}
              description={option.description}
              selected={params.clothing === option.id}
              onClick={() => handleSelect('clothing', option.id)}
            />
          ))}
        </div>
      </div>

      {/* Expression Section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Smile className="w-5 h-5 text-muted-foreground" />
          <h4 className="font-semibold text-foreground">Expression</h4>
          {params.expression && (
            <button
              onClick={() => onChange({ ...params, expression: null })}
              className="ml-auto text-xs text-blue-600 hover:text-blue-700"
            >
              Clear
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-3">
          {EXPRESSION_OPTIONS.map((option) => (
            <StyleParameterCard
              key={option.id}
              icon={option.icon}
              title={option.title}
              description={option.description}
              selected={params.expression === option.id}
              onClick={() => handleSelect('expression', option.id)}
            />
          ))}
        </div>
      </div>

      {/* Background Section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Image className="w-5 h-5 text-muted-foreground" />
          <h4 className="font-semibold text-foreground">Background</h4>
          {params.background && (
            <button
              onClick={() => onChange({ ...params, background: null })}
              className="ml-auto text-xs text-blue-600 hover:text-blue-700"
            >
              Clear
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 sm:gap-3">
          {BACKGROUND_OPTIONS.map((option) => (
            <StyleParameterCard
              key={option.id}
              icon={option.icon}
              title={option.title}
              description={option.description}
              selected={params.background === option.id}
              onClick={() => handleSelect('background', option.id)}
            />
          ))}
        </div>
      </div>

      {/* Pose Section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <User className="w-5 h-5 text-muted-foreground" />
          <h4 className="font-semibold text-foreground">Pose</h4>
          {params.pose && (
            <button
              onClick={() => onChange({ ...params, pose: null })}
              className="ml-auto text-xs text-blue-600 hover:text-blue-700"
            >
              Clear
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-3">
          {POSE_OPTIONS.map((option) => (
            <StyleParameterCard
              key={option.id}
              icon={option.icon}
              title={option.title}
              description={option.description}
              selected={params.pose === option.id}
              onClick={() => handleSelect('pose', option.id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

// Export helper function to construct prompt from selections
export function buildCustomPromptFromParams(params: CustomStyleParams): string {
  const selectedParts: string[] = [];

  // Find selected options and extract prompt text
  if (params.clothing) {
    const option = CLOTHING_OPTIONS.find((o) => o.id === params.clothing);
    if (option) selectedParts.push(option.promptText);
  }

  if (params.expression) {
    const option = EXPRESSION_OPTIONS.find((o) => o.id === params.expression);
    if (option) selectedParts.push(option.promptText);
  }

  if (params.background) {
    const option = BACKGROUND_OPTIONS.find((o) => o.id === params.background);
    if (option) selectedParts.push(option.promptText);
  }

  if (params.pose) {
    const option = POSE_OPTIONS.find((o) => o.id === params.pose);
    if (option) selectedParts.push(option.promptText);
  }

  // Construct final prompt
  if (selectedParts.length === 0) {
    return 'Professional LinkedIn headshot with clean composition, professional attire, natural expression, studio background, and polished appearance.';
  }

  return `Professional LinkedIn headshot ${selectedParts.join(', ')}. High-quality studio lighting, sharp focus, professional photography.`;
}
