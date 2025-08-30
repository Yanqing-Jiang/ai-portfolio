export interface Project {
  id: string;
  title: string;
  description: string;
  technologies: string[];
  systemInstruction: string;
  defaultPrompts: string[];
  imageUrl?: string;
  coverUrl?: string;
  gifUrl?: string;
}

export interface ProjectYear {
  year: number;
  subtitle?: string;
  projects: Project[];
}

export interface ChatMessage {
  id:string;
  role: 'user' | 'model' | 'audio';
  text?: string;
  audioUrl?: string;
}