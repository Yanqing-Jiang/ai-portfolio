export interface Project {
  id: string;
  canonicalId?: string;
  noindex?: boolean;
  title: string;
  description: string;
  cardDescription?: string;
  technologies: string[];
  systemInstruction: string;
  defaultPrompts: string[];
  imageUrl?: string;
  coverUrl?: string;
  link?: string;
  contentHtml?: string;
  gifUrl?: string;
  videoUrl?: string;
  posterUrl?: string;
  seoTitle?: string;
  seoDescription?: string;
  seoKeywords?: string[];
  ogImage?: string;
  datePublished?: string;
  dateModified?: string;
  serviceTags?: string[];
  statHighlights?: string[];
  linkText?: string; // SEO-friendly anchor text, e.g., "Agent-to-UI case study"
  primaryMetricValue?: {
    label?: string;
    value: number;
    unitText?: string;
  };
}

export interface ProjectYear {
  year: number;
  subtitle?: string;
  label?: string;
  hiddenOnLanding?: boolean;
  projects: Project[];
}

export interface ChatMessage {
  id:string;
  role: 'user' | 'model' | 'audio';
  text?: string;
  audioUrl?: string;
}
