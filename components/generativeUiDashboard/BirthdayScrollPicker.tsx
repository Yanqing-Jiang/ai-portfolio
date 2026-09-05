/**
 * BirthdayScrollPicker — Mobile-first 3-column scroll wheel date picker
 * for BaZi fortune reading. iOS-style momentum scroll with snap behavior.
 *
 * Design choice: 3-column scroll picker (Year | Month | Day) because:
 * - Users selecting BaZi dates go back 50-80+ years — scroll wheels handle
 *   large ranges with O(1) taps (flick to decade, fine-tune)
 * - Familiar iOS/Android pattern = zero learning curve
 * - Fits within max-w-lg, works with touch, meets 44px tap targets
 * - No external deps — pure React + CSS scroll-snap + Framer Motion
 *
 * Usage:
 *   <BirthdayScrollPicker value="1990-06-15" onChange={(d) => setDate(d)} />
 *   Output: YYYY-MM-DD string (same contract as <input type="date">)
 */

import { useState, useRef, useCallback, useEffect, useMemo, type KeyboardEvent } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// ---------------------------------------------------------------------------
// Types & Constants
// ---------------------------------------------------------------------------

interface BirthdayScrollPickerProps {
    value: string; // YYYY-MM-DD or ''
    onChange: (date: string) => void;
    minYear?: number;
    maxYear?: number;
}

const MONTHS = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
] as const;

const MONTH_LABELS_CN: Record<number, string> = {
    1: '正月', 2: '二月', 3: '三月', 4: '四月',
    5: '五月', 6: '六月', 7: '七月', 8: '八月',
    9: '九月', 10: '十月', 11: '冬月', 12: '腊月',
};

function getDaysInMonth(year: number, month: number): number {
    return new Date(year, month, 0).getDate();
}

function pad2(n: number): string {
    return n.toString().padStart(2, '0');
}

// Chinese zodiac for year display
const ZODIAC_ANIMALS = ['鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪'];
function getZodiac(year: number): string {
    return ZODIAC_ANIMALS[(year - 4) % 12];
}

// Heavenly Stems
const HEAVENLY_STEMS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const EARTHLY_BRANCHES_YEAR = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
function getGanZhiYear(year: number): string {
    const stem = HEAVENLY_STEMS[(year - 4) % 10];
    const branch = EARTHLY_BRANCHES_YEAR[(year - 4) % 12];
    return `${stem}${branch}`;
}

// ---------------------------------------------------------------------------
// ScrollColumn — single column with momentum scroll + snap
// ---------------------------------------------------------------------------

const ITEM_HEIGHT = 48; // px — must match CSS
const VISIBLE_ITEMS = 5; // show 5 items, center one is selected

function scrollContainerTo(container: HTMLDivElement, top: number): void {
    if (typeof container.scrollTo === 'function') {
        container.scrollTo({ top, behavior: 'smooth' });
    } else {
        // jsdom and a few embedded webviews expose scrollTop without scrollTo.
        container.scrollTop = top;
    }
}

interface ScrollColumnProps {
    columnId: 'year' | 'month' | 'day';
    items: { value: number; label: string; sublabel?: string }[];
    selected: number;
    onSelect: (value: number) => void;
    width?: string;
}

function ScrollColumn({ columnId, items, selected, onSelect, width = '33%' }: ScrollColumnProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const isScrollingRef = useRef(false);
    const scrollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const selectedIndex = items.findIndex((i) => i.value === selected);

    // Scroll to selected item on mount and when selected changes externally
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        const targetScroll = selectedIndex * ITEM_HEIGHT;
        // Only programmatic-scroll if we're not currently user-scrolling
        if (!isScrollingRef.current) {
            container.scrollTop = targetScroll;
        }
    }, [selectedIndex]);

    const handleScroll = useCallback(() => {
        isScrollingRef.current = true;

        if (scrollTimeoutRef.current) {
            clearTimeout(scrollTimeoutRef.current);
        }

        scrollTimeoutRef.current = setTimeout(() => {
            isScrollingRef.current = false;
            const container = containerRef.current;
            if (!container) return;

            // Snap to nearest item
            const scrollPos = container.scrollTop;
            const nearestIndex = Math.round(scrollPos / ITEM_HEIGHT);
            const clampedIndex = Math.max(0, Math.min(nearestIndex, items.length - 1));

            // Smooth snap
            scrollContainerTo(container, clampedIndex * ITEM_HEIGHT);

            if (items[clampedIndex] && items[clampedIndex].value !== selected) {
                onSelect(items[clampedIndex].value);
            }
        }, 80);
    }, [items, selected, onSelect]);

    // Cleanup timeout
    useEffect(() => {
        return () => {
            if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current);
        };
    }, []);

    // Tap to select
    const selectItem = useCallback(
        (value: number, index: number) => {
            const container = containerRef.current;
            if (!container) return;
            scrollContainerTo(container, index * ITEM_HEIGHT);
            onSelect(value);
        },
        [onSelect],
    );

    const handleItemKeyDown = useCallback(
        (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
            let nextIndex: number | null = null;
            if (event.key === 'ArrowDown') nextIndex = Math.min(index + 1, items.length - 1);
            if (event.key === 'ArrowUp') nextIndex = Math.max(index - 1, 0);
            if (event.key === 'Home') nextIndex = 0;
            if (event.key === 'End') nextIndex = items.length - 1;
            if (nextIndex === null || nextIndex === index || !items[nextIndex]) return;

            event.preventDefault();
            selectItem(items[nextIndex].value, nextIndex);
        },
        [items, selectItem],
    );

    // Padding items so the first/last can reach center
    const paddingCount = Math.floor(VISIBLE_ITEMS / 2);

    return (
        <div className="relative" style={{ width, height: ITEM_HEIGHT * VISIBLE_ITEMS }}>
            {/* Selection highlight bar */}
            <div
                className="pointer-events-none absolute left-1 right-1 rounded-lg"
                style={{
                    top: ITEM_HEIGHT * paddingCount,
                    height: ITEM_HEIGHT,
                    background: 'rgba(234, 179, 8, 0.08)',
                    border: '1px solid rgba(234, 179, 8, 0.2)',
                    zIndex: 2,
                }}
            />

            {/* Fade gradients */}
            <div
                className="pointer-events-none absolute inset-x-0 top-0 z-10"
                style={{
                    height: ITEM_HEIGHT * 1.5,
                    background: 'linear-gradient(to bottom, var(--ming-bg, #0c0a14) 0%, transparent 100%)',
                }}
            />
            <div
                className="pointer-events-none absolute inset-x-0 bottom-0 z-10"
                style={{
                    height: ITEM_HEIGHT * 1.5,
                    background: 'linear-gradient(to top, var(--ming-bg, #0c0a14) 0%, transparent 100%)',
                }}
            />

            {/* Scrollable list */}
            <div
                ref={containerRef}
                className="h-full overflow-y-auto scrollbar-hide"
                role="group"
                aria-label={`${columnId} of birth`}
                onScroll={handleScroll}
                style={{
                    scrollSnapType: 'y mandatory',
                    WebkitOverflowScrolling: 'touch',
                    msOverflowStyle: 'none',
                    scrollbarWidth: 'none',
                }}
            >
                {/* Top padding */}
                {Array.from({ length: paddingCount }).map((_, i) => (
                    <div key={`${columnId}-pad-top-${i}`} style={{ height: ITEM_HEIGHT }} />
                ))}

                {items.map((item, index) => {
                    const isSelected = item.value === selected;
                    return (
                        <button
                            type="button"
                            key={`${columnId}-${item.value}-${index}`}
                            onClick={() => selectItem(item.value, index)}
                            onKeyDown={(event) => handleItemKeyDown(event, index)}
                            aria-label={`${item.label}${item.sublabel ? `, ${item.sublabel}` : ''}`}
                            aria-pressed={isSelected}
                            className="flex w-full cursor-pointer items-center justify-center select-none border-0 p-0"
                            style={{
                                height: ITEM_HEIGHT,
                                scrollSnapAlign: 'start',
                                transition: 'color 0.15s, opacity 0.15s',
                                color: isSelected ? '#eab308' : '#94a3b8',
                                opacity: isSelected ? 1 : 0.5,
                                fontWeight: isSelected ? 600 : 400,
                                background: 'transparent',
                            }}
                        >
                            <div className="flex flex-col items-center leading-tight">
                                <span
                                    className="text-base"
                                    style={{
                                        fontSize: isSelected ? '18px' : '15px',
                                        transition: 'font-size 0.15s',
                                    }}
                                >
                                    {item.label}
                                </span>
                                {item.sublabel && (
                                    <span
                                        className="text-[10px]"
                                        style={{
                                            fontFamily: 'var(--ming-font-chinese)',
                                            opacity: 0.7,
                                        }}
                                    >
                                        {item.sublabel}
                                    </span>
                                )}
                            </div>
                        </button>
                    );
                })}

                {/* Bottom padding */}
                {Array.from({ length: paddingCount }).map((_, i) => (
                    <div key={`${columnId}-pad-bot-${i}`} style={{ height: ITEM_HEIGHT }} />
                ))}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function BirthdayScrollPicker({
    value,
    onChange,
    minYear = 1940,
    maxYear = 2026,
}: BirthdayScrollPickerProps) {
    // Parse initial value or default to 1990-01-15
    const parsed = useMemo(() => {
        if (value) {
            const [y, m, d] = value.split('-').map(Number);
            if (y && m && d) return { year: y, month: m, day: d };
        }
        return { year: 1990, month: 1, day: 15 };
    }, [value]);

    const [year, setYear] = useState(parsed.year);
    const [month, setMonth] = useState(parsed.month);
    const [day, setDay] = useState(parsed.day);
    const [isOpen, setIsOpen] = useState(false);

    // Clamp day when year/month changes
    const maxDay = getDaysInMonth(year, month);
    const clampedDay = Math.min(day, maxDay);

    // Emit change
    const emitDate = useCallback(
        (y: number, m: number, d: number) => {
            const md = getDaysInMonth(y, m);
            const cd = Math.min(d, md);
            onChange(`${y}-${pad2(m)}-${pad2(cd)}`);
        },
        [onChange],
    );

    const handleYearChange = useCallback(
        (y: number) => {
            setYear(y);
            emitDate(y, month, day);
        },
        [month, day, emitDate],
    );

    const handleMonthChange = useCallback(
        (m: number) => {
            setMonth(m);
            emitDate(year, m, day);
        },
        [year, day, emitDate],
    );

    const handleDayChange = useCallback(
        (d: number) => {
            setDay(d);
            emitDate(year, month, d);
        },
        [year, month, emitDate],
    );

    // Sync internal state if value prop changes externally
    useEffect(() => {
        if (value) {
            const [y, m, d] = value.split('-').map(Number);
            if (y && m && d) {
                setYear(y);
                setMonth(m);
                setDay(d);
            }
        }
    }, [value]);

    // Build column items
    const yearItems = useMemo(() => {
        const items = [];
        for (let y = maxYear; y >= minYear; y--) {
            items.push({
                value: y,
                label: `${y}`,
                sublabel: `${getGanZhiYear(y)}${getZodiac(y)}年`,
            });
        }
        return items;
    }, [minYear, maxYear]);

    const monthItems = useMemo(() => {
        return Array.from({ length: 12 }, (_, i) => ({
            value: i + 1,
            label: MONTHS[i],
            sublabel: MONTH_LABELS_CN[i + 1],
        }));
    }, []);

    const dayItems = useMemo(() => {
        return Array.from({ length: maxDay }, (_, i) => ({
            value: i + 1,
            label: `${i + 1}`,
        }));
    }, [maxDay]);

    // Display string
    const displayValue = value
        ? `${year}  /  ${MONTHS[month - 1]}  /  ${clampedDay}`
        : '';

    const displaySublabel = value
        ? `${getGanZhiYear(year)}${getZodiac(year)}年 ${MONTH_LABELS_CN[month]}${clampedDay}日`
        : '';

    return (
        <div className="relative">
            {/* Trigger button — looks like an input field */}
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className="flex w-full items-center justify-between rounded-lg border px-4 py-3 text-left transition-colors"
                style={{
                    background: 'rgba(30, 41, 59, 0.5)',
                    borderColor: isOpen
                        ? 'var(--ming-gold, #eab308)'
                        : 'rgba(148, 163, 184, 0.2)',
                    minHeight: '48px',
                }}
            >
                <div className="flex flex-col">
                    {value ? (
                        <>
                            <span className="text-base text-slate-200">{displayValue}</span>
                            <span
                                className="text-xs text-slate-500"
                                style={{ fontFamily: 'var(--ming-font-chinese)' }}
                            >
                                {displaySublabel}
                            </span>
                        </>
                    ) : (
                        <span className="text-base text-slate-500">Select birthday</span>
                    )}
                </div>

                {/* Chevron */}
                <svg
                    className="h-5 w-5 text-slate-500 transition-transform"
                    style={{ transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
            </button>

            {/* Scroll picker panel */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                        className="overflow-hidden"
                    >
                        <div
                            className="mt-2 rounded-xl border p-1"
                            style={{
                                background: 'var(--ming-bg, #0c0a14)',
                                borderColor: 'rgba(148, 163, 184, 0.15)',
                            }}
                        >
                            {/* Column headers */}
                            <div className="flex px-1 pb-1 pt-2">
                                <div className="flex-1 text-center text-xs font-medium text-slate-500">
                                    Year
                                </div>
                                <div className="flex-1 text-center text-xs font-medium text-slate-500">
                                    Month
                                </div>
                                <div className="flex-1 text-center text-xs font-medium text-slate-500">
                                    Day
                                </div>
                            </div>

                            {/* Columns */}
                            <div className="flex">
                                <ScrollColumn
                                    columnId="year"
                                    items={yearItems}
                                    selected={year}
                                    onSelect={handleYearChange}
                                />
                                <ScrollColumn
                                    columnId="month"
                                    items={monthItems}
                                    selected={month}
                                    onSelect={handleMonthChange}
                                />
                                <ScrollColumn
                                    columnId="day"
                                    items={dayItems}
                                    selected={clampedDay}
                                    onSelect={handleDayChange}
                                />
                            </div>

                            {/* Done button */}
                            <div className="px-2 pb-2 pt-1">
                                <button
                                    type="button"
                                    onClick={() => setIsOpen(false)}
                                    className="w-full rounded-lg py-2.5 text-sm font-medium transition-colors"
                                    style={{
                                        background: 'rgba(234, 179, 8, 0.12)',
                                        color: '#eab308',
                                        border: '1px solid rgba(234, 179, 8, 0.25)',
                                    }}
                                >
                                    Done
                                </button>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Hide native scrollbar globally for this component */}
            <style>{`
                .scrollbar-hide::-webkit-scrollbar { display: none; }
                .scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
            `}</style>
        </div>
    );
}
