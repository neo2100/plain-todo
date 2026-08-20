import { useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Plus, ArrowUpRight, X, Archive } from "lucide-react";

export default function BacklogPanel({ items, onChange, onMoveToToday }) {
  const [draft, setDraft] = useState("");

  const addItem = () => {
    const text = draft.trim();
    if (!text) return;
    onChange([...items, { id: Math.random().toString(36).slice(2, 12), text, done: false }]);
    setDraft("");
  };

  const updateItem = (id, patch) =>
    onChange(items.map((it) => (it.id === id ? { ...it, ...patch } : it)));

  const removeItem = (id) => onChange(items.filter((it) => it.id !== id));

  return (
    <div className="h-full flex flex-col" data-testid="backlog-panel">
      <div className="flex items-center gap-2 mb-6">
        <Archive className="h-4 w-4" strokeWidth={1.5} />
        <h2 className="font-cabinet font-bold text-lg tracking-tight">Backlog</h2>
        <span className="ml-auto text-xs font-mono text-muted-foreground">{items.length}</span>
      </div>

      <div className="flex items-center gap-2 mb-4 border border-border">
        <input
          data-testid="backlog-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addItem()}
          placeholder="park a task for later…"
          className="editor-input text-sm px-3 py-2.5"
        />
        <button data-testid="backlog-add-btn" onClick={addItem} className="px-3 py-2.5 text-muted-foreground hover:text-foreground transition-colors">
          <Plus className="h-4 w-4" strokeWidth={1.5} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto thin-scroll -mr-2 pr-2">
        {items.length === 0 && (
          <p className="text-sm font-mono text-muted-foreground/60 py-4">
            Nothing parked. Move a task here to remember it without cluttering today.
          </p>
        )}
        {items.map((it) => {
          const url = it.text.match(/https?:\/\/[^\s)]+/)?.[0];
          return (
            <div key={it.id} className="group flex items-start gap-2.5 py-2 border-b border-border/50">
              <Checkbox
                data-testid="backlog-checkbox"
                checked={it.done}
                onCheckedChange={(v) => updateItem(it.id, { done: !!v })}
                className="rounded-none h-4 w-4 mt-0.5 border-foreground/40 data-[state=checked]:bg-foreground data-[state=checked]:border-foreground"
              />
              <input
                data-testid="backlog-item-input"
                value={it.text}
                onChange={(e) => updateItem(it.id, { text: e.target.value })}
                spellCheck={false}
                className={`editor-input text-sm leading-6 ${it.done ? "line-through text-muted-foreground/60" : ""}`}
              />
              <div className="flex items-center gap-1 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity mt-0.5">
                {url && (
                  <a href={url} target="_blank" rel="noreferrer" className="text-muted-foreground hover:text-foreground" title="Open link">
                    <ArrowUpRight className="h-3.5 w-3.5 rotate-0" strokeWidth={1.5} />
                  </a>
                )}
                <button
                  data-testid="backlog-move-today-btn"
                  onClick={() => { onMoveToToday(it.text); removeItem(it.id); }}
                  className="text-muted-foreground hover:text-foreground"
                  title="Move to today"
                >
                  <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={1.5} />
                </button>
                <button data-testid="backlog-delete-btn" onClick={() => removeItem(it.id)} className="text-muted-foreground hover:text-destructive" title="Delete">
                  <X className="h-3.5 w-3.5" strokeWidth={1.5} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
