import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import {
  CheckSquare, Sun, Moon, Settings, LogOut, Search, PanelRight, Code2, ListChecks,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuLabel, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";

export default function Header({
  user, onLogout, viewMode, setViewMode, onOpenSettings, search, setSearch, onOpenBacklog,
}) {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = resolvedTheme === "dark";

  return (
    <header className="sticky top-0 z-50 h-16 bg-background border-b border-border flex items-center px-4 sm:px-6 gap-3">
      <div className="flex items-center gap-2 flex-shrink-0">
        <CheckSquare className="h-5 w-5" strokeWidth={1.5} />
        <span className="font-cabinet font-extrabold text-lg tracking-tight hidden sm:inline">Plain Todo</span>
      </div>

      <div className="flex-1 max-w-md mx-auto relative">
        <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" strokeWidth={1.5} />
        <input
          data-testid="search-input"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search all days…"
          className="w-full h-9 pl-9 pr-3 bg-secondary border border-transparent focus:border-border focus:outline-none text-sm font-mono rounded-none transition-colors"
        />
      </div>

      <div className="flex items-center gap-1 flex-shrink-0">
        {/* View toggle */}
        <div className="flex items-center border border-border">
          <button
            data-testid="view-rich-btn"
            onClick={() => setViewMode("rich")}
            title="Rich view"
            className={`h-9 px-2.5 flex items-center transition-colors ${viewMode === "rich" ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"}`}
          >
            <ListChecks className="h-4 w-4" strokeWidth={1.5} />
          </button>
          <button
            data-testid="view-plain-btn"
            onClick={() => setViewMode("plain")}
            title="Plain text view"
            className={`h-9 px-2.5 flex items-center transition-colors ${viewMode === "plain" ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"}`}
          >
            <Code2 className="h-4 w-4" strokeWidth={1.5} />
          </button>
        </div>

        <Button data-testid="backlog-toggle-btn" onClick={onOpenBacklog} variant="ghost" size="icon" className="rounded-none lg:hidden">
          <PanelRight className="h-4 w-4" strokeWidth={1.5} />
        </Button>

        <Button
          data-testid="theme-toggle"
          onClick={() => setTheme(isDark ? "light" : "dark")}
          variant="ghost" size="icon" className="rounded-none"
        >
          {mounted && isDark ? <Sun className="h-4 w-4" strokeWidth={1.5} /> : <Moon className="h-4 w-4" strokeWidth={1.5} />}
        </Button>

        <Button data-testid="settings-btn" onClick={onOpenSettings} variant="ghost" size="icon" className="rounded-none">
          <Settings className="h-4 w-4" strokeWidth={1.5} />
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button data-testid="user-menu-btn" className="h-9 w-9 flex items-center justify-center bg-foreground text-background font-mono text-sm">
              {(user?.name || user?.email || "?").slice(0, 1).toUpperCase()}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="rounded-none w-56">
            <DropdownMenuLabel className="font-mono text-xs truncate">{user?.email}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem data-testid="logout-btn" onClick={onLogout} className="rounded-none cursor-pointer">
              <LogOut className="h-4 w-4 mr-2" strokeWidth={1.5} /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
