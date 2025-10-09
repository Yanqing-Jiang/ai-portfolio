export interface Project {
  id: string;
  title: string;
  description: string;
  technologies: string[];
  systemInstruction: string;
  defaultPrompts: string[];
  imageUrl?: string;
  coverUrl?: string;
  link?: string;
  contentHtml?: string;
  gifUrl?: string;
  seoTitle?: string;
  seoDescription?: string;
  seoKeywords?: string[];
  ogImage?: string;
  datePublished?: string;
  dateModified?: string;
  serviceTags?: string[];
  statHighlights?: string[];
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
