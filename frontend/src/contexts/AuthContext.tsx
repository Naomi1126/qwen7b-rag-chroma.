import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface User {
  id: string;
  name: string;
  email: string;
  areas: string[];
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isPending: boolean;
  error: Error | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isPending, setIsPending] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Restaurar sesión al cargar
  useEffect(() => {
    const savedToken = localStorage.getItem('auth_token');
    if (savedToken) {
      setToken(savedToken);
      fetchUserData(savedToken);
    } else {
      setIsPending(false);
    }
  }, []);

  const fetchUserData = async (authToken: string) => {
    try {
      const response = await fetch('/api/me', {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch user data');
      }

      const data = await response.json();
      setUser({
        id: '', 
        name: data.name,
        email: data.email,
        areas: data.areas,
      });
      setError(null);
    } catch (err) {
      console.error('Error fetching user data:', err);
      setError(err instanceof Error ? err : new Error('Unknown error'));
      localStorage.removeItem('auth_token');
      setToken(null);
    } finally {
      setIsPending(false);
    }
  };

  const login = async (username: string, password: string) => {
    setError(null);
    setIsPending(true);

    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Login failed');
      }

      const data = await response.json();
      const authToken = data.token;

      setToken(authToken);
      localStorage.setItem('auth_token', authToken);

      setUser({
        id: data.user_id,
        name: username.split('@')[0], 
        email: username,
        areas: data.areas,
      });

      setError(null);
    } catch (err) {
      console.error('Login error:', err);
      setError(err instanceof Error ? err : new Error('Login failed'));
      throw err;
    } finally {
      setIsPending(false);
    }
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    setError(null);
    localStorage.removeItem('auth_token');
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isPending, error }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}