import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";

const WEEKDAYS = [
  { v: 0, t: "Mon" }, { v: 1, t: "Tue" }, { v: 2, t: "Wed" }, { v: 3, t: "Thu" },
  { v: 4, t: "Fri" }, { v: 5, t: "Sat" }, { v: 6, t: "Sun" },
];

const INTERVALS = [
  { v: "daily", t: "Every day", d: "Carry unfinished tasks forward each allowed day." },
  { v: "weekly", t: "Weekly", d: "Accumulate for a week, then carry forward." },
  { v: "custom", t: "Custom", d: "Carry forward every N days." },
];

export default function SettingsDialog({ open, onOpenChange, settings, onChange }) {
  const set = (patch) => onChange({ ...settings, ...patch });
  const toggleDay = (v) => {
    const has = settings.carry_weekdays.includes(v);
    const next = has ? settings.carry_weekdays.filter((d) => d !== v) : [...settings.carry_weekdays, v].sort((a, b) => a - b);
    set({ carry_weekdays: next });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-none sm:max-w-lg" data-testid="settings-dialog">
        <DialogHeader>
          <DialogTitle className="font-cabinet font-bold tracking-tight">Carry-over settings</DialogTitle>
          <DialogDescription>Control when unfinished tasks roll onto a new day.</DialogDescription>
        </DialogHeader>

        <div className="space-y-7 mt-2">
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-sm font-medium">Auto carry-over</Label>
              <p className="text-xs text-muted-foreground mt-0.5">Move unfinished tasks forward automatically.</p>
            </div>
            <Switch
              data-testid="rollover-enabled-switch"
              checked={settings.rollover_enabled}
              onCheckedChange={(v) => set({ rollover_enabled: v })}
            />
          </div>

          <div className={settings.rollover_enabled ? "" : "opacity-40 pointer-events-none"}>
            <Label className="text-xs font-mono uppercase tracking-wide text-muted-foreground">Frequency</Label>
            <div className="mt-3 space-y-2">
              {INTERVALS.map((opt) => (
                <button
                  key={opt.v}
                  data-testid={`interval-${opt.v}`}
                  onClick={() => set({ interval_mode: opt.v })}
                  className={`w-full text-left border p-3.5 transition-colors ${settings.interval_mode === opt.v ? "border-foreground bg-accent" : "border-border hover:bg-accent/50"}`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`h-3 w-3 rounded-full border ${settings.interval_mode === opt.v ? "bg-foreground border-foreground" : "border-muted-foreground"}`} />
                    <span className="font-mono text-sm">{opt.t}</span>
                    {opt.v === "custom" && settings.interval_mode === "custom" && (
                      <div className="ml-auto flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                        <Input
                          data-testid="interval-days-input"
                          type="number"
                          min={1}
                          value={settings.interval_days}
                          onChange={(e) => set({ interval_days: Math.max(1, parseInt(e.target.value || "1", 10)) })}
                          className="h-8 w-16 rounded-none font-mono text-sm"
                        />
                        <span className="text-xs text-muted-foreground">days</span>
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1 pl-5">{opt.d}</p>
                </button>
              ))}
            </div>

            <Label className="text-xs font-mono uppercase tracking-wide text-muted-foreground mt-6 block">Carry onto these days</Label>
            <p className="text-xs text-muted-foreground mt-0.5 mb-3">Tasks wait until the next selected day (e.g. skip weekends).</p>
            <div className="flex flex-wrap gap-2">
              {WEEKDAYS.map((d) => {
                const active = settings.carry_weekdays.includes(d.v);
                return (
                  <button
                    key={d.v}
                    data-testid={`weekday-${d.v}`}
                    onClick={() => toggleDay(d.v)}
                    className={`h-9 w-12 border font-mono text-xs transition-colors ${active ? "bg-foreground text-background border-foreground" : "border-border text-muted-foreground hover:bg-accent/50"}`}
                  >
                    {d.t}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
