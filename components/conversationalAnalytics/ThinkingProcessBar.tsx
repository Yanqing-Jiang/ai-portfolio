import React from 'react';
import { PlanStep } from './hooks/useSSEStream';
import { useEffect, useRef } from 'react';

const statusColor: Record<PlanStep['status'], string> = {
    pending: 'text-gray-400',
    running: 'text-blue-400',
    completed: 'text-green-400',
    error: 'text-red-400',
};

const statusIcon: Record<PlanStep['status'], string> = {
    pending: '○',
    running: '●',
    completed: '✓',
    error: '✗',
};

interface ThinkingProcessBarProps {
    steps: PlanStep[];
    currentStepId: string | null;
    isExpanded: boolean;
    onToggle: () => void;
}

const ThinkingProcessBar: React.FC<ThinkingProcessBarProps> = ({
    steps,
    currentStepId,
    isExpanded,
    onToggle,
}) => {
    const currentStep = steps.find(s => s.id === currentStepId) || steps.find(s => s.status === 'running');
    const label = currentStep ? currentStep.label : 'Ready';
    const status = currentStep ? currentStep.status : 'completed';
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll the collapsed status text (ChatGPT-style marquee feel)
    useEffect(() => {
        const el = scrollRef.current;
        if (!el) return;
        let direction = 1;
        const speed = 1; // px per tick
        const interval = setInterval(() => {
            if (!el) return;
            el.scrollLeft += speed * direction;
            if (el.scrollLeft + el.clientWidth >= el.scrollWidth) {
                direction = -1;
            } else if (el.scrollLeft <= 0) {
                direction = 1;
            }
        }, 20);
        return () => clearInterval(interval);
    }, [label, status]);

    return (
        <div className="px-4 py-2 bg-gray-800 border-b border-gray-700">
            <button
                onClick={onToggle}
                className="w-full flex items-center justify-between text-sm text-gray-200"
            >
                <div className="flex items-center gap-2">
                    <span className="text-gray-400">Plan</span>
                    <span className={`${statusColor[status as PlanStep['status']]}`}>
                        {statusIcon[status as PlanStep['status']]}
                    </span>
                    <div
                        ref={scrollRef}
                        className="text-gray-300 max-w-[220px] overflow-x-auto whitespace-nowrap scrollbar-thin scrollbar-thumb-gray-700"
                        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
                    >
                        <span className="pr-8 inline-block">{label}</span>
                    </div>
                </div>
                <span className={`transform transition-transform ${isExpanded ? 'rotate-90' : ''}`}>▶</span>
            </button>

            {isExpanded && steps.length > 0 && (
                <div className="mt-2 space-y-2">
                    {steps.map(step => (
                        <div key={step.id} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                                <span className={statusColor[step.status]}>{statusIcon[step.status]}</span>
                                <span className="text-gray-200">{step.label}</span>
                            </div>
                            {step.summary && <span className="text-xs text-gray-400">{step.summary}</span>}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default ThinkingProcessBar;

