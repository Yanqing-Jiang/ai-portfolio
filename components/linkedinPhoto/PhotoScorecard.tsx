import React from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Sparkles, CheckCircle, AlertCircle, Lightbulb, AlertTriangle } from 'lucide-react';

/**
 * PhotoScorecard: Displays AI Quality Scorecard with radial progress indicators.
 * Shows RED for low scores (casual photos) and recommends Executive Suite styles.
 * Called from: Page.tsx after photo analysis completes
 * Why: Powers the "wow factor" feature that positions the tool as an expert consultant.
 */

export interface PhotoScores {
    lighting: number;
    angle: number;
    background: number;
    expression: number;
    outfit?: number;
    overall: number;
}

interface PhotoScorecardProps {
    scores: PhotoScores;
    tips: string[];
    processingMs?: number;
    className?: string;
    onStyleRecommendation?: (styleId: string) => void;
}

const ScoreRing: React.FC<{
    score: number;
    label: string;
    size?: 'sm' | 'lg';
}> = ({ score, label, size = 'sm' }) => {
    const percentage = (score / 10) * 100;
    const circumference = 2 * Math.PI * 40;
    const strokeDashoffset = circumference - (percentage / 100) * circumference;

    // Strict color grading - RED for scores below 6
    const getScoreColor = (s: number) => {
        if (s >= 8) return { stroke: '#10b981', bg: 'bg-emerald-500/20', text: 'text-emerald-400', label: 'Excellent' };
        if (s >= 6) return { stroke: '#D4AF37', bg: 'bg-amber-500/20', text: 'text-amber-400', label: 'Good' };
        if (s >= 4) return { stroke: '#f97316', bg: 'bg-orange-500/20', text: 'text-orange-400', label: 'Fair' };
        return { stroke: '#ef4444', bg: 'bg-red-500/20', text: 'text-red-400', label: 'Poor' };
    };

    const colors = getScoreColor(score);
    const ringSize = size === 'lg' ? 140 : 72;
    const fontSize = size === 'lg' ? 'text-4xl' : 'text-lg';

    return (
        <div className="flex flex-col items-center gap-1.5">
            <div className="relative" style={{ width: ringSize, height: ringSize }}>
                <svg
                    className="transform -rotate-90"
                    width={ringSize}
                    height={ringSize}
                    viewBox="0 0 100 100"
                >
                    {/* Background ring */}
                    <circle
                        cx="50"
                        cy="50"
                        r="40"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="8"
                        className="text-slate-700/50"
                    />
                    {/* Score ring */}
                    <circle
                        cx="50"
                        cy="50"
                        r="40"
                        fill="none"
                        stroke={colors.stroke}
                        strokeWidth="8"
                        strokeLinecap="round"
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        className="transition-all duration-1000 ease-out"
                        style={{
                            filter: `drop-shadow(0 0 8px ${colors.stroke}60)`,
                        }}
                    />
                </svg>
                <div
                    className={cn(
                        'absolute inset-0 flex flex-col items-center justify-center font-bold',
                        colors.text
                    )}
                >
                    <span className={fontSize}>{score}</span>
                    {size === 'lg' && (
                        <span className="text-xs uppercase tracking-wider opacity-80">{colors.label}</span>
                    )}
                </div>
            </div>
            <span className="text-[10px] text-slate-400 uppercase tracking-wider font-medium text-center leading-tight">
                {label}
            </span>
        </div>
    );
};

// Style recommendation cards
const STYLE_RECOMMENDATIONS = [
    {
        id: 'fortune_500',
        name: 'The Fortune 500',
        description: 'Boardroom-ready executive presence',
        gradient: 'from-slate-800 to-slate-900',
        border: 'border-slate-600',
        emoji: '💼',
    },
    {
        id: 'silicon_valley',
        name: 'Silicon Valley Founder',
        description: 'Minimalist tech aesthetic',
        gradient: 'from-slate-700 to-slate-800',
        border: 'border-slate-500',
        emoji: '🚀',
    },
    {
        id: 'creative_director',
        name: 'Creative Director',
        description: 'Bold editorial lighting',
        gradient: 'from-purple-900 to-slate-900',
        border: 'border-purple-700',
        emoji: '🎨',
    },
];

export const PhotoScorecard: React.FC<PhotoScorecardProps> = ({
    scores,
    tips,
    processingMs,
    className,
    onStyleRecommendation,
}) => {
    const needsImprovement = scores.overall < 7;

    const getOverallStatus = (score: number) => {
        if (score >= 8) return { label: 'LinkedIn Ready!', icon: CheckCircle, color: 'text-emerald-400', bgColor: 'bg-emerald-500/20' };
        if (score >= 6) return { label: 'Good Foundation', icon: Lightbulb, color: 'text-amber-400', bgColor: 'bg-amber-500/20' };
        if (score >= 4) return { label: 'Needs Enhancement', icon: AlertCircle, color: 'text-orange-400', bgColor: 'bg-orange-500/20' };
        return { label: 'Casual Photo Detected', icon: AlertTriangle, color: 'text-red-400', bgColor: 'bg-red-500/20' };
    };

    const status = getOverallStatus(scores.overall);
    const StatusIcon = status.icon;

    return (
        <Card
            className={cn(
                'border-2 bg-gradient-to-br from-slate-900/95 to-slate-800/80 backdrop-blur-xl shadow-2xl',
                needsImprovement ? 'border-red-500/50' : 'border-emerald-500/30',
                className
            )}
        >
            <CardContent className="p-5 space-y-5">
                {/* Header with Status */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className={cn(
                            'flex items-center justify-center w-10 h-10 rounded-full',
                            status.bgColor
                        )}>
                            <Sparkles className={cn('w-5 h-5', status.color)} />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-white">
                                Professional Readiness Score
                            </h3>
                            <div className={cn('flex items-center gap-1.5 text-sm font-medium', status.color)}>
                                <StatusIcon className="w-4 h-4" />
                                <span>{status.label}</span>
                            </div>
                        </div>
                    </div>
                    {processingMs && (
                        <span className="text-xs text-slate-500 bg-slate-800/50 px-2 py-1 rounded">
                            {(processingMs / 1000).toFixed(1)}s
                        </span>
                    )}
                </div>

                {/* Main Score */}
                <div className="flex justify-center py-2">
                    <ScoreRing score={scores.overall} label="Overall Score" size="lg" />
                </div>

                {/* Category Scores - Now includes Outfit */}
                <div className="grid grid-cols-5 gap-2">
                    <ScoreRing score={scores.lighting} label="Lighting" />
                    <ScoreRing score={scores.angle} label="Angle" />
                    <ScoreRing score={scores.background} label="Background" />
                    <ScoreRing score={scores.expression} label="Expression" />
                    <ScoreRing score={scores.outfit ?? 5} label="Outfit" />
                </div>

                {/* AI Recommendations */}
                {tips.length > 0 && (
                    <div className="space-y-2 pt-3 border-t border-slate-700/50">
                        <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
                            <Lightbulb className="w-4 h-4 text-amber-400" />
                            <span>AI Recommendations</span>
                        </div>
                        <ul className="space-y-1.5">
                            {tips.map((tip, index) => (
                                <li
                                    key={index}
                                    className="flex items-start gap-2 text-sm text-slate-400"
                                >
                                    {tip.toLowerCase().includes('great') ||
                                        tip.toLowerCase().includes('excellent') ||
                                        tip.toLowerCase().includes('perfect') ? (
                                        <CheckCircle className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
                                    ) : (
                                        <AlertCircle className="w-4 h-4 text-orange-400 mt-0.5 flex-shrink-0" />
                                    )}
                                    <span>{tip}</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* Style Recommendations - ALWAYS show, but more prominent for low scores */}
                <div className={cn(
                    "space-y-3 pt-4 border-t",
                    needsImprovement ? "border-red-500/30" : "border-slate-700/50"
                )}>
                    <div className="text-center">
                        {needsImprovement ? (
                            <>
                                <p className="text-sm font-semibold text-amber-400 mb-1">
                                    ✨ Transform this into a professional headshot
                                </p>
                                <p className="text-xs text-slate-500">
                                    Our AI can dramatically improve your photo with these styles:
                                </p>
                            </>
                        ) : (
                            <>
                                <p className="text-sm font-semibold text-slate-300 mb-1">
                                    🎯 Choose an Executive Suite Style
                                </p>
                                <p className="text-xs text-slate-500">
                                    Elevate your photo even further with our premium presets:
                                </p>
                            </>
                        )}
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                        {STYLE_RECOMMENDATIONS.map((style) => (
                            <button
                                key={style.id}
                                onClick={() => onStyleRecommendation?.(style.id)}
                                className={cn(
                                    'p-2.5 rounded-xl border transition-all duration-200 text-left',
                                    'bg-gradient-to-br hover:scale-[1.02] hover:shadow-lg',
                                    style.gradient,
                                    style.border,
                                    'hover:border-amber-500/50'
                                )}
                            >
                                <div className="text-lg mb-1">{style.emoji}</div>
                                <p className="text-xs font-semibold text-white leading-tight">{style.name}</p>
                                <p className="text-[10px] text-slate-400 mt-0.5 leading-tight">{style.description}</p>
                            </button>
                        ))}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};
