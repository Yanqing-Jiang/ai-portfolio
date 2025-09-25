import React from 'react';
import { Player } from '@lottiefiles/react-lottie-player';

// Simple pulse animation data (inline JSON for performance)
const pulseAnimationData = {
  "v": "5.7.4",
  "fr": 30,
  "ip": 0,
  "op": 60,
  "w": 100,
  "h": 100,
  "nm": "Pulse",
  "ddd": 0,
  "assets": [],
  "layers": [
    {
      "ddd": 0,
      "ind": 1,
      "ty": 4,
      "nm": "Circle",
      "sr": 1,
      "ks": {
        "o": {"a": 0, "k": 100},
        "r": {"a": 0, "k": 0},
        "p": {"a": 0, "k": [50, 50, 0]},
        "a": {"a": 0, "k": [0, 0, 0]},
        "s": {
          "a": 1,
          "k": [
            {"i": {"x": [0.42], "y": [1]}, "o": {"x": [0.58], "y": [0]}, "t": 0, "s": [0]},
            {"i": {"x": [0.42], "y": [1]}, "o": {"x": [0.58], "y": [0]}, "t": 30, "s": [120]},
            {"t": 60, "s": [0]}
          ]
        }
      },
      "ao": 0,
      "shapes": [
        {
          "ty": "gr",
          "it": [
            {
              "d": 1,
              "ty": "el",
              "s": {"a": 0, "k": [40, 40]},
              "p": {"a": 0, "k": [0, 0]},
              "nm": "Ellipse Path 1",
              "mn": "ADBE Vector Shape - Ellipse"
            },
            {
              "ty": "fl",
              "c": {"a": 0, "k": [0.23, 0.51, 0.96, 0.3]},
              "o": {"a": 0, "k": 100},
              "r": 1,
              "bm": 0,
              "nm": "Fill 1",
              "mn": "ADBE Vector Graphic - Fill"
            }
          ]
        }
      ],
      "ip": 0,
      "op": 60,
      "st": 0,
      "bm": 0
    }
  ]
};

// Glow animation data
const glowAnimationData = {
  "v": "5.7.4",
  "fr": 30,
  "ip": 0,
  "op": 90,
  "w": 100,
  "h": 100,
  "nm": "Glow",
  "ddd": 0,
  "assets": [],
  "layers": [
    {
      "ddd": 0,
      "ind": 1,
      "ty": 4,
      "nm": "Glow Circle",
      "sr": 1,
      "ks": {
        "o": {
          "a": 1,
          "k": [
            {"i": {"x": [0.42], "y": [1]}, "o": {"x": [0.58], "y": [0]}, "t": 0, "s": [30]},
            {"i": {"x": [0.42], "y": [1]}, "o": {"x": [0.58], "y": [0]}, "t": 45, "s": [80]},
            {"t": 90, "s": [30]}
          ]
        },
        "r": {"a": 0, "k": 0},
        "p": {"a": 0, "k": [50, 50, 0]},
        "a": {"a": 0, "k": [0, 0, 0]},
        "s": {
          "a": 1,
          "k": [
            {"i": {"x": [0.42], "y": [1]}, "o": {"x": [0.58], "y": [0]}, "t": 0, "s": [100]},
            {"i": {"x": [0.42], "y": [1]}, "o": {"x": [0.58], "y": [0]}, "t": 45, "s": [110]},
            {"t": 90, "s": [100]}
          ]
        }
      },
      "ao": 0,
      "shapes": [
        {
          "ty": "gr",
          "it": [
            {
              "d": 1,
              "ty": "el",
              "s": {"a": 0, "k": [60, 60]},
              "p": {"a": 0, "k": [0, 0]},
              "nm": "Ellipse Path 1",
              "mn": "ADBE Vector Shape - Ellipse"
            },
            {
              "ty": "fl",
              "c": {"a": 0, "k": [0.23, 0.51, 0.96, 1]},
              "o": {"a": 0, "k": 100},
              "r": 1,
              "bm": 0,
              "nm": "Fill 1",
              "mn": "ADBE Vector Graphic - Fill"
            }
          ]
        }
      ],
      "ip": 0,
      "op": 90,
      "st": 0,
      "bm": 0
    }
  ]
};

interface PulseAnimationProps {
  color?: string;
  size?: number;
  speed?: number;
  className?: string;
}

export const PulseAnimation: React.FC<PulseAnimationProps> = ({
  color = '#3b82f6',
  size = 60,
  speed = 1,
  className = ''
}) => {
  // Modify animation data color dynamically
  const modifiedData = {
    ...pulseAnimationData,
    layers: pulseAnimationData.layers.map(layer => ({
      ...layer,
      shapes: layer.shapes?.map(shape => ({
        ...shape,
        it: shape.it?.map(item => {
          if (item.ty === 'fl') {
            // Convert hex color to RGB array
            const hex = color.replace('#', '');
            const r = parseInt(hex.substr(0, 2), 16) / 255;
            const g = parseInt(hex.substr(2, 2), 16) / 255;
            const b = parseInt(hex.substr(4, 2), 16) / 255;
            return {
              ...item,
              c: { a: 0, k: [r, g, b, 0.3] }
            };
          }
          return item;
        })
      }))
    }))
  };

  return (
    <div className={`pulse-animation ${className}`}>
      <Player
        autoplay
        loop
        src={modifiedData}
        style={{ height: `${size}px`, width: `${size}px` }}
        speed={speed}
        className="pointer-events-none"
      />
    </div>
  );
};

interface GlowAnimationProps {
  color?: string;
  size?: number;
  speed?: number;
  intensity?: 'low' | 'medium' | 'high';
  className?: string;
}

export const GlowAnimation: React.FC<GlowAnimationProps> = ({
  color = '#3b82f6',
  size = 80,
  speed = 1,
  intensity = 'medium',
  className = ''
}) => {
  const intensityMap = {
    low: 0.2,
    medium: 0.5,
    high: 0.8
  };

  // Modify animation data color and intensity dynamically
  const modifiedData = {
    ...glowAnimationData,
    layers: glowAnimationData.layers.map(layer => ({
      ...layer,
      shapes: layer.shapes?.map(shape => ({
        ...shape,
        it: shape.it?.map(item => {
          if (item.ty === 'fl') {
            // Convert hex color to RGB array
            const hex = color.replace('#', '');
            const r = parseInt(hex.substr(0, 2), 16) / 255;
            const g = parseInt(hex.substr(2, 2), 16) / 255;
            const b = parseInt(hex.substr(4, 2), 16) / 255;
            return {
              ...item,
              c: { a: 0, k: [r, g, b, intensityMap[intensity]] }
            };
          }
          return item;
        })
      }))
    }))
  };

  return (
    <div className={`glow-animation ${className}`}>
      <Player
        autoplay
        loop
        src={modifiedData}
        style={{ height: `${size}px`, width: `${size}px` }}
        speed={speed}
        className="pointer-events-none absolute inset-0"
      />
    </div>
  );
};

// Ripple effect for data flow
interface RippleAnimationProps {
  color?: string;
  size?: number;
  speed?: number;
  className?: string;
}

export const RippleAnimation: React.FC<RippleAnimationProps> = ({
  color = '#10b981',
  size = 40,
  speed = 1.5,
  className = ''
}) => {
  return (
    <div className={`ripple-animation ${className} relative`}>
      {[0, 1, 2].map((index) => (
        <div
          key={index}
          className="absolute inset-0 rounded-full animate-ping"
          style={{
            backgroundColor: color,
            opacity: 0.3 - index * 0.1,
            animationDelay: `${index * 0.5}s`,
            animationDuration: `${2 / speed}s`,
            width: `${size}px`,
            height: `${size}px`,
          }}
        />
      ))}
    </div>
  );
};

// Success burst animation
export const SuccessBurstAnimation: React.FC<{
  color?: string;
  size?: number;
  className?: string;
}> = ({
  color = '#10b981',
  size = 50,
  className = ''
}) => {
  return (
    <div className={`success-burst ${className} relative`}>
      {[...Array(8)].map((_, index) => (
        <div
          key={index}
          className="absolute w-1 h-4 bg-current animate-pulse"
          style={{
            color,
            transform: `rotate(${index * 45}deg) translateY(-${size / 2}px)`,
            transformOrigin: 'bottom center',
            animationDelay: `${index * 0.1}s`,
            animationDuration: '0.8s',
          }}
        />
      ))}
      <div
        className="absolute inset-0 rounded-full animate-bounce"
        style={{
          backgroundColor: color,
          width: `${size / 3}px`,
          height: `${size / 3}px`,
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
        }}
      />
    </div>
  );
};