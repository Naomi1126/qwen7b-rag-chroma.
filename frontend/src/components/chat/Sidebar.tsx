import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Plus, MessageSquare, LogOut, User } from "lucide-react";
import type { Conversation } from "@/types/conversation";

type AreaOption = { slug: string; name: string };

type SidebarProps = {
  conversations: Conversation[];
  selectedConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onLogout: () => void;
  userName: string;
  isLoading: boolean;

  areas: AreaOption[];
  selectedArea: string;
  onChangeArea: (slug: string) => void;
};

export function Sidebar({
  conversations,
  selectedConversationId,
  onSelectConversation,
  onNewConversation,
  onLogout,
  userName,
  isLoading,
  areas,
  selectedArea,
  onChangeArea,
}: SidebarProps) {
  return (
    <aside className="w-80 bg-secondary border-r border-border flex flex-col">
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded bg-accent flex items-center justify-center">
              <span className="text-accent-foreground font-bold text-sm">CM</span>
            </div>
            <div>
              <h2 className="font-headline text-lg font-bold text-foreground">Comarket</h2>
              <p className="text-xs text-gray-300">S.A. de C.V.</p>
            </div>
          </div>
        </div>

        <Button
          onClick={onNewConversation}
          className="w-full bg-accent hover:bg-[hsl(214,77%,38%)] text-accent-foreground rounded-full"
        >
          <Plus className="w-4 h-4 mr-2" />
          Nueva Conversación
        </Button>

        {/* ✅ Dropdown de área (mínimo, compacto) */}
        <div className="mt-4">
          <label className="text-xs text-gray-300">Área</label>
          <select
            value={selectedArea}
            onChange={(e) => onChangeArea(e.target.value)}
            className="w-full mt-1 h-9 rounded-md bg-muted px-3 text-sm text-foreground border border-border"
          >
            {/* Si por algún motivo no hay áreas, aún dejamos general */}
            {areas.length === 0 ? (
              <option value="general">General</option>
            ) : (
              areas.map((a) => (
                <option key={a.slug} value={a.slug}>
                  {a.name || a.slug}
                </option>
              ))
            )}
          </select>
        </div>
      </div>

      <div className="px-4 py-3 border-b border-border">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">Historial</h3>
      </div>

      <ScrollArea className="flex-1 px-2">
        {isLoading ? (
          <div className="p-4 text-center text-gray-400 text-sm">Cargando conversaciones...</div>
        ) : conversations.length === 0 ? (
          <div className="p-4 text-center text-gray-400 text-sm">No hay conversaciones aún</div>
        ) : (
          <div className="space-y-1 py-2">
            {conversations.map((conversation) => (
              <button
                key={conversation.id}
                onClick={() => onSelectConversation(conversation.id)}
                className={`w-full text-left px-3 py-3 rounded-lg transition-colors duration-150 flex items-start gap-3 ${
                  selectedConversationId === conversation.id
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-secondary-foreground/10 text-foreground"
                }`}
              >
                <MessageSquare className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{conversation.title}</p>
                  <p className="text-xs opacity-70 mt-0.5">
                    {new Date(conversation.updatedAt).toLocaleDateString("es-ES", {
                      day: "numeric",
                      month: "short",
                    })}
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}
      </ScrollArea>

      <div className="p-4 border-t border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
              <User className="w-4 h-4 text-muted-foreground" />
            </div>
            <span className="text-sm text-foreground font-medium truncate max-w-[150px]">{userName}</span>
          </div>
          <Button
            onClick={onLogout}
            variant="ghost"
            size="icon"
            className="text-gray-400 hover:text-foreground hover:bg-secondary-foreground/10"
            title="Cerrar sesión"
          >
            <LogOut className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </aside>
  );
}
