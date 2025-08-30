import React, { useState, useRef, useEffect, useCallback } from 'react';

interface SimpleGogginsAudioPlayerProps {
  backendUrl: string;
  isActive: boolean;
  onPlaybackComplete?: () => void;
  onPlaybackError?: (error: string) => void;
}

const SimpleGogginsAudioPlayer = React.forwardRef<
  { playAudio: (text: string) => void; stop: () => void }, 
  SimpleGogginsAudioPlayerProps
>(({ 
  backendUrl, 
  isActive,
  onPlaybackComplete, 
  onPlaybackError 
}, ref) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [volume, setVolume] = useState(1);
  const [status, setStatus] = useState('');
  const [currentText, setCurrentText] = useState<string | null>(null);
  
  const audioRef = useRef<HTMLAudioElement>(null);
  const audioUrlRef = useRef<string | null>(null);

  // Initialize audio element event listeners
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const updateTime = () => {
      setCurrentTime(audio.currentTime);
      if (audio.duration) {
        setProgress((audio.currentTime / audio.duration) * 100);
      }
    };

    const handleLoadedMetadata = () => {
      setDuration(audio.duration);
    };

    const handleCanPlayThrough = () => {
      // Auto-play when audio is fully loaded
      setStatus('🔊 Auto-playing Goggins voice...');
      audio.play().catch(error => {
        console.error('Auto-play failed:', error);
        onPlaybackError?.('Auto-play failed - user interaction may be required');
        setStatus('Click play to start audio');
      });
    };

    const handlePlay = () => {
      setIsPlaying(true);
      setStatus('🔊 Playing Goggins motivation...');
    };

    const handlePause = () => {
      setIsPlaying(false);
      setStatus('⏸️ Paused');
    };

    const handleEnded = () => {
      setIsPlaying(false);
      setProgress(0);
      setCurrentTime(0);
      setStatus('✅ Motivation complete!');
      onPlaybackComplete?.();
    };

    const handleError = () => {
      setIsPlaying(false);
      setIsLoading(false);
      setStatus('❌ Audio playback failed');
      onPlaybackError?.('Audio playback failed');
    };

    audio.addEventListener('timeupdate', updateTime);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('canplaythrough', handleCanPlayThrough);
    audio.addEventListener('play', handlePlay);
    audio.addEventListener('pause', handlePause);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('error', handleError);

    return () => {
      audio.removeEventListener('timeupdate', updateTime);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('canplaythrough', handleCanPlayThrough);
      audio.removeEventListener('play', handlePlay);
      audio.removeEventListener('pause', handlePause);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('error', handleError);
    };
  }, [onPlaybackComplete, onPlaybackError]);

  const playAudio = useCallback(async (text: string) => {
    if (isLoading) return; // Prevent multiple simultaneous requests
    
    setIsLoading(true);
    setStatus('🎵 Generating Goggins voice...');
    setCurrentText(text);
    
    try {
      // Use the simple TTS endpoint to get complete audio file
      const response = await fetch(`${backendUrl}/api/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) {
        throw new Error(`TTS request failed: ${response.statusText}`);
      }

      const blob = await response.blob();
      
      // Clean up old audio URL
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
      }
      
      // Create new audio URL
      const audioUrl = URL.createObjectURL(blob);
      audioUrlRef.current = audioUrl;
      
      if (audioRef.current) {
        audioRef.current.src = audioUrl;
        // Audio will auto-play via the canplaythrough event
      }
      
      setIsLoading(false);
      setStatus('📡 Audio ready, loading...');
      
    } catch (error) {
      console.error('Error generating TTS audio:', error);
      setIsLoading(false);
      setStatus('❌ Failed to generate voice');
      onPlaybackError?.(`Failed to generate audio: ${error}`);
    }
  }, [backendUrl, isLoading, onPlaybackError]);

  const play = useCallback(async () => {
    if (audioRef.current) {
      try {
        await audioRef.current.play();
      } catch (error) {
        console.error('Audio play failed:', error);
        onPlaybackError?.('Audio playback failed');
      }
    }
  }, [onPlaybackError]);

  const pause = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
    }
  }, []);

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    
    setIsPlaying(false);
    setProgress(0);
    setCurrentTime(0);
    setStatus('');
    setCurrentText(null);
    
    // Clean up audio URL
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
  }, []);

  const seek = useCallback((time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time;
    }
  }, []);

  const handleProgressClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!duration) return;
    
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const newTime = (clickX / rect.width) * duration;
    seek(newTime);
  }, [duration, seek]);

  const handleVolumeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseFloat(e.target.value);
    setVolume(newVolume);
    if (audioRef.current) {
      audioRef.current.volume = newVolume;
    }
  }, []);

  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  // Expose methods to parent
  React.useImperativeHandle(ref, () => ({
    playAudio: playAudio,
    stop: stop
  }));

  if (!isActive && !currentText) {
    return null;
  }

  return (
    <div className="bg-gray-800/90 rounded-lg p-4 space-y-3 border border-gray-700/50 backdrop-blur-sm">
      <audio
        ref={audioRef}
        preload="metadata"
        className="hidden"
      />
      
      {/* Goggins Audio Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full overflow-hidden">
          <img 
            src="https://yanqinghot.blob.core.windows.net/public-access/Goggins%20Yelling.jpg" 
            alt="Goggins Voice" 
            className="w-full h-full object-cover"
          />
        </div>
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-white">Goggins Voice</h3>
          <p className="text-xs text-gray-400">
            {status || 'Ready to motivate'}
          </p>
        </div>
        {isLoading && (
          <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        )}
      </div>
      
      {/* Audio Controls - Only show when we have audio */}
      {currentText && !isLoading && (
        <div className="space-y-3">
          {/* Progress Bar */}
          <div className="space-y-1">
            <div 
              className="h-2 bg-gray-700 rounded-full cursor-pointer relative"
              onClick={handleProgressClick}
            >
              <div 
                className="h-full bg-blue-500 rounded-full transition-all duration-100"
                style={{ width: `${progress}%` }}
              />
              {progress > 0 && (
                <div 
                  className="absolute top-1/2 transform -translate-y-1/2 w-4 h-4 bg-blue-500 rounded-full shadow-lg transition-all duration-100"
                  style={{ left: `calc(${progress}% - 8px)` }}
                />
              )}
            </div>
            
            <div className="flex justify-between text-xs text-gray-400">
              <span>{formatTime(currentTime)}</span>
              <span>{formatTime(duration)}</span>
            </div>
          </div>

          {/* Control Buttons */}
          <div className="flex items-center justify-center gap-4">
            <button
              onClick={isPlaying ? pause : play}
              className="flex items-center justify-center w-12 h-12 bg-blue-600 hover:bg-blue-500 rounded-full text-white transition-colors"
              aria-label={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? (
                <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M6 4a1 1 0 011 1v10a1 1 0 11-2 0V5a1 1 0 011-1zM14 4a1 1 0 011 1v10a1 1 0 11-2 0V5a1 1 0 011-1z" clipRule="evenodd" />
                </svg>
              ) : (
                <svg className="w-6 h-6 ml-1" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                </svg>
              )}
            </button>

            {/* Volume Control */}
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M9.383 3.076A1 1 0 0110 4v12a1 1 0 01-1.617.82L4.07 13H2a1 1 0 01-1-1V8a1 1 0 011-1h2.07l4.313-3.82z" clipRule="evenodd" />
              </svg>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={volume}
                onChange={handleVolumeChange}
                className="w-20 h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

SimpleGogginsAudioPlayer.displayName = 'SimpleGogginsAudioPlayer';

export default SimpleGogginsAudioPlayer;