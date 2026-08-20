import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { parseContent, serializeLines } from "@/lib/parser";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { Plus, Archive, ExternalLink } from "lucide-react";
import { firstUrl } from "@/lib/parser";

const MAX_INDENT = 6;

export default function DayEditor({ content, viewMode, onChange, onMoveToBacklog, autoFocusFirst }) {
  const [lines, setLines] = useState(() => parseContent(content));
  const inputsRef = useRef([]);
  const focusTarget = useRef(null);

  // Resync from parent when the content changes externally (rollover / move).
  useEffect(() => {
    if (serializeLines(lines) !== (content || "")) {
      setLines(parseContent(content));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content]);

  useLayoutEffect(() => {
    if (focusTarget.current != null) {
      const { index, pos } = focusTarget.current;
      const el = inputsRef.current[index];
      if (el) {
        el.focus();
        if (pos != null) {
          try { el.setSelectionRange(pos, pos); } catch {}
        }
      }
      focusTarget.current = null;
    }
  });

  const commit = (next) => {
    setLines(next);
    onChange(serializeLines(next));
  };

  const updateText = (i, text) => {
    const next = lines.slice();
    const line = { ...next[i], text };
    if (line.type === "blank" && text !== "") line.type = "text";
    next[i] = line;
    commit(next);
  };

  const toggleDone = (i) => {
    const next = lines.slice();
    next[i] = { ...next[i], done: !next[i].done };
    commit(next);
  };

  const setIndent = (i, delta) => {
    const next = lines.slice();
    const indent = Math.max(0, Math.min(MAX_INDENT, (next[i].indent || 0) + delta));
    next[i] = { ...next[i], indent };
    commit(next);
  };

  const addLineAfter = (i, type) => {
    const next = lines.slice();
    const base = i >= 0 ? next[i] : { indent: 0 };
    const newLine = { type, text: "", indent: base.indent || 0, done: false };
    next.splice(i + 1, 0, newLine);
    focusTarget.current = { index: i + 1, pos: 0 };
    commit(next);
  };

  const removeLine = (i, focusPrev = true) => {
    const next = lines.slice();
    const prevText = i > 0 ? next[i - 1].text : "";
    next.splice(i, 1);
    if (focusPrev && i > 0) focusTarget.current = { index: i - 1, pos: prevText.length };
    commit(next.length ? next : []);
  };

  const onKeyDown = (e, i) => {
    const el = e.target;
    if (e.key === "Enter") {
      e.preventDefault();
      const pos = el.selectionStart ?? el.value.length;
      const before = el.value.slice(0, pos);
      const after = el.value.slice(pos);
      const cur = lines[i];
      const nextType = cur.type === "task" ? "task" : cur.type === "bullet" ? "bullet" : "text";
      const next = lines.slice();
      next[i] = { ...cur, text: before };
      next.splice(i + 1, 0, { type: nextType, text: after, indent: cur.indent || 0, done: false });
      focusTarget.current = { index: i + 1, pos: 0 };
      commit(next);
    } else if (e.key === "Backspace") {
      const pos = el.selectionStart ?? 0;
      if (pos === 0) {
        if (lines[i].text === "" && lines.length > 1) {
          e.preventDefault();
          removeLine(i);
        } else if (i > 0) {
          e.preventDefault();
          const next = lines.slice();
          const prev = next[i - 1];
          const mergePos = prev.text.length;
          next[i - 1] = { ...prev, text: prev.text + lines[i].text };
          next.splice(i, 1);
          focusTarget.current = { index: i - 1, pos: mergePos };
          commit(next);
        }
      }
    } else if (e.key === "Tab") {
      e.preventDefault();
      setIndent(i, e.shiftKey ? -1 : 1);
    } else if (e.key === "ArrowUp" && i > 0) {
      const el2 = inputsRef.current[i - 1];
      if (el2) { e.preventDefault(); el2.focus(); }
    } else if (e.key === "ArrowDown" && i < lines.length - 1) {
      const el2 = inputsRef.current[i + 1];
      if (el2) { e.preventDefault(); el2.focus(); }
    }
  };

  // ---- Plain-text mode ----
  if (viewMode === "plain") {
    return (
      <Textarea
        data-testid="plain-editor"
        value={content}
        onChange={(e) => onChange(e.target.value)}
        placeholder={"[ ] a task\n- a bullet note\nhttps://a-link.com"}
        className="editor-input min-h-[120px] text-sm leading-7 rounded-none border-0 focus-visible:ring-0 px-0 py-0 shadow-none"
        style={{ height: "auto" }}
        rows={Math.max(4, (content || "").split("\n").length + 1)}
      />
    );
  }

  // ---- Rich mode ----
  return (
    <div className="space-y-0.5">
      {lines.length === 0 && (
        <button
          data-testid="empty-add-task"
          onClick={() => { const next = [{ type: "task", text: "", indent: 0, done: false }]; focusTarget.current = { index: 0, pos: 0 }; commit(next); }}
          className="text-sm font-mono text-muted-foreground/60 hover:text-foreground transition-colors py-1"
        >
          <span className="opacity-60">[ ]</span> add your first task…
        </button>
      )}

      {lines.map((line, i) => {
        const url = firstUrl(line.text);
        return (
          <div
            key={i}
            className="group flex items-start gap-2.5"
            style={{ paddingLeft: `${(line.indent || 0) * 22}px` }}
          >
            <div className="pt-[3px] w-4 flex-shrink-0 flex justify-center">
              {line.type === "task" ? (
                <Checkbox
                  data-testid="todo-checkbox"
                  checked={line.done}
                  onCheckedChange={() => toggleDone(i)}
                  className="rounded-none h-4 w-4 border-foreground/40 data-[state=checked]:bg-foreground data-[state=checked]:border-foreground"
                />
              ) : line.type === "bullet" ? (
                <span className="text-muted-foreground select-none leading-6 text-sm">•</span>
              ) : (
                <span className="select-none leading-6" />
              )}
            </div>

            <input
              ref={(el) => (inputsRef.current[i] = el)}
              data-testid="line-input"
              value={line.text}
              onChange={(e) => updateText(i, e.target.value)}
              onKeyDown={(e) => onKeyDown(e, i)}
              autoFocus={autoFocusFirst && i === 0}
              spellCheck={false}
              placeholder={line.type === "task" ? "task…" : line.type === "bullet" ? "note…" : ""}
              className={`editor-input text-sm leading-6 py-0.5 ${
                line.type === "task" && line.done ? "line-through text-muted-foreground/60" : "text-foreground"
              }`}
            />

            <div className="flex items-center gap-1 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity pt-[2px]">
              {url && (
                <a href={url} target="_blank" rel="noreferrer" data-testid="open-link-btn"
                   className="text-muted-foreground hover:text-foreground" title="Open link">
                  <ExternalLink className="h-3.5 w-3.5" strokeWidth={1.5} />
                </a>
              )}
              {line.type === "task" && onMoveToBacklog && (
                <button
                  data-testid="move-to-backlog-btn"
                  onClick={() => { onMoveToBacklog(line.text); removeLine(i, false); }}
                  className="text-muted-foreground hover:text-foreground"
                  title="Move to backlog"
                >
                  <Archive className="h-3.5 w-3.5" strokeWidth={1.5} />
                </button>
              )}
            </div>
          </div>
        );
      })}

      <div className="flex items-center gap-4 pt-2 opacity-100 sm:opacity-0 sm:group-hover/day:opacity-100 transition-opacity">
        <button data-testid="add-task-btn" onClick={() => addLineAfter(lines.length - 1, "task")}
          className="inline-flex items-center gap-1.5 text-xs font-mono text-muted-foreground hover:text-foreground transition-colors">
          <Plus className="h-3.5 w-3.5" strokeWidth={1.5} /> task
        </button>
        <button data-testid="add-bullet-btn" onClick={() => addLineAfter(lines.length - 1, "bullet")}
          className="inline-flex items-center gap-1.5 text-xs font-mono text-muted-foreground hover:text-foreground transition-colors">
          <Plus className="h-3.5 w-3.5" strokeWidth={1.5} /> note
        </button>
      </div>
    </div>
  );
}
