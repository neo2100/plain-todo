// Plain-text <-> structured line helpers for Plain Todo.

export function parseLine(line) {
  const m = line.match(/^(\s*)(.*)$/);
  const rawIndent = m[1].replace(/\t/g, "  ");
  const indent = Math.floor(rawIndent.length / 2);
  const rest = m[2];
  if (/^#\s?/.test(rest))
    return { type: "heading", text: rest.replace(/^#\s?/, ""), indent: 0 };
  if (/^\[ \]\s?/.test(rest))
    return { type: "task", done: false, text: rest.replace(/^\[ \]\s?/, ""), indent };
  if (/^\[x\]\s?/i.test(rest))
    return { type: "task", done: true, text: rest.replace(/^\[x\]\s?/i, ""), indent };
  if (/^[-*]\s?/.test(rest))
    return { type: "bullet", text: rest.replace(/^[-*]\s?/, ""), indent };
  if (rest.trim() === "") return { type: "blank", text: "", indent: 0 };
  return { type: "text", text: rest, indent };
}

export function serializeLine(item) {
  const pad = "  ".repeat(item.indent || 0);
  if (item.type === "heading") return "# " + item.text;
  if (item.type === "task") return pad + (item.done ? "[x] " : "[ ] ") + item.text;
  if (item.type === "bullet") return pad + "- " + item.text;
  if (item.type === "blank") return "";
  return pad + item.text;
}

export function parseContent(content) {
  const lines = (content || "").split("\n");
  if (lines.length === 1 && lines[0] === "") return [];
  return lines.map(parseLine);
}

export function serializeLines(items) {
  return items.map(serializeLine).join("\n");
}

// ---- Grouping ---------------------------------------------------------------
// A task owns following lines until the next task at the same-or-shallower
// indent, or a heading. Notes / sub-tasks below therefore travel with it.
export function groupEnd(lines, i) {
  const d = lines[i].indent || 0;
  let j = i + 1;
  const n = lines.length;
  while (j < n) {
    const L = lines[j];
    if (L.type === "heading") break;
    if (L.type === "task" && (L.indent || 0) <= d) break;
    j++;
  }
  return j;
}

// Split a flat line list into top-level blocks (drag units).
export function parseBlocks(lines) {
  const blocks = [];
  let i = 0;
  const n = lines.length;
  while (i < n) {
    const L = lines[i];
    if (L.type === "task") {
      const end = groupEnd(lines, i);
      blocks.push({ start: i, lines: lines.slice(i, end) });
      i = end;
    } else {
      blocks.push({ start: i, lines: [L] });
      i += 1;
    }
  }
  return blocks;
}

export function blocksToLines(blocks) {
  return blocks.flatMap((b) => b.lines);
}

// ---- Checkbox cascade -------------------------------------------------------
function parentIndex(lines, idx) {
  const d = lines[idx].indent || 0;
  for (let j = idx - 1; j >= 0; j--) {
    const L = lines[j];
    if (L.type === "heading") return -1;
    if (L.type === "task" && (L.indent || 0) < d) return j;
  }
  return -1;
}

function descendantsAllDone(lines, pIdx) {
  const d = lines[pIdx].indent || 0;
  let hasChild = false;
  for (let j = pIdx + 1; j < lines.length; j++) {
    const L = lines[j];
    if (L.type === "heading") break;
    if (L.type === "task" && (L.indent || 0) <= d) break;
    if (L.type === "task") {
      hasChild = true;
      if (!L.done) return false;
    }
  }
  return hasChild;
}

// Toggle a task. Checking cascades down to sub-tasks and auto-checks a parent
// whose children are all done. Unchecking is independent (does not cascade).
export function toggleTaskCascade(lines, idx) {
  const next = lines.map((l) => ({ ...l }));
  const willCheck = !next[idx].done;
  next[idx].done = willCheck;
  if (willCheck) {
    const end = groupEnd(next, idx);
    for (let j = idx + 1; j < end; j++) {
      if (next[j].type === "task") next[j].done = true;
    }
    let cur = idx;
    while (true) {
      const p = parentIndex(next, cur);
      if (p < 0) break;
      if (descendantsAllDone(next, p)) {
        next[p].done = true;
        cur = p;
      } else break;
    }
  }
  return next;
}

// ---- Links ------------------------------------------------------------------
const URL_RE = /(https?:\/\/[^\s)]+)/g;

export function firstUrl(text) {
  URL_RE.lastIndex = 0;
  const m = URL_RE.exec(text || "");
  return m ? m[0] : null;
}
