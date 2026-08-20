import { useCallback, useEffect, useRef, useState } from "react";
import { format, parseISO } from "date-fns";
import { toast } from "sonner";
import {
  DndContext, PointerSensor, TouchSensor, useSensor, useSensors, closestCenter,
} from "@dnd-kit/core";
import { arrayMove } from "@dnd-kit/sortable";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { parseContent, parseBlocks, blocksToLines, serializeLines } from "@/lib/parser";
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

const DEFAULT_SETTINGS = {
  rollover_enabled: true,
  carry_weekdays: [0, 1, 2, 3, 4, 5, 6],
  interval_mode: "daily",
  interval_days: 1,
};

function DayHeader({ date }) {
  const d = parseISO(date);
  const label = format(d, "EEE, dd MMM yyyy");
  let badge = null;
  if (date === localDate(0)) badge = "Today";
  else if (date === localDate(-1)) badge = "Yesterday";
  return (
    <div className="flex items-baseline gap-3 mb-5">
      <h2 className="font-cabinet font-bold text-2xl tracking-tight" data-testid="day-title">{label}</h2>
      {badge && <span className="text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 bg-foreground text-background">{badge}</span>}
    </div>
  );
}

export default function Board() {
  const { user, logout } = useAuth();
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState([]);
  const [backlog, setBacklog] = useState([]);
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [viewMode, setViewMode] = useState(() => localStorage.getItem("pt_view") || "rich");
  const [search, setSearch] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [backlogSheetOpen, setBacklogSheetOpen] = useState(false);
  const saveTimers = useRef({});
  const pending = useRef({});
  const today = localDate(0);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 200, tolerance: 6 } }),
  );

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
      setSettings({ ...DEFAULT_SETTINGS, ...(data.settings || {}) });
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

  const contentOf = (date) => days.find((d) => d.date === date)?.content || "";

  const updateDay = (date, content) => {
    setDays((prev) => {
      const exists = prev.some((d) => d.date === date);
      return exists ? prev.map((d) => (d.date === date ? { ...d, content } : d)) : [{ date, content }, ...prev];
    });
    scheduleSave(date, content);
  };

  const saveBacklog = (items) => {
    setBacklog(items);
    api.put(`/backlog`, { items }).catch(() => toast.error("Backlog save failed"));
  };

  const addBacklog = (text, notes = "") => {
    saveBacklog([...backlog, { id: Math.random().toString(36).slice(2, 12), text, done: false, notes }]);
    toast("Moved to backlog");
  };

  const moveBacklogToToday = (item) => {
    const group = [{ type: "task", text: item.text, indent: 0, done: false }];
    parseContent(item.notes || "").forEach((l) => group.push({ ...l }));
    const groupText = serializeLines(group);
    const cur = contentOf(today).trim();
    updateDay(today, cur ? `${cur}\n${groupText}` : groupText);
    toast("Moved to today");
  };

  const saveSettings = (next) => {
    setSettings(next);
    api.put(`/settings`, next).catch(() => toast.error("Could not save settings"));
  };

  const addDay = (date) => {
    if (days.some((d) => d.date === date)) { toast("That day already exists"); return; }
    setDays((prev) => [...prev, { date, content: "" }].sort((x, y) => (x.date < y.date ? 1 : -1)));
    api.put(`/days/${date}`, { content: "" }).catch(() => toast.error("Could not create day"));
    toast("Day added");
  };

  const moveGroupAcrossDays = (fromDate, fromPos, toDate, toPos) => {
    const srcBlocks = parseBlocks(parseContent(contentOf(fromDate)));
    const block = srcBlocks[fromPos];
    if (!block) return;
    const groupLines = block.lines;
    const remaining = srcBlocks.filter((_, i) => i !== fromPos);
    updateDay(fromDate, serializeLines(blocksToLines(remaining)));

    const dstBlocks = parseBlocks(parseContent(contentOf(toDate)));
    const at = toPos == null ? dstBlocks.length : Math.min(toPos, dstBlocks.length);
    dstBlocks.splice(at, 0, { start: 0, lines: groupLines });
    updateDay(toDate, serializeLines(blocksToLines(dstBlocks)));
    toast("Moved to another day");
  };

  const onDragEnd = (event) => {
    const { active, over } = event;
    if (!over) return;
    const a = active.data.current;
    if (!a || a.type !== "block") return;

    // Dropped onto the backlog zone -> move the whole task group.
    if (over.id === "backlog") {
      const blocks = parseBlocks(parseContent(contentOf(a.date)));
      const block = blocks[a.pos];
      if (!block) return;
      const taskLine = block.lines.find((l) => l.type === "task");
      if (!taskLine) { toast("Only tasks can go to the backlog"); return; }
      const rest = block.lines
        .filter((l) => l !== taskLine)
        .map((l) => ({ ...l, indent: Math.max(0, (l.indent || 0) - (taskLine.indent || 0)) }));
      const remaining = blocks.filter((_, i) => i !== a.pos);
      updateDay(a.date, serializeLines(blocksToLines(remaining)));
      addBacklog(taskLine.text, serializeLines(rest));
      return;
    }

    const o = over.data.current;
    // Dropped over a block.
    if (o && o.type === "block") {
      if (o.date === a.date) {
        if (a.pos !== o.pos) {
          const blocks = parseBlocks(parseContent(contentOf(a.date)));
          const moved = arrayMove(blocks, a.pos, o.pos);
          updateDay(a.date, serializeLines(blocksToLines(moved)));
        }
      } else {
        moveGroupAcrossDays(a.date, a.pos, o.date, o.pos);
      }
      return;
    }
    // Dropped onto a day drop-zone (e.g. empty day or gaps).
    if (o && o.type === "day" && o.date !== a.date) {
      moveGroupAcrossDays(a.date, a.pos, o.date, null);
    }
  };

  const handleLogout = async () => { flushAll(); await logout(); };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" strokeWidth={1.5} />
      </div>
    );
  }

  const q = search.trim().toLowerCase();
  const visibleDays = q ? days.filter((d) => d.content.toLowerCase().includes(q) || d.date.includes(q)) : days;

  return (
    <div className="min-h-screen flex flex-col bg-background relative z-10">
      <Header
        user={user}
        onLogout={handleLogout}
        viewMode={viewMode}
        setViewMode={setViewMode}
        onOpenSettings={() => setSettingsOpen(true)}
        onAddDay={addDay}
        today={today}
        search={search}
        setSearch={setSearch}
        onOpenBacklog={() => setBacklogSheetOpen(true)}
      />

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
          <main className="lg:col-span-8 xl:col-span-9 overflow-y-auto thin-scroll px-5 sm:px-10 lg:px-20 py-10 lg:py-14" data-testid="editor-canvas">
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
                    date={day.date}
                    content={day.content}
                    viewMode={viewMode}
                    onChange={(c) => updateDay(day.date, c)}
                    onMoveToBacklog={addBacklog}
                  />
                  {idx < visibleDays.length - 1 && <div className="h-px bg-border mt-14" />}
                </section>
              ))}
            </div>
          </main>

          <aside className="hidden lg:block lg:col-span-4 xl:col-span-3 border-l border-border bg-card/40 overflow-y-auto thin-scroll px-8 py-14">
            <BacklogPanel items={backlog} onChange={saveBacklog} onMoveToToday={moveBacklogToToday} />
          </aside>
        </div>

        <Sheet open={backlogSheetOpen} onOpenChange={setBacklogSheetOpen}>
          <SheetContent side="right" className="w-[88vw] sm:w-96 rounded-none px-6 py-10 bg-card">
            <BacklogPanel items={backlog} onChange={saveBacklog} onMoveToToday={moveBacklogToToday} />
          </SheetContent>
        </Sheet>
      </DndContext>

      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        settings={settings}
        onChange={saveSettings}
      />
    </div>
  );
}
