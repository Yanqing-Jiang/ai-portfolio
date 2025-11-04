import React, { useEffect, useRef, useState } from 'react';
import { StepIndicator } from './StepIndicator';
import { StylePresetCard, INITIAL_STYLE_PRESETS, type StylePreset } from './StylePresetCard';
import { ImageVariationGallery, type ImageVariation } from './ImageVariationGallery';
import { VariationControls, type VariationRequestOptions } from './VariationControls';
import { CustomStyleBuilder, buildCustomPromptFromParams, type CustomStyleParams } from './CustomStyleBuilder';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Upload, X, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { configService } from '@/services/config';
import { apiService } from '@/services/apiService';

interface LinkedInPhotoPageProps {
  apiPath?: string;
}

const STEPS = [
  { number: 1, label: 'Upload Photo' },
  { number: 2, label: 'Choose Style' },
  { number: 3, label: 'Review Results' },
];

const LINKEDIN_PHOTO_THEME: React.CSSProperties = {
  '--background': '222 47% 7%',
  '--foreground': '210 40% 96%',
  '--card': '222 47% 11%',
  '--card-foreground': '210 40% 96%',
  '--popover': '222 47% 12%',
  '--popover-foreground': '210 40% 96%',
  '--primary': '199 89% 63%',
  '--primary-foreground': '210 40% 98%',
  '--secondary': '222 30% 18%',
  '--secondary-foreground': '210 40% 96%',
  '--muted': '217 28% 20%',
  '--muted-foreground': '214 20% 72%',
  '--accent': '199 89% 63%',
  '--accent-foreground': '222 47% 12%',
  '--destructive': '0 62.8% 45%',
  '--destructive-foreground': '210 40% 98%',
  '--border': '222 32% 24%',
  '--input': '222 32% 24%',
  '--ring': '199 89% 63%',
};

const VARIATION_API_PATH = '/api/linkedin-photo/variation';

const LinkedInPhotoPage: React.FC<LinkedInPhotoPageProps> = ({ apiPath = '/api/linkedin-photo/generate' }) => {
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

  const fileInputRef = useRef<HTMLInputElement>(null);
  const step2Ref = useRef<HTMLDivElement>(null);
  const step3Ref = useRef<HTMLDivElement>(null);
  const backendBaseRef = useRef(configService.getBackendUrl().replace(/\/$/, ''));

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

        const targetUrl = `${backendBaseRef.current}/api/linkedin-photo/prompts`;
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

  const scrollToRef = (ref: React.RefObject<HTMLDivElement>) => {
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

  const handleFileChange = (file: File | null) => {
    setError(null);
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
    setCurrentStep(2);
    setTimeout(() => scrollToRef(step2Ref), 100);
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
      const targetUrl = VARIATION_API_PATH.startsWith('http')
        ? VARIATION_API_PATH
        : `${backendBaseRef.current}${VARIATION_API_PATH.startsWith('/') ? '' : '/'}${VARIATION_API_PATH}`;

      const response = await fetch(targetUrl, {
        method: 'POST',
        body: formData,
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

      setTimeout(() => scrollToRef(step3Ref), 100);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to create a variation right now.';
      console.error('LinkedIn photo variation failed:', err);
      setError(message);
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

      const targetUrl = apiPath.startsWith('http')
        ? apiPath
        : `${backendBaseRef.current}${apiPath.startsWith('/') ? '' : '/'}${apiPath}`;

      const response = await fetch(targetUrl, {
        method: 'POST',
        body: formData,
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
      setGenerationProgress(100);
      setCurrentStep(3);
      setTimeout(() => scrollToRef(step3Ref), 100);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to generate headshot right now.';
      console.error('LinkedIn photo generation failed:', err);
      setError(message);
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
    <div className="relative min-h-screen overflow-hidden" style={LINKEDIN_PHOTO_THEME}>
      <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950" />
      <div className="pointer-events-none absolute -top-40 right-[-25%] h-[520px] w-[520px] rounded-full bg-cyan-500/15 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-48 left-[-20%] h-[560px] w-[560px] rounded-full bg-blue-500/10 blur-3xl" />
      <div className="relative z-10 py-16 sm:py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto space-y-12 text-foreground">
          {/* Header */}
          <header className="text-center space-y-6 mb-4">
            <div className="space-y-4">
              <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-foreground leading-[1.1]">
                LinkedIn Profile Picture Generator
              </h1>
              <p className="text-xl sm:text-2xl text-muted-foreground/90 max-w-3xl mx-auto font-light leading-relaxed">
                Transform your photo into a professional LinkedIn profile picture.
              </p>
            </div>
          </header>

          {/* Step Indicator */}
          <StepIndicator steps={STEPS} currentStep={currentStep} />

          <div className="grid gap-8 lg:grid-cols-2 lg:items-start">
            {/* Step 1: Upload Photo */}
            <Card className="h-full border-border/50 shadow-xl">
              <CardHeader className="space-y-3 pb-6">
                <CardTitle className="flex items-center gap-3 text-2xl">
                  <span className="flex items-center justify-center w-10 h-10 rounded-full bg-primary text-primary-foreground text-base font-bold">
                    1
                  </span>
                  Upload Photo
                </CardTitle>
                <CardDescription className="text-base leading-relaxed">
                  Upload a clear photo. Best results with good lighting and plain background.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div
                  className={cn(
                    'border-2 border-dashed rounded-xl p-10 transition-all cursor-pointer',
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
                    accept="image/jpeg,image/png"
                    onChange={handleInputChange}
                    className="hidden"
                  />
                  {photoPreview ? (
                    <div className="flex flex-col md:flex-row items-center gap-6">
                      <img src={photoPreview} alt="Preview" className="w-32 h-32 object-cover rounded-xl border shadow-md" />
                      <div className="flex-1 text-center md:text-left space-y-1">
                        <p className="font-semibold text-base">Photo uploaded successfully!</p>
                        <p className="text-sm text-muted-foreground">Click or drag to replace</p>
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
                        <p className="font-semibold text-base">Drop your photo here or click to browse</p>
                        <p className="text-sm text-muted-foreground">JPEG or PNG, max 8 MB</p>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Step 2: Choose Style */}
            <div ref={step2Ref} className="h-full">
              <Card className={cn('h-full border-border/50 shadow-xl', !photoFile && 'opacity-50 pointer-events-none')}>
                <CardHeader className="space-y-3 pb-6">
                  <CardTitle className="flex items-center gap-3 text-2xl">
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
                  <CardDescription className="text-base leading-relaxed">Select a preset or write your own custom style description.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
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


                  <Button
                    onClick={handleGenerate}
                    disabled={!photoFile || (!selectedPreset) || isGenerating || (!stylePrompt.trim() && selectedPreset?.id !== 'custom')}
                    size="lg"
                    className="w-full text-base font-semibold h-14"
                  >
                    <Sparkles className="w-5 h-5" />
                    {isGenerating ? 'Creating Your Portrait...' : 'Generate LinkedIn Headshot'}
                  </Button>

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
            </div>
          </div>

          {/* Step 3: Review Results */}
          {variations.length > 0 && (
            <div ref={step3Ref} className="mt-12">
              <Card className="border-border/50 shadow-xl">
                <CardHeader className="space-y-3 pb-8">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div className="space-y-2">
                      <CardTitle className="flex items-center gap-3 text-2xl">
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
                <CardContent className="space-y-6">
                  <ImageVariationGallery
                    variations={variations}
                    originalImage={photoPreview}
                    onDownload={handleDownloadVariation}
                    onShare={handleShareVariation}
                  />

                  <VariationControls
                    disabled={isGenerating || isCreatingVariation}
                    isSubmitting={isCreatingVariation}
                    onCreateVariation={handleCreateVariation}
                  />

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
    </div>
  );
};

export const Page = LinkedInPhotoPage;
export default LinkedInPhotoPage;
