import React, { useEffect, useRef, useState } from 'react';
import SectionShell from '../SectionShell';
import { HOMER_THEME } from '../theme';

// Function: MorningRoutineVideo — Plan §5.0.
// 60-second silent autoplay-on-scroll Mac Mini routine recording.
// Sprint 3 will drop the WebM/MP4 assets into public/homer/morning-routine.{webm,mp4};
// Sprint 1 ships a styled placeholder with the autoplay-on-intersect logic
// already wired so we can swap in the asset without touching the layout.

export const MorningRoutineVideo: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [hasSrc, setHasSrc] = useState(false);

  useEffect(() => {
    // Probe whether the video asset is present. If a HEAD on the .webm asset
    // succeeds we wire it up; otherwise we leave the placeholder in place.
    fetch('/homer/morning-routine.webm', { method: 'HEAD' })
      .then((r) => setHasSrc(r.ok))
      .catch(() => setHasSrc(false));
  }, []);

  useEffect(() => {
    if (!hasSrc || !videoRef.current) return;
    const el = videoRef.current;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) el.play().catch(() => {});
        else el.pause();
      },
      { threshold: 0.4 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [hasSrc]);

  return (
    <SectionShell
      id="morning-routine"
      eyebrow="60-second routine"
      title="What an autonomous morning looks like."
      subtitle="No audio. Captions only. One Mac Mini, eight agents, twelve scheduled jobs. Recorded straight from the production daemon."
    >
      <div
        className="relative aspect-video rounded-lg overflow-hidden border"
        style={{ borderColor: HOMER_THEME.divider, background: HOMER_THEME.bgSoft }}
      >
        {hasSrc ? (
          <video
            ref={videoRef}
            muted
            playsInline
            loop
            preload="metadata"
            poster="/homer/morning-routine-poster.jpg"
            className="w-full max-w-full h-full object-cover"
          >
            <source src="/homer/morning-routine.webm" type="video/webm" />
            <source src="/homer/morning-routine.mp4" type="video/mp4" />
          </video>
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <div
              className="text-xs tracking-[0.32em] uppercase"
              style={{ fontFamily: HOMER_THEME.fontMono, color: HOMER_THEME.accent }}
            >
              [ video lands in Sprint 3 ]
            </div>
          </div>
        )}
      </div>
    </SectionShell>
  );
};

export default MorningRoutineVideo;
