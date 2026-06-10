import React, { useCallback, useEffect, useRef, useState } from 'react';
import { StepIndicator } from './StepIndicator';
import { StylePresetCard, INITIAL_STYLE_PRESETS, type StylePreset } from './StylePresetCard';
import { ImageVariationGallery, type ImageVariation } from './ImageVariationGallery';
import { VariationControls, type VariationRequestOptions } from './VariationControls';
import { CustomStyleBuilder, buildCustomPromptFromParams, type CustomStyleParams } from './CustomStyleBuilder';
import { MagicScanAnimation } from './MagicScanAnimation';
import { PhotoScorecard, type PhotoScores } from './PhotoScorecard';
import { HolographicButton } from './HolographicButton';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Upload, X, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { configService } from '@/services/config';
import { apiService } from '@/services/apiService';
import { AuthModal } from '../AuthModal';
import { authService, type AuthState } from '@/services/auth';

// --- Function/Class Map ---
// Component: LinkedInPhotoPage — mounted by ProjectView for the LinkedIn photo project; handles upload → prompt selection → generation/variation.
// Helper: fetchCredits — fetches LinkedIn photo credits for signed-in users from /api/headshot-studio/credits.
// Helper: ensureAuthenticated/ensureCreditsAvailable — gates actions to logged-in users with remaining credits; shows auth or follow modals when blocked.
// Purpose: Deliver the LinkedIn photo generator experience with credit gating, hero imagery, and preset loading.

interface LinkedInPhotoPageProps {
  apiPath?: string;
}

const STEPS = [
  { number: 1, label: 'Upload Photo' },
  { number: 2, label: 'Choose Style' },
  { number: 3, label: 'Review Results' },
];

// Premium "Luxury Executive" theme: Midnight Navy + Champagne Gold
const HEADSHOT_STUDIO_THEME: React.CSSProperties & Record<`--${string}`, string> = {
  '--background': '222 71% 4%',
  '--foreground': '210 40% 96%',
  '--card': '222 50% 8%',
  '--card-foreground': '210 40% 96%',
  '--popover': '222 50% 10%',
  '--popover-foreground': '210 40% 96%',
  '--primary': '43 74% 49%',
  '--primary-foreground': '222 71% 4%',
  '--secondary': '222 30% 14%',
  '--secondary-foreground': '210 40% 96%',
  '--muted': '217 28% 16%',
  '--muted-foreground': '214 20% 68%',
  '--accent': '210 100% 40%',
  '--accent-foreground': '210 40% 98%',
  '--destructive': '0 62.8% 45%',
  '--destructive-foreground': '210 40% 98%',
  '--border': '222 32% 20%',
  '--input': '222 32% 20%',
  '--ring': '43 74% 49%',
};

const VARIATION_API_PATH = '/api/headshot-studio/variation';
const LINKEDIN_CREDIT_LIMIT = 2;
const LINKEDIN_FOLLOW_URL = 'https://www.linkedin.com/in/jiangyanqing/';

const LinkedInPhotoPage: React.FC<LinkedInPhotoPageProps> = ({ apiPath = '/api/headshot-studio/generate' }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [selectedPreset, setSelectedPreset] = useState<StylePreset | null>(null);
  const [stylePrompt, setStylePrompt] = useState('');
  const [expandedPrompt, setExpandedPrompt] = useState('');
  const [variations, setVariations] = useState<ImageVariation[]>([]);
  const [processingMs, setProcessingMs] = useState<number | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [shareStatus, setShareStatus] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [presetOptions, setPresetOptions] = useState<StylePreset[]>(INITIAL_STYLE_PRESETS);
  const [isLoadingPresets, setIsLoadingPresets] = useState(true);
  const [presetLoadError, setPresetLoadError] = useState<string | null>(null);
  const [isCreatingVariation, setIsCreatingVariation] = useState(false);
  const [customStyleParams, setCustomStyleParams] = useState<CustomStyleParams>({
    clothing: null,
    expression: null,
    background: null,
    pose: null,
  });
  const [authState, setAuthState] = useState<AuthState>({ user: null, loading: true, error: null });
  const [showAuthModal, setShowAuthModal] = useState(false);
  type CreditInfo = { used: number; remaining: number; limit: number };
  const [credits, setCredits] = useState<CreditInfo | null>(null);
  const [creditsLoading, setCreditsLoading] = useState(false);
  const [creditsError, setCreditsError] = useState<string | null>(null);
  const [showFollowModal, setShowFollowModal] = useState(false);
  const [followMessage, setFollowMessage] = useState<string | null>(null);
  // AI Quality Scorecard state
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<{ scores: PhotoScores; tips: string[]; processingMs: number } | null>(null);
  const isSignedIn = !!authState.user;

  const fileInputRef = useRef<HTMLInputElement>(null);
  const step2Ref = useRef<HTMLDivElement>(null);
  const step3Ref = useRef<HTMLDivElement>(null);
  const backendBaseRef = useRef(configService.getBackendUrl().replace(/\/$/, ''));

  useEffect(() => {
    const unsubscribe = authService.subscribe(setAuthState);
    return unsubscribe;
  }, []);

  const fetchCredits = useCallback(async (): Promise<CreditInfo | null> => {
    if (!authState.user) {
      setCredits(null);
      setCreditsError(null);
      return null;
    }

    setCreditsLoading(true);
    setCreditsError(null);

    try {
      const headers = await authService.getAuthHeaders();
      const response = await fetch(`${backendBaseRef.current}/api/headshot-studio/credits`, {
        headers,
      });

      if (response.status === 401) {
        setShowAuthModal(true);
        throw new Error('Sign in to view your LinkedIn photo credits.');
      }

      if (!response.ok) {
        const text = await response.text().catch(() => '');
        const trimmed = text.trim();
        throw new Error(trimmed || `Unable to load credits (HTTP ${response.status}).`);
      }

      const payload = await response.json();
      const nextCredits: CreditInfo = {
        used: typeof payload?.used === 'number' ? payload.used : 0,
        remaining: typeof payload?.remaining === 'number' ? payload.remaining : 0,
        limit: typeof payload?.limit === 'number' ? payload.limit : LINKEDIN_CREDIT_LIMIT,
      };
      setCredits(nextCredits);
      return nextCredits;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to load credits.';
      setCreditsError(message);
      return null;
    } finally {
      setCreditsLoading(false);
    }
  }, [authState.user]);

  const ensureAuthenticated = useCallback((): boolean => {
    if (!authState.user) {
      setShowAuthModal(true);
      setError('Sign in to generate your LinkedIn photo.');
      return false;
    }
    return true;
  }, [authState.user]);

  const ensureCreditsAvailable = useCallback(async (): Promise<boolean> => {
    const latest = await fetchCredits();
    const snapshot = latest ?? credits;
    if (!snapshot) {
      if (creditsError) {
        setError(creditsError);
      }
      return false;
    }
    const remaining = snapshot.remaining ?? 0;

    if (remaining <= 0) {
      const message =
        'You have used all available LinkedIn photo credits. Follow Yanqing on LinkedIn to request more.';
      setFollowMessage(message);
      setShowFollowModal(true);
      setError(message);
      return false;
    }
    return true;
  }, [credits, creditsError, fetchCredits]);

  useEffect(() => {
    if (authState.loading) return;
    if (!authState.user) {
      setCredits(null);
      setCreditsError(null);
      return;
    }
    fetchCredits();
  }, [authState.loading, authState.user, fetchCredits]);

  const handleFollowClose = () => {
    setShowFollowModal(false);
    setFollowMessage(null);
  };

  const handleFollowLink = () => {
    window.open(LINKEDIN_FOLLOW_URL, '_blank', 'noopener,noreferrer');
  };

  useEffect(() => {
    return () => {
      if (photoPreview) {
        URL.revokeObjectURL(photoPreview);
      }
    };
  }, [photoPreview]);

  useEffect(() => {
    let isActive = true;

    const loadCanonicalPrompts = async () => {
      try {
        setIsLoadingPresets(true);
        setPresetLoadError(null);

        const targetUrl = `${backendBaseRef.current}/api/headshot-studio/prompts`;
        const response = await fetch(targetUrl);

        if (!response.ok) {
          let detail: string | undefined;
          try {
            const errorJson = await response.json();
            if (typeof errorJson?.detail === 'string') {
              detail = errorJson.detail;
            }
          } catch {
            // ignore JSON parsing issues
          }
          if (!detail) {
            const text = await response.text().catch(() => '');
            detail = text.trim() || `Request failed with status ${response.status}`;
          }
          throw new Error(detail);
        }

        const payload = (await response.json()) as Record<string, string>;
        const nextOptions = INITIAL_STYLE_PRESETS.map((preset) => {
          if (preset.expansionMode === 'fixed') {
            const candidate = payload?.[preset.id];
            if (typeof candidate === 'string' && candidate.trim().length > 0) {
              return { ...preset, prompt: candidate.trim() };
            }
          }
          return preset;
        });

        if (!isActive) return;

        setPresetOptions(nextOptions);
        setSelectedPreset((prev) => {
          if (!prev) return prev;
          const updated = nextOptions.find((option) => option.id === prev.id);
          if (!updated) {
            return prev;
          }
          if (updated.expansionMode === 'fixed') {
            setStylePrompt(updated.prompt);
          }
          return updated;
        });
      } catch (err) {
        if (!isActive) return;
        const message =
          err instanceof Error && err.message
            ? err.message
            : 'Unknown error while loading prompts.';
        setPresetLoadError(`Unable to load canonical presets. ${message}`);
      } finally {
        if (isActive) {
          setIsLoadingPresets(false);
        }
      }
    };

    loadCanonicalPrompts();

    return () => {
      isActive = false;
    };
  }, []);

  const scrollToRef = (ref: React.RefObject<HTMLDivElement | null>) => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const normalizeVariations = (raw: any[], existingCount = 0): ImageVariation[] => {
    if (!Array.isArray(raw)) return [];

    return raw
      .map((variation: any, index: number) => {
        const fallbackIndex = existingCount + index + 1;
        const id =
          typeof variation?.id === 'string' && variation.id.length > 0
            ? variation.id
            : `var-${fallbackIndex}`;
        const imageBase64 =
          typeof variation?.image_base64 === 'string' && variation.image_base64.length > 0
            ? variation.image_base64
            : typeof variation?.imageBase64 === 'string' && variation.imageBase64.length > 0
              ? variation.imageBase64
              : '';
        const imageMimeType =
          typeof variation?.image_mime_type === 'string' && variation.image_mime_type.length > 0
            ? variation.image_mime_type
            : typeof variation?.imageMimeType === 'string' && variation.imageMimeType.length > 0
              ? variation.imageMimeType
              : 'image/png';

        const width = Number.isFinite(variation?.width) ? Number(variation.width) : 0;
        const height = Number.isFinite(variation?.height) ? Number(variation.height) : 0;

        return {
          id,
          imageBase64,
          imageMimeType,
          width,
          height,
        };
      })
      .filter((variation: ImageVariation) => variation.imageBase64.length > 0);
  };

  const handleFileChange = async (file: File | null) => {
    setError(null);
    setAnalysisResult(null);
    if (!file) {
      setPhotoFile(null);
      if (photoPreview) {
        URL.revokeObjectURL(photoPreview);
        setPhotoPreview(null);
      }
      return;
    }

    const nextPreview = URL.createObjectURL(file);
    if (photoPreview) URL.revokeObjectURL(photoPreview);
    setPhotoPreview(nextPreview);
    setPhotoFile(file);
    // Stay on Step 1 - let user review their score before proceeding
    // setCurrentStep(2) is removed - user will move to Step 2 manually

    // Trigger AI Quality Scorecard analysis
    setIsAnalyzing(true);
    try {
      const formData = new FormData();
      formData.append('photo', file);

      // Include auth headers so signed-in users get higher rate limits
      const authHeaders = await authService.getAuthHeaders();

      const response = await fetch(`${backendBaseRef.current}/api/headshot-studio/analyze`, {
        method: 'POST',
        headers: authHeaders,
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setAnalysisResult({
          scores: data.scores,
          tips: data.tips || [],
          processingMs: data.processing_ms || 0,
        });
        // Auto-scroll scorecard into view on mobile
        setTimeout(() => {
          document.querySelector('[data-scorecard]')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 100);
      } else if (response.status === 429) {
        setError('Analysis rate limit exceeded. Please try again in a few minutes.');
      } else {
        setError('Photo analysis is temporarily unavailable. Please try again.');
        console.warn('Photo analysis failed:', response.status);
      }
    } catch (err) {
      setError('Could not connect to the analysis service. Please try again.');
      console.warn('Photo analysis error:', err);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    handleFileChange(file || null);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file && (file.type === 'image/jpeg' || file.type === 'image/png')) {
      handleFileChange(file);
    }
  };

  const handleCreateVariation = async (options: VariationRequestOptions) => {
    if (!photoFile || !expandedPrompt.trim()) {
      return;
    }

    if (!ensureAuthenticated()) return;
    const hasCredits = await ensureCreditsAvailable();
    if (!hasCredits) return;

    setIsCreatingVariation(true);
    setError(null);
    setShareStatus(null);

    const formData = new FormData();
    formData.append('photo', photoFile);
    formData.append('base_prompt', expandedPrompt);
    formData.append('background', options.background);
    formData.append('expression', options.expression);
    formData.append('pose', options.pose);
    formData.append('prop', options.prop);

    try {
      const authHeaders = await authService.getAuthHeaders();
      const targetUrl = VARIATION_API_PATH.startsWith('http')
        ? VARIATION_API_PATH
        : `${backendBaseRef.current}${VARIATION_API_PATH.startsWith('/') ? '' : '/'}${VARIATION_API_PATH}`;

      const response = await fetch(targetUrl, {
        method: 'POST',
        body: formData,
        headers: {
          ...authHeaders,
        },
      });

      if (!response.ok) {
        let errorDetail: string | undefined;
        try {
          const errorJson = await response.json();
          if (typeof errorJson?.detail === 'string') {
            errorDetail = errorJson.detail;
          } else if (typeof errorJson?.error === 'string') {
            errorDetail = errorJson.error;
          }
        } catch {
          // fall through
        }

        if (!errorDetail) {
          const fallbackText = await response.text().catch(() => '');
          const trimmed = fallbackText.trim();
          if (trimmed && !trimmed.startsWith('<')) {
            errorDetail = trimmed;
          } else {
            errorDetail = `Variation request failed with status ${response.status}`;
          }
        }

        throw new Error(errorDetail || 'Failed to create a variation.');
      }

      const payload = await response.json();
      const nextPrompt = payload.expanded_prompt ?? payload.expandedPrompt ?? '';
      setExpandedPrompt(nextPrompt);

      const rawVariations = Array.isArray(payload.variations) ? payload.variations : [];
      const normalizedVariations = normalizeVariations(rawVariations, variations.length);
      setVariations((prev) => [...prev, ...normalizedVariations]);

      const nextProcessingMs =
        typeof payload.processing_ms === 'number'
          ? payload.processing_ms
          : typeof payload.processingMs === 'number'
            ? payload.processingMs
            : null;
      if (nextProcessingMs !== null) {
        setProcessingMs(nextProcessingMs);
      }

      await fetchCredits();
      setTimeout(() => scrollToRef(step3Ref), 100);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to create a variation right now.';
      console.error('LinkedIn photo variation failed:', err);
      setError(message);
      if (message.toLowerCase().includes('credit') || message.toLowerCase().includes('follow yanqing')) {
        setFollowMessage(message);
        setShowFollowModal(true);
      }
    } finally {
      setIsCreatingVariation(false);
    }
  };

  const handlePresetSelect = (preset: StylePreset) => {
    setSelectedPreset(preset);
    setStylePrompt(preset.prompt);
    setError(null);

    // Reset custom style params when switching away from custom
    if (preset.id !== 'custom') {
      setCustomStyleParams({
        clothing: null,
        expression: null,
        background: null,
        pose: null,
      });
    }
  };

  const handleGenerate = async () => {
    if (!photoFile) return;

    if (!ensureAuthenticated()) return;
    const hasCredits = await ensureCreditsAvailable();
    if (!hasCredits) return;

    const isCustomPreset = selectedPreset?.id === 'custom';

    // Build prompt from custom params if custom preset selected
    let promptForSubmission = stylePrompt.trim();
    if (isCustomPreset) {
      promptForSubmission = buildCustomPromptFromParams(customStyleParams);
    }

    if (!promptForSubmission) return;

    const shouldUseLLMExpansion = isCustomPreset
      ? promptForSubmission.length < 100
      : selectedPreset?.expansionMode !== 'fixed';

    setIsGenerating(true);
    setError(null);
    setShareStatus(null);
    setExpandedPrompt('');
    setVariations([]);
    setProcessingMs(null);
    setGenerationProgress(0);

    let progressInterval: ReturnType<typeof setInterval> | null = null;

    const formData = new FormData();
    formData.append('photo', photoFile);
    formData.append('prompt', promptForSubmission);
    if (!shouldUseLLMExpansion) {
      formData.append('prompt_mode', 'fixed');
    }

    try {
      const usageResponse = await apiService.countUserInput({ weight: 10 });
      if (!usageResponse.success) {
        const baseMessage =
          usageResponse.error ||
          'Daily photo quota reached. Please try again after the midnight UTC reset.';
        const noticeSuffix = usageResponse.needsAuth
          ? ' Sign in or purchase tokens to continue.'
          : ' Free guest quota resets at 00:00 UTC.';
        setError(`${baseMessage}${noticeSuffix}`.trim());
        return;
      }

      // Simulate progress after quota check passes
      progressInterval = setInterval(() => {
        setGenerationProgress((prev) => Math.min(prev + 10, 90));
      }, 500);

      const authHeaders = await authService.getAuthHeaders();
      const targetUrl = apiPath.startsWith('http')
        ? apiPath
        : `${backendBaseRef.current}${apiPath.startsWith('/') ? '' : '/'}${apiPath}`;

      const response = await fetch(targetUrl, {
        method: 'POST',
        body: formData,
        headers: {
          ...authHeaders,
        },
      });

      if (!response.ok) {
        let errorDetail: string | undefined;
        try {
          const errorJson = await response.json();
          if (typeof errorJson?.detail === 'string') {
            errorDetail = errorJson.detail;
          } else if (typeof errorJson?.error === 'string') {
            errorDetail = errorJson.error;
          }
        } catch {
          // Non-JSON response bodies are handled below
        }

        if (!errorDetail) {
          const fallbackText = await response.text().catch(() => '');
          const trimmed = fallbackText.trim();
          if (trimmed && !trimmed.startsWith('<')) {
            errorDetail = trimmed;
          } else {
            errorDetail = `Request failed with status ${response.status}`;
          }
        }

        throw new Error(errorDetail || 'Failed to generate headshot.');
      }

      const payload = await response.json();
      setExpandedPrompt(payload.expanded_prompt ?? payload.expandedPrompt ?? '');

      const rawVariations = Array.isArray(payload.variations) ? payload.variations : [];
      const normalizedVariations = normalizeVariations(rawVariations);
      setVariations(normalizedVariations);

      const nextProcessingMs =
        typeof payload.processing_ms === 'number'
          ? payload.processing_ms
          : typeof payload.processingMs === 'number'
            ? payload.processingMs
            : null;
      setProcessingMs(nextProcessingMs);
      await fetchCredits();
      setGenerationProgress(100);
      setCurrentStep(3);
      setTimeout(() => scrollToRef(step3Ref), 100);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to generate headshot right now.';
      console.error('LinkedIn photo generation failed:', err);
      setError(message);
      if (message.toLowerCase().includes('credit') || message.toLowerCase().includes('follow yanqing')) {
        setFollowMessage(message);
        setShowFollowModal(true);
      }
    } finally {
      if (progressInterval) {
        clearInterval(progressInterval);
      }
      setIsGenerating(false);
      setGenerationProgress(0);
    }
  };

  const handleDownloadVariation = (variationId: string) => {
    const variation = variations.find((v) => v.id === variationId);
    if (!variation) return;

    const dataUrl = `data:${variation.imageMimeType};base64,${variation.imageBase64}`;
    const anchor = document.createElement('a');
    anchor.href = dataUrl;
    anchor.download = `linkedin-headshot-${variationId}.png`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
  };

  const handleShareVariation = async (variationId: string) => {
    const variation = variations.find((v) => v.id === variationId);
    if (!variation) return;

    if (!('share' in navigator)) {
      setShareStatus('Web Share is unavailable. Download the headshot to share it manually.');
      return;
    }

    try {
      const dataUrl = `data:${variation.imageMimeType};base64,${variation.imageBase64}`;
      const blob = await (await fetch(dataUrl)).blob();
      const file = new File([blob], `linkedin-headshot-${variationId}.png`, { type: variation.imageMimeType });

      await navigator.share({
        files: [file],
        title: 'LinkedIn Headshot',
        text: 'Generated with AI Headshot Studio.',
      });
      setShareStatus('Shared successfully.');
    } catch (err) {
      if ((err as DOMException)?.name === 'AbortError') {
        setShareStatus('Share cancelled.');
      } else {
        setShareStatus('Unable to share automatically. Try downloading instead.');
      }
    }
  };

  const handleReset = () => {
    setPhotoFile(null);
    if (photoPreview) {
      URL.revokeObjectURL(photoPreview);
      setPhotoPreview(null);
    }
    setSelectedPreset(null);
    setStylePrompt('');
    setExpandedPrompt('');
    setVariations([]);
    setProcessingMs(null);
    setError(null);
    setShareStatus(null);
    setIsCreatingVariation(false);
    setCurrentStep(1);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="relative min-h-screen overflow-hidden" style={HEADSHOT_STUDIO_THEME}>
      <div className="absolute inset-0 bg-gradient-to-br from-[#0B1120] via-slate-900 to-[#0B1120]" />
      <div className="pointer-events-none absolute -top-40 right-[-25%] h-[520px] w-[520px] rounded-full bg-amber-500/10 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-48 left-[-20%] h-[560px] w-[560px] rounded-full bg-blue-600/10 blur-3xl" />

      {/* Google Fonts for premium typography */}
      <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&display=swap" rel="stylesheet" />

      <div className="relative z-10 py-8 sm:py-16 md:py-20 px-3 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto space-y-6 sm:space-y-12 text-foreground">
          {/* Header - fades away when photo is uploaded */}
          <header className={cn(
            "text-center space-y-6 mb-4 transition-all duration-500",
            photoFile && "opacity-0 h-0 overflow-hidden !mb-0 !space-y-0"
          )}>
            <div className="space-y-4">
              <h1
                className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight text-foreground leading-[1.1]"
                style={{ fontFamily: "'Cormorant Garamond', 'Playfair Display', Georgia, serif" }}
              >
                The Headshot Studio
              </h1>
              <p className="text-xl sm:text-2xl text-muted-foreground/90 max-w-3xl mx-auto font-light leading-relaxed flex items-center justify-center gap-2 flex-wrap">
                <span className="text-primary font-medium">Executive-grade AI portraits</span>
                <span>powered by</span>
                <a
                  href="https://deepmind.google/technologies/gemini/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="relative inline-flex items-center group"
                >
                  <img
                    src="https://www.gstatic.com/lamda/images/gemini_sparkle_v002_d4735304ff6292a690345.svg"
                    alt="Google Gemini"
                    className="h-6 w-6 mr-1"
                  />
                  <span className="text-primary font-semibold hover:underline">
                    Gemini 3 Image
                  </span>
                  {/* Tooltip */}
                  <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-slate-800 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none whitespace-nowrap border border-amber-500/30 shadow-xl z-50">
                    Also known as "Nano Banana Pro" (experimental image generation model)
                  </span>
                </a>
              </p>
              <div className="flex justify-center">
                <video
                  autoPlay
                  muted
                  loop
                  playsInline
                  poster="https://yanqinghot.blob.core.windows.net/public-access/3-photo-rotate-poster.jpg"
                  className="w-full max-w-3xl rounded-2xl shadow-2xl border-2 border-amber-500/40"
                  aria-label="Before and after transformation showcase"
                >
                  <source src="https://yanqinghot.blob.core.windows.net/public-access/3-photo-rotate.webm" type="video/webm" />
                  <source src="https://yanqinghot.blob.core.windows.net/public-access/3-photo-rotate.mp4" type="video/mp4" />
                  <img src="https://yanqinghot.blob.core.windows.net/public-access/3-photo-rotate-poster.jpg" alt="Before and after transformation showcase" loading="lazy" />
                </video>
              </div>
            </div>
            {/* Only show credits badge when signed in - no sign-in banner here */}
            {isSignedIn && (
              <div className="flex justify-center">
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/30 text-primary-foreground">
                  <Sparkles className="w-4 h-4" />
                  <span>
                    {creditsLoading
                      ? 'Loading credits...'
                      : `${credits?.remaining ?? LINKEDIN_CREDIT_LIMIT}/${credits?.limit ?? LINKEDIN_CREDIT_LIMIT} headshot credits left`}
                  </span>
                </div>
              </div>
            )}
            {creditsError && isSignedIn && (
              <div className="max-w-3xl mx-auto p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-sm text-destructive text-left">
                {creditsError}
              </div>
            )}
          </header>

          {/* Step Indicator - always visible */}
          <StepIndicator steps={STEPS} currentStep={currentStep} />

          <div className="grid gap-8 lg:grid-cols-2 lg:items-start">
            {/* Step 1: Upload Photo */}
            <Card className="h-full border-border/50 shadow-xl">
              <CardHeader className="space-y-3 pb-6 p-4 sm:p-6 sm:pb-6">
                <CardTitle className="flex items-center gap-3 text-xl sm:text-2xl">
                  <span className="flex items-center justify-center w-10 h-10 rounded-full bg-primary text-primary-foreground text-base font-bold">
                    1
                  </span>
                  Upload Photo
                </CardTitle>
                <CardDescription className="text-sm sm:text-base leading-relaxed">
                  Get a{' '}
                  <span className="relative inline-block group cursor-help">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-gradient-to-r from-violet-500/15 to-blue-500/15 text-blue-300 font-medium rounded-full border border-blue-400/30 text-sm hover:border-blue-400/50 transition-colors">
                      <Sparkles className="w-3.5 h-3.5 text-violet-400" />
                      Professional Readiness Score
                    </span>
                    {/* Tooltip explaining scoring */}
                    <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 p-3 bg-slate-800 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none w-64 border border-amber-500/30 shadow-xl z-50">
                      <strong className="block mb-1 text-amber-400">AI Quality Scores (1-10):</strong>
                      <ul className="space-y-0.5 text-slate-300">
                        <li>• <span className="text-white">Lighting</span> - Even illumination, no harsh shadows</li>
                        <li>• <span className="text-white">Angle</span> - Flattering camera height and position</li>
                        <li>• <span className="text-white">Background</span> - Clean, professional setting</li>
                        <li>• <span className="text-white">Expression</span> - Confident, approachable look</li>
                        <li>• <span className="text-white">Outfit</span> - Professional attire assessment</li>
                      </ul>
                    </span>
                  </span>
                  {' '}for free.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 p-4 pt-0 sm:p-6 sm:pt-0">
                <div
                  className={cn(
                    'border-2 border-dashed rounded-xl p-4 sm:p-10 transition-all cursor-pointer',
                    isDragging ? 'border-primary bg-primary/5 scale-[1.02]' : 'border-border hover:border-primary/50',
                    photoPreview && 'bg-muted/30'
                  )}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/*"
                    onChange={handleInputChange}
                    aria-label="Upload photo"
                    className="hidden"
                  />
                  {photoPreview ? (
                    <div className="flex flex-col md:flex-row items-center gap-3 sm:gap-6">
                      <div className="relative">
                        <img src={photoPreview} alt="Preview" className="w-32 h-32 object-cover rounded-xl border shadow-md" />
                        <MagicScanAnimation isActive={isAnalyzing} />
                      </div>
                      <div className="flex-1 text-center md:text-left space-y-2">
                        {isAnalyzing ? (
                          <div className="space-y-3">
                            <div className="flex items-center gap-2">
                              <div className="animate-spin rounded-full h-4 w-4 border-2 border-primary border-t-transparent" />
                              <p className="font-semibold text-base text-primary animate-pulse">
                                Analyzing Readiness Score...
                              </p>
                            </div>
                            <div className="w-full max-w-xs">
                              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                                <div className="h-full bg-gradient-to-r from-amber-500 to-primary rounded-full animate-pulse" style={{ width: '60%' }} />
                              </div>
                              <p className="text-xs text-muted-foreground mt-1">AI is evaluating your photo...</p>
                            </div>
                          </div>
                        ) : (
                          <>
                            <p className="font-semibold text-base text-emerald-400">
                              ✓ Photo uploaded successfully!
                            </p>
                            <p className="text-sm text-muted-foreground">Click or drag to replace</p>
                          </>
                        )}
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleFileChange(null);
                        }}
                      >
                        <X className="w-4 h-4" />
                        Remove
                      </Button>
                    </div>
                  ) : (
                    <div className="text-center space-y-4">
                      <Upload className="w-14 h-14 mx-auto text-muted-foreground" />
                      <div className="space-y-1">
                        <p className="font-semibold text-base hidden sm:block">Drop your photo here or click to browse</p>
                        <p className="font-semibold text-base sm:hidden">Tap to take a photo or choose from gallery</p>
                        <p className="text-sm text-muted-foreground">JPEG or PNG, max 8 MB</p>
                      </div>
                    </div>
                  )}
                </div>
                {/* AI Quality Scorecard — outside the dropzone to avoid box-in-box nesting */}
                {analysisResult && (
                  <div data-scorecard>
                    <PhotoScorecard
                      scores={analysisResult.scores}
                      tips={analysisResult.tips}
                      processingMs={analysisResult.processingMs}
                      onStyleRecommendation={(styleId) => {
                        const style = presetOptions.find(p => p.id === styleId);
                        if (style) {
                          handlePresetSelect(style);
                          setTimeout(() => scrollToRef(step2Ref), 100);
                        }
                      }}
                    />
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Step 2: Choose Style */}
            <div ref={step2Ref} className="h-full relative">
              <Card className={cn(
                'h-full border-border/50 shadow-xl',
                !photoFile && 'opacity-50 pointer-events-none'
              )}>
                <CardHeader className="space-y-3 pb-6 p-4 sm:p-6 sm:pb-6">
                  <CardTitle className="flex items-center gap-3 text-xl sm:text-2xl">
                    <span
                      className={cn(
                        'flex items-center justify-center w-10 h-10 rounded-full text-base font-bold',
                        currentStep >= 2 ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
                      )}
                    >
                      2
                    </span>
                    Choose Your Style
                  </CardTitle>
                  <CardDescription className="text-sm sm:text-base leading-relaxed">Select an Executive Suite preset or create your own custom style.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6 p-4 pt-0 sm:p-6 sm:pt-0">
                  {isLoadingPresets && (
                    <div className="w-full rounded-lg border border-border/40 bg-muted/30 p-4 text-sm text-muted-foreground">
                      Loading canonical style prompts…
                    </div>
                  )}

                  {presetLoadError && (
                    <div className="w-full rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
                      {presetLoadError}
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                    {presetOptions.map((preset) => (
                      <StylePresetCard
                        key={preset.id}
                        preset={preset}
                        isSelected={selectedPreset?.id === preset.id}
                        onClick={() => handlePresetSelect(preset)}
                        disabled={preset.expansionMode === 'fixed' && isLoadingPresets}
                      />
                    ))}
                  </div>

                  {selectedPreset?.id === 'custom' && (
                    <CustomStyleBuilder
                      params={customStyleParams}
                      onChange={setCustomStyleParams}
                    />
                  )}


                  <HolographicButton
                    onClick={handleGenerate}
                    disabled={!photoFile || (!selectedPreset) || isGenerating || (!stylePrompt.trim() && selectedPreset?.id !== 'custom')}
                    size="lg"
                    className="w-full text-base font-semibold h-14"
                  >
                    <Sparkles className="w-5 h-5 mr-2" />
                    {isGenerating ? 'Creating Your Portrait...' : 'Generate Executive Headshot'}
                  </HolographicButton>

                  {isGenerating && (
                    <div className="space-y-2">
                      <Progress value={generationProgress} className="h-2" />
                      <p className="text-sm text-center text-muted-foreground">
                        Creating your portrait... This may take a minute.
                      </p>
                    </div>
                  )}

                  {error && currentStep < 3 && (
                    <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
                      <p className="text-sm text-destructive">{error}</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Premium Sign-in Overlay - appears after photo upload for non-signed-in users */}
              {photoFile && !isSignedIn && (
                <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/80 backdrop-blur-md rounded-xl">
                  <div className="max-w-md mx-4 p-8 bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl border-2 border-amber-500/40 shadow-2xl text-center space-y-6">
                    {/* Premium badge */}
                    <div className="inline-flex items-center gap-2 px-4 py-2 bg-amber-500/20 rounded-full border border-amber-500/30">
                      <Sparkles className="w-4 h-4 text-amber-400" />
                      <span className="text-sm font-semibold text-amber-300">Exclusive Access</span>
                    </div>

                    <div className="space-y-2">
                      <h3 className="text-2xl font-bold text-white" style={{ fontFamily: "'Playfair Display', serif" }}>
                        Unlock Your Professional Look
                      </h3>
                      <p className="text-slate-400 text-sm leading-relaxed">
                        Sign in to access the Executive Suite styles and transform your photo into a professional headshot.
                      </p>
                    </div>

                    {/* Benefits list */}
                    <div className="text-left space-y-2 py-2">
                      {['AI Quality Scorecard analysis', 'Executive Suite style presets', '2 free headshot generations'].map((benefit, i) => (
                        <div key={i} className="flex items-center gap-2 text-sm text-slate-300">
                          <svg className="w-4 h-4 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                          <span>{benefit}</span>
                        </div>
                      ))}
                    </div>

                    <Button
                      onClick={() => setShowAuthModal(true)}
                      size="lg"
                      className="w-full h-12 bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white font-semibold shadow-lg hover:shadow-amber-500/25"
                    >
                      <Sparkles className="w-4 h-4 mr-2" />
                      Sign In to Continue
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Step 3: Review Results */}
          {variations.length > 0 && (
            <div ref={step3Ref} className="mt-12">
              <Card className="border-border/50 shadow-xl">
                <CardHeader className="space-y-3 pb-8 p-4 sm:p-6 sm:pb-8">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div className="space-y-2">
                      <CardTitle className="flex items-center gap-3 text-xl sm:text-2xl">
                        <span className="flex items-center justify-center w-10 h-10 rounded-full bg-primary text-primary-foreground text-base font-bold">
                          3
                        </span>
                        Your LinkedIn Portrait Gallery
                      </CardTitle>
                      <CardDescription className="text-base">
                        {variations.length === 1
                          ? '1 portrait generated'
                          : `${variations.length} portraits generated`}{' '}
                        {processingMs && `in ${(processingMs / 1000).toFixed(1)}s`}
                      </CardDescription>
                    </div>
                    <Button variant="outline" onClick={handleReset} className="h-11 px-6">
                      Start Over
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-6 p-4 pt-0 sm:p-6 sm:pt-0">
                  <ImageVariationGallery
                    variations={variations}
                    originalImage={photoPreview}
                    onDownload={handleDownloadVariation}
                    onShare={handleShareVariation}
                  />

                  {/* Variation Controls - Mobile-friendly collapsible */}
                  <div className="lg:block">
                    {/* Desktop: always visible */}
                    <div className="hidden lg:block">
                      <VariationControls
                        disabled={isGenerating || isCreatingVariation}
                        isSubmitting={isCreatingVariation}
                        onCreateVariation={handleCreateVariation}
                      />
                    </div>
                    {/* Mobile: collapsible bottom sheet style */}
                    <div className="lg:hidden">
                      <details className="group rounded-2xl border border-border/40 bg-secondary/40 shadow-inner shadow-black/30">
                        <summary className="flex cursor-pointer items-center justify-between p-4 text-foreground list-none">
                          <div className="flex items-center gap-3">
                            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/15 text-primary">
                              <Sparkles className="h-5 w-5" />
                            </div>
                            <div>
                              <p className="text-base font-semibold">Guided Variation Builder</p>
                              <p className="text-xs text-muted-foreground">Tap to customize your next variation</p>
                            </div>
                          </div>
                          <svg className="h-5 w-5 text-muted-foreground transition-transform group-open:rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </summary>
                        <div className="p-4 pt-0">
                          <VariationControls
                            variant="embedded"
                            disabled={isGenerating || isCreatingVariation}
                            isSubmitting={isCreatingVariation}
                            onCreateVariation={handleCreateVariation}
                          />
                        </div>
                      </details>
                    </div>
                  </div>

                  {error && currentStep === 3 && (
                    <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
                      <p className="text-sm text-destructive">{error}</p>
                    </div>
                  )}

                  {shareStatus && (
                    <div className="p-3 bg-muted rounded-lg">
                      <p className="text-sm text-center">{shareStatus}</p>
                    </div>
                  )}

                  <div className="space-y-4 pt-4">
                    <h3 className="text-lg font-semibold">AI-Expanded Prompt</h3>
                    <p className="text-base text-muted-foreground leading-relaxed">
                      This is the detailed prompt sent to the AI model based on your style selection.
                    </p>
                    <div className="p-5 bg-muted/50 rounded-lg">
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">{expandedPrompt}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>

      {showFollowModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="relative w-full max-w-md transform transition-all duration-300 bg-gradient-to-br from-blue-50 to-purple-50 rounded-2xl shadow-2xl border border-white/40">
            <button
              onClick={handleFollowClose}
              className="absolute top-4 right-4 text-gray-500 hover:text-gray-700 transition-colors"
              aria-label="Close follow modal"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <div className="px-8 pt-8 pb-6 text-center space-y-4">
              <div className="w-16 h-16 mx-auto rounded-full bg-white/40 backdrop-blur flex items-center justify-center">
                <svg className="w-8 h-8 text-blue-600" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M4.98 3.5C4.98 4.88 3.88 6 2.5 6S0 4.88 0 3.5 1.12 1 2.5 1 4.98 2.12 4.98 3.5zM.22 8.98h4.56V24H.22zM8.94 8.98h4.37v2.05h.06c.61-1.16 2.1-2.38 4.32-2.38 4.62 0 5.47 3.04 5.47 6.99V24h-4.56v-7.35c0-1.75-.03-4-2.44-4-2.45 0-2.82 1.9-2.82 3.86V24H8.94z" />
                </svg>
              </div>
              <h3 className="text-2xl font-bold text-gray-900">Credits used up</h3>
              <p className="text-sm text-gray-700 leading-relaxed">
                {followMessage || 'You have used both LinkedIn photo credits. Follow Yanqing on LinkedIn to request more.'}
              </p>
              <div className="flex flex-col gap-2">
                <button
                  onClick={handleFollowLink}
                  className="w-full py-3 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-500 transition-colors shadow-lg"
                >
                  Follow on LinkedIn
                </button>
                <button
                  onClick={handleFollowClose}
                  className="w-full py-3 rounded-xl border border-gray-200 text-gray-800 hover:bg-white transition-colors"
                >
                  Maybe later
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        onSuccess={() => {
          setShowAuthModal(false);
          fetchCredits();
        }}
      />
    </div>
  );
};

export const Page = LinkedInPhotoPage;
export default LinkedInPhotoPage;
