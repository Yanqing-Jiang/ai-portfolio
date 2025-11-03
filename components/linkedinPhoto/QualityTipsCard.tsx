import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronUp, Lightbulb } from 'lucide-react';

export const QualityTipsCard: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <Card className="bg-muted/50 border-muted">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Lightbulb className="w-5 h-5 text-primary" />
            <CardTitle className="text-base">Photo Quality Tips</CardTitle>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="h-8 w-8 p-0"
          >
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </Button>
        </div>
        {!isExpanded && (
          <CardDescription className="text-xs">Click to see tips for best results</CardDescription>
        )}
      </CardHeader>

      {isExpanded && (
        <CardContent className="pt-0 space-y-3">
          <div className="text-sm space-y-2">
            <div className="flex gap-2">
              <span className="text-primary font-semibold">✓</span>
              <span>
                <strong>Good lighting:</strong> Use natural light or well-lit indoor space
              </span>
            </div>
            <div className="flex gap-2">
              <span className="text-primary font-semibold">✓</span>
              <span>
                <strong>Plain background:</strong> Solid or simple backdrop works best
              </span>
            </div>
            <div className="flex gap-2">
              <span className="text-primary font-semibold">✓</span>
              <span>
                <strong>Clear focus:</strong> Face should be sharp and in focus
              </span>
            </div>
            <div className="flex gap-2">
              <span className="text-primary font-semibold">✓</span>
              <span>
                <strong>Head and shoulders:</strong> Frame from chest up for professional look
              </span>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  );
};
