import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Logo } from "./Logo";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { UserCircle2 } from "lucide-react";

export function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!username || !password) {
      setError(true);
      setErrorMessage("Por favor completa todos los campos");
      setTimeout(() => setError(false), 500);
      return;
    }

    setIsLoading(true);
    setErrorMessage("");
    
    try {
      await login(username, password);
    } catch (err) {
      console.error("Login failed:", err);
      setError(true);
      setErrorMessage(err instanceof Error ? err.message : "Error al iniciar sesión");
      setTimeout(() => setError(false), 3000);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-1 flex flex-col items-center justify-center px-4 py-8 relative overflow-hidden">
      <div className="absolute inset-0 z-0">
        <div className="w-full h-full bg-gradient-to-br from-blue-900/20 via-purple-900/20 to-pink-900/20" />
      </div>

      <div className="relative z-10 w-full max-w-md animate-fade-in">
        <div className="flex flex-col items-center gap-8">
          <Logo />
          
          <Card className={`w-full bg-card p-8 rounded-lg shadow-2xl ${error ? "animate-shake" : ""}`}>
            <form onSubmit={handleSubmit} className="flex flex-col items-center gap-6">
              <div className="flex items-center justify-center w-16 h-16 rounded-full bg-muted">
                <UserCircle2 className="w-10 h-10 text-muted-foreground" strokeWidth={1.5} />
              </div>

              <div className="w-full">
                <label htmlFor="username" className="sr-only">
                  Usuario
                </label>
                <Input
                  id="username"
                  type="text"
                  placeholder="Usuario (email)"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full h-12 px-4 rounded-full bg-input border-border text-card-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-transparent transition-all duration-200"
                  aria-label="Campo de usuario"
                  disabled={isLoading}
                  autoComplete="email"
                />
              </div>

              <div className="w-full">
                <label htmlFor="password" className="sr-only">
                  Contraseña
                </label>
                <Input
                  id="password"
                  type="password"
                  placeholder="Contraseña"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full h-12 px-4 rounded-full bg-input border-border text-card-foreground placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:border-transparent transition-all duration-200"
                  aria-label="Campo de contraseña"
                  disabled={isLoading}
                  autoComplete="current-password"
                />
              </div>

              {errorMessage && (
                <div className="w-full text-sm text-red-500 text-center">
                  {errorMessage}
                </div>
              )}

              <Button
                type="submit"
                className="w-full h-12 rounded-full bg-accent text-accent-foreground font-normal text-base hover:bg-[hsl(214,77%,38%)] transition-all duration-200 ease-in"
                disabled={isLoading}
              >
                {isLoading ? "Entrando..." : "Entrar"}
              </Button>

              <p className="text-xs text-muted-foreground text-center">
              
              </p>
            </form>
          </Card>
          
          <footer className="text-center">
            <p className="text-xs text-gray-400">
              © Comarket S.A. de C.V. 2024
            </p>
          </footer>
        </div>
      </div>
    </div>
  );
}