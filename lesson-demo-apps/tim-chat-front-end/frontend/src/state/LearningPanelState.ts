import { create } from 'zustand';

interface Resource {
  title: string;
  description: string;
  url: string;
  type: 'documentation' | 'tutorial' | 'example';
}

interface CodeExample {
  title: string;
  description: string;
  code: string;
  language: string;
}

interface EnrichmentContent {
  type: 'fun_fact' | 'investigation_tip' | 'learning_path';
  title: string;
  content: string;
  relatedLinks?: string[];
}

interface LearningPanelState {
  topic: string;
  resources: Resource[];
  examples: CodeExample[];
  enrichments: EnrichmentContent[];
  isFirstLoad: boolean;
  setTopic: (topic: string) => void;
  setResources: (resources: Resource[]) => void;
  setExamples: (examples: CodeExample[]) => void;
  setEnrichments: (enrichments: EnrichmentContent[]) => void;
  setIsFirstLoad: (isFirstLoad: boolean) => void;
  clearContent: () => void;
}

// Create the store
export const useLearningPanelStore = create<LearningPanelState>((set) => ({
  topic: '',
  resources: [],
  examples: [],
  enrichments: [],
  isFirstLoad: true,
  setTopic: (topic) => set({ topic }),
  setResources: (resources) => set({ resources }),
  setExamples: (examples) => set({ examples }),
  setEnrichments: (enrichments) => set({ enrichments }),
  setIsFirstLoad: (isFirstLoad) => set({ isFirstLoad }),
  clearContent: () => set({ topic: '', resources: [], examples: [], enrichments: [] })
}));

// Add cleanup on hot reload
if (module.hot) {
  module.hot.dispose(() => {
    useLearningPanelStore.getState().clearContent();
  });
} 