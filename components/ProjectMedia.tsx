import React, { useState } from 'react';

interface ProjectMediaProps {
  src: string;
  videoUrl?: string;
  posterUrl?: string;
  alt: string;
  className?: string;
  style?: React.CSSProperties;
  loading?: 'lazy' | 'eager';
}

const ProjectMedia: React.FC<ProjectMediaProps> = ({
  src,
  videoUrl,
  posterUrl,
  alt,
  className,
  style,
  loading,
}) => {
  const [videoFailed, setVideoFailed] = useState(false);

  const imgSrc = posterUrl || src;

  if (!imgSrc && !videoUrl) return null;

  if (videoUrl && !videoFailed) {
    return (
      <video
        autoPlay
        muted
        loop
        playsInline
        poster={posterUrl}
        className={className}
        style={style}
        aria-label={alt}
        onError={() => setVideoFailed(true)}
      >
        <source src={videoUrl} type="video/webm" />
        <source src={videoUrl.replace(/\.webm$/, '.mp4')} type="video/mp4" />
        <img src={imgSrc} alt={alt} className={className} style={style} loading={loading} />
      </video>
    );
  }

  return (
    <img
      src={imgSrc}
      alt={alt}
      className={className}
      style={style}
      loading={loading}
    />
  );
};

export default ProjectMedia;
