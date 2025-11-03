import React, { useEffect, useRef, useState } from 'react';
import { StepIndicator } from './StepIndicator';
import { StylePresetCard, STYLE_PRESETS, type StylePreset } from './StylePresetCard';
import { ImageVariationGallery, type ImageVariation } from './ImageVariationGallery';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Upload, X, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { configService } from '@/services/config';

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

  const scrollToRef = (ref: React.RefObject<HTMLDivElement>) => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
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

  const handlePresetSelect = (preset: StylePreset) => {
    setSelectedPreset(preset);
    setStylePrompt(preset.prompt);
    setError(null);
  };

  const handleGenerate = async () => {
    if (!photoFile || !stylePrompt.trim()) return;

    setIsGenerating(true);
    setError(null);
    setShareStatus(null);
    setExpandedPrompt('');
    setVariations([]);
    setProcessingMs(null);
    setGenerationProgress(0);

    // Simulate progress
    const progressInterval = setInterval(() => {
      setGenerationProgress((prev) => Math.min(prev + 10, 90));
    }, 500);

    const formData = new FormData();
    formData.append('photo', photoFile);
    formData.append('prompt', stylePrompt.trim());

      try {
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
        const normalizedVariations: ImageVariation[] = rawVariations
          .map((variation: any, index: number) => {
            const id = typeof variation?.id === 'string' && variation.id.length > 0
              ? variation.id
              : `var-${index + 1}`;
            const imageBase64 =
              typeof variation?.image_base64 === 'string' && variation.image_base64.length > 0
                ? variation.image_base64
                : typeof variation?.imageBase64 === 'string'
                  ? variation.imageBase64
                  : '';
            const imageMimeType =
              typeof variation?.image_mime_type === 'string' && variation.image_mime_type.length > 0
                ? variation.image_mime_type
                : typeof variation?.imageMimeType === 'string' && variation.imageMimeType.length > 0
                  ? variation.imageMimeType
                  : 'image/png';

            return {
              id,
              imageBase64,
              imageMimeType,
              width: Number.isFinite(variation?.width) ? variation.width : 0,
              height: Number.isFinite(variation?.height) ? variation.height : 0,
            };
          })
          .filter((variation: ImageVariation) => variation.imageBase64.length > 0);

        setVariations(normalizedVariations);

        if (typeof payload.processing_ms === 'number') {
          setProcessingMs(payload.processing_ms);
        }
      setGenerationProgress(100);
      setCurrentStep(3);
      setTimeout(() => scrollToRef(step3Ref), 100);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unable to generate headshot right now.';
        console.error('LinkedIn photo generation failed:', err);
        setError(message);
      } finally {
        clearInterval(progressInterval);
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
    setCurrentStep(1);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="relative min-h-screen overflow-hidden" style={LINKEDIN_PHOTO_THEME}>
      <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950" />
      <div className="pointer-events-none absolute -top-40 right-[-25%] h-[520px] w-[520px] rounded-full bg-cyan-500/15 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-48 left-[-20%] h-[560px] w-[560px] rounded-full bg-blue-500/10 blur-3xl" />
      <div className="relative z-10 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto space-y-8 text-foreground">
          {/* Header */}
          <header className="text-center space-y-3">
            <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-foreground">AI Headshot Generator</h1>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
              Transform your photo into a professional LinkedIn headshot. Upload, choose your style, and get multiple variations.
            </p>
          </header>

          {/* Step Indicator */}
          <StepIndicator steps={STEPS} currentStep={currentStep} />

          <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
            {/* Step 1: Upload Photo */}
            <Card className="h-full">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="flex items-center justify-center w-8 h-8 rounded-full bg-primary text-primary-foreground text-sm font-bold">
                    1
                  </span>
                  Upload Photo
                </CardTitle>
                <CardDescription>
                  Upload a clear photo. Best results with good lighting and plain background.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div
                  className={cn(
                    'border-2 border-dashed rounded-lg p-8 transition-all cursor-pointer',
                    isDragging ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50',
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
                      <img src={photoPreview} alt="Preview" className="w-32 h-32 object-cover rounded-lg border" />
                      <div className="flex-1 text-center md:text-left">
                        <p className="font-medium mb-1">Photo uploaded successfully!</p>
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
                    <div className="text-center space-y-2">
                      <Upload className="w-12 h-12 mx-auto text-muted-foreground" />
                      <div>
                        <p className="font-medium">Drop your photo here or click to browse</p>
                        <p className="text-sm text-muted-foreground">JPEG or PNG, max 8 MB</p>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Step 2: Choose Style */}
            <div ref={step2Ref} className="h-full">
              <Card className={cn('h-full', !photoFile && 'opacity-50 pointer-events-none')}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <span
                      className={cn(
                        'flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold',
                        currentStep >= 2 ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
                      )}
                    >
                      2
                    </span>
                    Choose Your Style
                  </CardTitle>
                  <CardDescription>Select a preset or write your own custom style description.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                    {STYLE_PRESETS.map((preset) => (
                      <StylePresetCard
                        key={preset.id}
                        preset={preset}
                        isSelected={selectedPreset?.id === preset.id}
                        onClick={() => handlePresetSelect(preset)}
                      />
                    ))}
                  </div>

                  {selectedPreset?.id === 'custom' && (
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Custom Style Description</label>
                      <textarea
                        value={stylePrompt}
                        onChange={(e) => setStylePrompt(e.target.value)}
                        placeholder="Describe your desired style, background, lighting, and professional vibe..."
                        rows={4}
                        className="w-full resize-none rounded-lg border border-input bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                      />
                    </div>
                  )}

                  {selectedPreset && selectedPreset.id !== 'custom' && (
                    <div className="p-4 bg-muted/50 rounded-lg">
                      <p className="text-sm font-medium mb-1">Selected style prompt:</p>
                      <p className="text-sm text-muted-foreground">{stylePrompt}</p>
                    </div>
                  )}

                  <Button
                    onClick={handleGenerate}
                    disabled={!photoFile || !stylePrompt.trim() || isGenerating}
                    size="lg"
                    className="w-full"
                  >
                    <Sparkles className="w-5 h-5" />
                    {isGenerating ? 'Generating Variations...' : 'Generate Professional Headshots'}
                  </Button>

                  {isGenerating && (
                    <div className="space-y-2">
                      <Progress value={generationProgress} className="h-2" />
                      <p className="text-sm text-center text-muted-foreground">
                        Creating your headshots... This may take a minute.
                      </p>
                    </div>
                  )}

                  {error && (
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
            <div ref={step3Ref} className="mt-8">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <CardTitle className="flex items-center gap-2">
                        <span className="flex items-center justify-center w-8 h-8 rounded-full bg-primary text-primary-foreground text-sm font-bold">
                          3
                        </span>
                        Your Professional Headshots
                      </CardTitle>
                      <CardDescription>
                        {variations.length} variations generated{' '}
                        {processingMs && `in ${(processingMs / 1000).toFixed(1)}s`}
                      </CardDescription>
                    </div>
                    <Button variant="outline" onClick={handleReset}>
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

                  {shareStatus && (
                    <div className="p-3 bg-muted rounded-lg">
                      <p className="text-sm text-center">{shareStatus}</p>
                    </div>
                  )}

                  <div className="space-y-3">
                    <h3 className="font-semibold">AI-Expanded Prompt</h3>
                    <p className="text-sm text-muted-foreground">
                      This is the detailed prompt sent to the AI model based on your style selection.
                    </p>
                    <div className="p-4 bg-muted/50 rounded-lg">
                      <p className="text-sm whitespace-pre-wrap">{expandedPrompt}</p>
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
