import { useAuth } from "./contexts/AuthContext";
import { LoginPage } from "./components/LoginPage";
import { ChatPage } from "./components/ChatPage";

function App() {
  const { user, isPending, error } = useAuth();

  if (isPending) {
    return (
      <div className="min-h-screen bg-gradient-1 flex items-center justify-center">
        <div className="text-foreground text-xl">Cargando...</div>
      </div>
    );
  }

  if (error && !user) {
    return (
      <div className="min-h-screen bg-gradient-1 flex items-center justify-center">
        <div className="text-red-400 text-xl">Error: {error.message}</div>
      </div>
    );
  }

  return user ? <ChatPage /> : <LoginPage />;
}

export default App;