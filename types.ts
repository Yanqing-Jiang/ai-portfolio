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
  // Phase C — schema.org entity-graph density fields. Cited 2026 research
  // (digitalapplied) attributes a 4.8x AI-citation boost to pages connected
  // to 15+ canonical entities. `mentions` lists canonical entity names that
  // appear in the project's body (e.g., "LangGraph", "Claude Agent SDK",
  // "A2UI Protocol"). `about` is the broader topical aboutness (defaults to
  // serviceTags when omitted). Both render as schema.org Thing objects.
  mentions?: string[];
  about?: string[];
  // Phase C — VideoObject support. `videoUrl` already exists above; these
  // extend it for the schema.org VideoObject embed in Article markup.
  // Multi-modal content (text + image + video) gets +156% AI selection rate.
  videoThumbnailUrl?: string;
  videoDurationISO?: string; // ISO 8601 duration, e.g., "PT2M30S"
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
