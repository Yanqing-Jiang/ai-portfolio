import React, { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Download, Share2, Maximize2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface ImageVariation {
  id: string;
  imageBase64: string;
  imageMimeType: string;
  width: number;
  height: number;
}

interface ImageVariationGalleryProps {
  variations: ImageVariation[];
  originalImage: string | null;
  onDownload: (variationId: string) => void;
  onShare: (variationId: string) => void;
}

export const ImageVariationGallery: React.FC<ImageVariationGalleryProps> = ({
  variations,
  originalImage,
  onDownload,
  onShare,
}) => {
  const [selectedVariation, setSelectedVariation] = useState<string | null>(variations[0]?.id || null);
  const [compareMode, setCompareMode] = useState(false);

  const selectedVar = variations.find((v) => v.id === selectedVariation);

  return (
    <div className="space-y-6">
      {/* Main Display */}
      <Card>
        <CardContent className="p-6">
          {compareMode && originalImage ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-sm font-medium mb-2 text-center">Original</p>
                <img src={originalImage} alt="Original" className="w-full rounded-lg border" />
              </div>
              <div>
                <p className="text-sm font-medium mb-2 text-center">Generated</p>
                {selectedVar && (
                  <div className="relative">
                    <img
                      src={`data:${selectedVar.imageMimeType};base64,${selectedVar.imageBase64}`}
                      alt="Generated"
                      className="w-full rounded-lg border"
                    />
                    <Badge className="absolute top-2 right-2" variant="secondary">
                      {selectedVar.width} x {selectedVar.height}
                    </Badge>
                  </div>
                )}
              </div>
            </div>
          ) : (
            selectedVar && (
              <div className="relative">
                <img
                  src={`data:${selectedVar.imageMimeType};base64,${selectedVar.imageBase64}`}
                  alt="Generated headshot"
                  className="w-full max-w-2xl mx-auto rounded-lg border"
                />
                <Badge className="absolute top-2 right-2" variant="secondary">
                  {selectedVar.width} x {selectedVar.height}
                </Badge>
              </div>
            )
          )}

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-2 justify-center mt-4">
            <Button
              variant={compareMode ? 'default' : 'outline'}
              size="sm"
              onClick={() => setCompareMode(!compareMode)}
              disabled={!originalImage}
            >
              <Maximize2 className="w-4 h-4" />
              {compareMode ? 'Single View' : 'Compare'}
            </Button>
            <Button variant="outline" size="sm" onClick={() => selectedVar && onDownload(selectedVar.id)}>
              <Download className="w-4 h-4" />
              Download
            </Button>
            <Button variant="outline" size="sm" onClick={() => selectedVar && onShare(selectedVar.id)}>
              <Share2 className="w-4 h-4" />
              Share
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Variation Thumbnails */}
      {variations.length > 1 && (
        <div>
          <p className="text-sm font-medium mb-3">All Variations ({variations.length})</p>
          <div
            className="flex gap-4 overflow-x-auto snap-x snap-mandatory pb-2 sm:grid sm:grid-cols-3 sm:overflow-x-visible sm:snap-none sm:pb-0"
            style={{ WebkitOverflowScrolling: 'touch' }}
          >
            {variations.map((variation, index) => (
              <Card
                key={variation.id}
                className={cn(
                  'cursor-pointer transition-all hover:shadow-md shrink-0 w-[45%] snap-center sm:w-auto sm:shrink',
                  selectedVariation === variation.id && 'ring-2 ring-primary ring-offset-2'
                )}
                onClick={() => setSelectedVariation(variation.id)}
              >
                <CardContent className="p-2">
                  <img
                    src={`data:${variation.imageMimeType};base64,${variation.imageBase64}`}
                    alt={`Variation ${index + 1}`}
                    className="w-full rounded border"
                  />
                  <p className="text-xs text-center mt-1 text-muted-foreground">Variation {index + 1}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
