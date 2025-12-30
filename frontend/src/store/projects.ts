import { create } from "zustand";
import { supabase, type Project, type Outline } from "@/lib/supabase";

type ProjectsState = {
  projects: Project[];
  currentProject: Project | null;
  outlines: Outline[];
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchProjects: () => Promise<void>;
  createProject: (title: string, prompt: string, genre?: string) => Promise<Project>;
  selectProject: (id: string) => Promise<void>;
  updateProject: (id: string, updates: Partial<Project>) => Promise<void>;
  fetchOutlines: (projectId: string) => Promise<void>;
  clearError: () => void;
};

export const useProjectsStore = create<ProjectsState>((set, get) => ({
  projects: [],
  currentProject: null,
  outlines: [],
  isLoading: false,
  error: null,

  fetchProjects: async () => {
    set({ isLoading: true, error: null });
    try {
      const { data, error } = await supabase
        .from("morphwrit_projects")
        .select("*")
        .order("updated_at", { ascending: false });

      if (error) throw error;

      set({ projects: data || [], isLoading: false });
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
    }
  },

  createProject: async (title: string, prompt: string, genre?: string) => {
    set({ isLoading: true, error: null });
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Not authenticated");

      const { data, error } = await supabase
        .from("morphwrit_projects")
        .insert({
          user_id: user.id,
          title,
          prompt,
          genre,
          status: "draft",
        })
        .select()
        .single();

      if (error) throw error;

      set((state) => ({
        projects: [data, ...state.projects],
        currentProject: data,
        isLoading: false,
      }));

      return data;
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
      throw error;
    }
  },

  selectProject: async (id: string) => {
    set({ isLoading: true, error: null });
    try {
      const { data, error } = await supabase
        .from("morphwrit_projects")
        .select("*")
        .eq("id", id)
        .single();

      if (error) throw error;

      set({ currentProject: data, isLoading: false });

      // Also fetch outlines
      await get().fetchOutlines(id);
    } catch (error) {
      set({ error: (error as Error).message, isLoading: false });
    }
  },

  updateProject: async (id: string, updates: Partial<Project>) => {
    try {
      const { data, error } = await supabase
        .from("morphwrit_projects")
        .update(updates)
        .eq("id", id)
        .select()
        .single();

      if (error) throw error;

      set((state) => ({
        projects: state.projects.map((p) => (p.id === id ? data : p)),
        currentProject: state.currentProject?.id === id ? data : state.currentProject,
      }));
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  fetchOutlines: async (projectId: string) => {
    try {
      const { data, error } = await supabase
        .from("morphwrit_outlines")
        .select("*")
        .eq("project_id", projectId)
        .order("layer");

      if (error) throw error;

      set({ outlines: data || [] });
    } catch (error) {
      set({ error: (error as Error).message });
    }
  },

  clearError: () => set({ error: null }),
}));

