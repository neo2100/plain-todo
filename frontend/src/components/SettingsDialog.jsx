import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

export default function SettingsDialog({ open, onOpenChange, rolloverMode, onChangeMode }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-none sm:max-w-md" data-testid="settings-dialog">
        <DialogHeader>
          <DialogTitle className="font-cabinet font-bold tracking-tight">Settings</DialogTitle>
          <DialogDescription>Configure how unfinished tasks carry over.</DialogDescription>
        </DialogHeader>

        <div className="mt-2">
          <Label className="text-xs font-mono uppercase tracking-wide text-muted-foreground">
            Auto carry-over
          </Label>
          <div className="mt-3 space-y-2">
            {[
              { v: "everyday", t: "Every day", d: "Roll unfinished tasks to the next calendar day." },
              { v: "workdays", t: "Working days only", d: "Skip weekends — tasks wait until Monday." },
            ].map((opt) => (
              <button
                key={opt.v}
                data-testid={`rollover-${opt.v}`}
                onClick={() => onChangeMode(opt.v)}
                className={`w-full text-left border p-4 transition-colors ${
                  rolloverMode === opt.v
                    ? "border-foreground bg-accent"
                    : "border-border hover:bg-accent/50"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className={`h-3 w-3 rounded-full border ${rolloverMode === opt.v ? "bg-foreground border-foreground" : "border-muted-foreground"}`} />
                  <span className="font-mono text-sm">{opt.t}</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1 pl-5">{opt.d}</p>
              </button>
            ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
