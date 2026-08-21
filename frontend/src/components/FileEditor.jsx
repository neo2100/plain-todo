import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import { CheckSquare, Minus, Hash } from "lucide-react";

const DELIM = /^===\s(\d{4}-\d{2}-\d{2})\s===$/;

function buildFile(days) {
  return days.map((d) => `=== ${d.date} ===\n${d.content}`).join("\n\n");
}

export function parseFile(text) {
  const lines = text.split("\n");
  const out = [];
  let cur = null;
  for (const line of lines) {
    const m = line.match(DELIM);
    if (m) {
      cur = { date: m[1], lines: [] };
      out.push(cur);
    } else if (cur) {
      cur.lines.push(line);
    }
  }
  return out.map((d) => ({ date: d.date, content: d.lines.join("\n").replace(/^\n+|\n+$/g, "") }));
}

function stripMarker(line) {
  const m = line.match(/^(\s*)(?:\[[ xX]?\]\s|[-*]\s|#\s)?(.*)$/);
  return { indent: m[1], text: m[2] };
}

export default function FileEditor({ days, onSave }) {
  const [text, setText] = useState(() => buildFile(days));
  const ref = useRef(null);
  const timer = useRef(null);
  const pendingSel = useRef(null);
  const datesSig = days.map((d) => d.date).join(",");

  // Rebuild when the set of days changes (e.g. a day was added) unless editing.
  useEffect(() => {
    if (document.activeElement !== ref.current) setText(buildFile(days));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datesSig]);

  useLayoutEffect(() => {
    if (pendingSel.current && ref.current) {
      const [s, e] = pendingSel.current;
      ref.current.focus();
      try { ref.current.setSelectionRange(s, e); } catch {}
      pendingSel.current = null;
    }
  });

  const scheduleSave = (value) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => onSave(parseFile(value)), 800);
  };

  const onChange = (e) => {
    setText(e.target.value);
    scheduleSave(e.target.value);
  };

  const convert = (kind) => {
    const el = ref.current;
    if (!el) return;
    const value = el.value;
    const selStart = el.selectionStart;
    const selEnd = el.selectionEnd;
    // Expand selection to whole lines.
    const lineStart = value.lastIndexOf("\n", selStart - 1) + 1;
    let lineEnd = value.indexOf("\n", selEnd);
    if (lineEnd === -1) lineEnd = value.length;
    const segment = value.slice(lineStart, lineEnd);
    const converted = segment
      .split("\n")
      .map((line) => {
        if (DELIM.test(line) || line.trim() === "") return line; // keep day delimiters & blanks
        const { indent, text: t } = stripMarker(line);
        if (kind === "task") return `${indent}[ ] ${t}`;
        if (kind === "note") return `${indent}- ${t}`;
        return `# ${t}`; // section
      })
      .join("\n");
    const next = value.slice(0, lineStart) + converted + value.slice(lineEnd);
    pendingSel.current = [lineStart, lineStart + converted.length];
    setText(next);
    scheduleSave(next);
  };

  const btn = "inline-flex items-center gap-1.5 h-8 px-3 border border-border text-xs font-mono hover:bg-accent transition-colors rounded-none";

  return (
    <div data-testid="file-editor">
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <span className="text-xs font-mono uppercase tracking-widest text-muted-foreground mr-1">Selection →</span>
        <button data-testid="convert-task-btn" onClick={() => convert("task")} className={btn}><CheckSquare className="h-3.5 w-3.5" strokeWidth={1.5} /> Task</button>
        <button data-testid="convert-note-btn" onClick={() => convert("note")} className={btn}><Minus className="h-3.5 w-3.5" strokeWidth={1.5} /> Note</button>
        <button data-testid="convert-section-btn" onClick={() => convert("section")} className={btn}><Hash className="h-3.5 w-3.5" strokeWidth={1.5} /> Section</button>
      </div>
      <Textarea
        ref={ref}
        data-testid="file-editor-textarea"
        value={text}
        onChange={onChange}
        spellCheck={false}
        className="editor-input min-h-[60vh] text-sm leading-7 rounded-none border border-border focus-visible:ring-0 p-4 shadow-none"
        placeholder={"=== 2026-08-20 ===\n[ ] a task\n  - a note\n# A section"}
      />
      <p className="text-xs text-muted-foreground mt-3 font-mono">
        One big file across all days. Lines like <span className="text-foreground">=== YYYY-MM-DD ===</span> separate days. Select lines and use the buttons above to convert.
      </p>
    </div>
  );
}
