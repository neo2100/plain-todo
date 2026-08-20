// Plain-text <-> structured line helpers for Plain Todo.

export function parseLine(line) {
  const m = line.match(/^(\s*)(.*)$/);
  const rawIndent = m[1].replace(/\t/g, "  ");
  const indent = Math.floor(rawIndent.length / 2);
  const rest = m[2];
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

const URL_RE = /(https?:\/\/[^\s)]+)/g;

// Returns array of { text, url? } segments for rendering links.
export function linkify(text) {
  const parts = [];
  let last = 0;
  let match;
  URL_RE.lastIndex = 0;
  while ((match = URL_RE.exec(text)) !== null) {
    if (match.index > last) parts.push({ text: text.slice(last, match.index) });
    parts.push({ text: match[0], url: match[0] });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last) });
  return parts;
}

export function firstUrl(text) {
  URL_RE.lastIndex = 0;
  const m = URL_RE.exec(text || "");
  return m ? m[0] : null;
}
