import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { signIn, signOut, fetchAuthSession } from 'aws-amplify/auth'

interface AuthState {
  token: string | null
  email: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshToken: () => Promise<string | null>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, _get) => ({
      token: null,
      email: null,

      login: async (email, password) => {
        await signIn({ username: email, password })
        const session = await fetchAuthSession()
        const token = session.tokens?.idToken?.toString() ?? null
        set({ token, email })
      },

      logout: async () => {
        await signOut()
        set({ token: null, email: null })
      },

      refreshToken: async () => {
        try {
          const session = await fetchAuthSession({ forceRefresh: true })
          const token = session.tokens?.idToken?.toString() ?? null
          set({ token })
          return token
        } catch {
          set({ token: null, email: null })
          return null
        }
      },
    }),
    { name: 'ebook-admin-auth', partialize: (s) => ({ token: s.token, email: s.email }) },
  ),
)
