import { useCallback, useEffect, useRef, useState } from "react";
import { format, parseISO } from "date-fns";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/Header";
import DayEditor from "@/components/DayEditor";
import BacklogPanel from "@/components/BacklogPanel";
import SettingsDialog from "@/components/SettingsDialog";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Loader2 } from "lucide-react";

function localDate(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function DayHeader({ date }) {
  const d = parseISO(date);
  const label = format(d, "EEE, dd MMM yyyy");
  let badge = null;
  if (date === localDate(0)) badge = "Today";
  else if (date === localDate(-1)) badge = "Yesterday";
  return (
    <div className="flex items-baseline gap-3 mb-5">
      <h2 className="font-cabinet font-bold text-2xl tracking-tight" data-testid="day-title">{label}</h2>
      {badge && (
        <span className="text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 bg-foreground text-background">
          {badge}
        </span>
      )}
    </div>
  );
}

export default function Board() {
  const { user, logout } = useAuth();
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState([]);
  const [backlog, setBacklog] = useState([]);
  const [rolloverMode, setRolloverMode] = useState("everyday");
  const [viewMode, setViewMode] = useState(() => localStorage.getItem("pt_view") || "rich");
  const [search, setSearch] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [backlogSheetOpen, setBacklogSheetOpen] = useState(false);
  const saveTimers = useRef({});
  const pending = useRef({});
  const today = localDate(0);

  useEffect(() => localStorage.setItem("pt_view", viewMode), [viewMode]);

  const flushAll = useCallback(() => {
    Object.keys(pending.current).forEach((date) => {
      clearTimeout(saveTimers.current[date]);
      const content = pending.current[date];
      delete pending.current[date];
      api.put(`/days/${date}`, { content }).catch(() => {});
    });
  }, []);

  useEffect(() => () => flushAll(), [flushAll]);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/board`, { params: { date: today } });
      setDays(data.days);
      setBacklog(data.backlog.items || []);
      setRolloverMode(data.settings.rollover_mode || "everyday");
    } catch (e) {
      toast.error("Failed to load your canvas.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { load(); }, [load]);

  const scheduleSave = (date, content) => {
    pending.current[date] = content;
    clearTimeout(saveTimers.current[date]);
    saveTimers.current[date] = setTimeout(() => {
      delete pending.current[date];
      api.put(`/days/${date}`, { content }).catch(() => toast.error("Save failed"));
    }, 600);
  };

  const handleLogout = async () => {
    flushAll();
    await logout();
  };

  const updateDay = (date, content) => {
    setDays((prev) => {
      const exists = prev.some((d) => d.date === date);
      const next = exists
        ? prev.map((d) => (d.date === date ? { ...d, content } : d))
        : [{ date, content }, ...prev];
      return next;
    });
    scheduleSave(date, content);
  };

  const saveBacklog = (items) => {
    setBacklog(items);
    api.put(`/backlog`, { items }).catch(() => toast.error("Backlog save failed"));
  };

  const moveToBacklog = (text) => {
    const item = { id: Math.random().toString(36).slice(2, 12), text, done: false };
    saveBacklog([...backlog, item]);
    toast("Moved to backlog");
  };

  const moveBacklogToToday = (text) => {
    const cur = days.find((d) => d.date === today)?.content || "";
    const base = cur.trim();
    const next = base ? `${base}\n[ ] ${text}` : `[ ] ${text}`;
    updateDay(today, next);
    toast("Moved to today");
  };

  const changeRollover = (mode) => {
    setRolloverMode(mode);
    api.put(`/settings`, { rollover_mode: mode }).catch(() => toast.error("Could not save setting"));
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" strokeWidth={1.5} />
      </div>
    );
  }

  const q = search.trim().toLowerCase();
  const visibleDays = q
    ? days.filter((d) => d.content.toLowerCase().includes(q) || d.date.includes(q))
    : days;

  return (
    <div className="min-h-screen flex flex-col bg-background relative z-10">
      <Header
        user={user}
        onLogout={handleLogout}
        viewMode={viewMode}
        setViewMode={setViewMode}
        onOpenSettings={() => setSettingsOpen(true)}
        search={search}
        setSearch={setSearch}
        onOpenBacklog={() => setBacklogSheetOpen(true)}
      />

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
        {/* Editor canvas */}
        <main className="lg:col-span-8 xl:col-span-9 overflow-y-auto thin-scroll px-5 sm:px-10 lg:px-16 py-10 lg:py-14" data-testid="editor-canvas">
          <div className="max-w-3xl">
            {visibleDays.length === 0 && (
              <p className="font-mono text-sm text-muted-foreground">No days match “{search}”.</p>
            )}
            {visibleDays.map((day, idx) => (
              <section
                key={day.date}
                className="group/day mb-14 animate-fade-up"
                style={{ animationDelay: `${Math.min(idx, 6) * 40}ms` }}
                data-testid={`day-block-${day.date}`}
              >
                <DayHeader date={day.date} />
                <DayEditor
                  content={day.content}
                  viewMode={viewMode}
                  onChange={(c) => updateDay(day.date, c)}
                  onMoveToBacklog={moveToBacklog}
                />
                {idx < visibleDays.length - 1 && <div className="h-px bg-border mt-14" />}
              </section>
            ))}
          </div>
        </main>

        {/* Backlog (desktop) */}
        <aside className="hidden lg:block lg:col-span-4 xl:col-span-3 border-l border-border bg-card/40 overflow-y-auto thin-scroll px-8 py-14">
          <BacklogPanel items={backlog} onChange={saveBacklog} onMoveToToday={moveBacklogToToday} />
        </aside>
      </div>

      {/* Backlog (mobile) */}
      <Sheet open={backlogSheetOpen} onOpenChange={setBacklogSheetOpen}>
        <SheetContent side="right" className="w-[88vw] sm:w-96 rounded-none px-6 py-10 bg-card">
          <BacklogPanel items={backlog} onChange={saveBacklog} onMoveToToday={(t) => { moveBacklogToToday(t); }} />
        </SheetContent>
      </Sheet>

      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        rolloverMode={rolloverMode}
        onChangeMode={changeRollover}
      />
    </div>
  );
}
