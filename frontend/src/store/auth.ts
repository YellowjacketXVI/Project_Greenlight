import { create } from "zustand";
import { persist } from "zustand/middleware";
import { supabase, type User } from "@/lib/supabase";

type AuthState = {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  checkSession: () => Promise<void>;
  clearError: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isLoading: false,
      error: null,

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const { data, error } = await supabase.auth.signInWithPassword({
            email,
            password,
          });

          if (error) throw error;

          set({
            user: {
              id: data.user!.id,
              email: data.user!.email!,
              display_name: data.user!.user_metadata?.display_name,
            },
            token: data.session!.access_token,
            isLoading: false,
          });
        } catch (error) {
          set({ error: (error as Error).message, isLoading: false });
          throw error;
        }
      },

      signup: async (email: string, password: string, displayName?: string) => {
        set({ isLoading: true, error: null });
        try {
          const { data, error } = await supabase.auth.signUp({
            email,
            password,
            options: {
              data: { display_name: displayName },
            },
          });

          if (error) throw error;

          set({
            user: {
              id: data.user!.id,
              email: data.user!.email!,
              display_name: displayName,
            },
            token: data.session?.access_token || null,
            isLoading: false,
          });
        } catch (error) {
          set({ error: (error as Error).message, isLoading: false });
          throw error;
        }
      },

      logout: async () => {
        set({ isLoading: true });
        try {
          await supabase.auth.signOut();
          set({ user: null, token: null, isLoading: false });
        } catch (error) {
          set({ error: (error as Error).message, isLoading: false });
        }
      },

      checkSession: async () => {
        set({ isLoading: true });
        try {
          const { data } = await supabase.auth.getSession();

          if (data.session) {
            set({
              user: {
                id: data.session.user.id,
                email: data.session.user.email!,
                display_name: data.session.user.user_metadata?.display_name,
              },
              token: data.session.access_token,
              isLoading: false,
            });
          } else {
            set({ user: null, token: null, isLoading: false });
          }
        } catch (error) {
          set({ user: null, token: null, isLoading: false });
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: "morpheus-auth",
      partialize: (state) => ({ token: state.token }),
    }
  )
);

