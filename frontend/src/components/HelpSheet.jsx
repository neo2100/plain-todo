import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Github, Mail, Keyboard } from "lucide-react";

const REPO = "https://github.com/neo2100/plain-todo/";

const SHORTCUTS = [
  { k: "[]  then space", d: "Turn a line into a checkbox task" },
  { k: "-  then space", d: "Turn a line into a bullet note" },
  { k: "#  then space", d: "Turn a line into a section title" },
  { k: "Enter", d: "Start a new line below (same type)" },
  { k: "Tab", d: "Indent — make it a sub-item" },
  { k: "Shift + Tab", d: "Outdent one level" },
  { k: "Backspace (empty line)", d: "Merge into the line above" },
  { k: "+ (hover a row)", d: "Insert a new line right below" },
  { k: "Drag handle ⠿", d: "Reorder, move to another day, or drop onto the Backlog" },
  { k: "Check a parent", d: "Also checks its sub-tasks; parent auto-checks when all children are done" },
];

export default function HelpSheet({ open, onOpenChange }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[92vw] sm:w-[440px] rounded-none bg-card overflow-y-auto thin-scroll" data-testid="help-sheet">
        <SheetHeader>
          <SheetTitle className="font-cabinet font-extrabold tracking-tight flex items-center gap-2">
            <Keyboard className="h-5 w-5" strokeWidth={1.5} /> Quick guide
          </SheetTitle>
          <SheetDescription>Type these anywhere in the editor.</SheetDescription>
        </SheetHeader>

        <div className="mt-6 divide-y divide-border/60">
          {SHORTCUTS.map((s) => (
            <div key={s.k} className="flex items-start gap-4 py-3">
              <kbd className="font-mono text-xs bg-secondary border border-border px-2 py-1 whitespace-nowrap">{s.k}</kbd>
              <span className="text-sm text-muted-foreground leading-6">{s.d}</span>
            </div>
          ))}
        </div>

        <div className="mt-8 pt-6 border-t border-border space-y-3">
          <a href={REPO} target="_blank" rel="noreferrer" data-testid="github-link" className="flex items-center gap-3 text-sm hover:text-foreground text-muted-foreground transition-colors">
            <Github className="h-4 w-4" strokeWidth={1.5} /> View source on GitHub
          </a>
          <a href={`${REPO}issues`} target="_blank" rel="noreferrer" data-testid="contact-link" className="flex items-center gap-3 text-sm hover:text-foreground text-muted-foreground transition-colors">
            <Mail className="h-4 w-4" strokeWidth={1.5} /> Contact us / report an issue
          </a>
        </div>
      </SheetContent>
    </Sheet>
  );
}
