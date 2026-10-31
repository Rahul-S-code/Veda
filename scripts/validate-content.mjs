// Checks every card in content/*.json has the fields the app expects.
// Run: node scripts/validate-content.mjs
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const dir = new URL("../content/", import.meta.url).pathname;
const files = readdirSync(dir).filter((f) => f.startsWith("cards.") && f.endsWith(".json"));
const required = ["id", "scripture", "reference", "sanskrit", "transliteration", "translation", "meaning", "story", "teaching", "test", "tags"];
const errors = [];
const ids = new Set();
let count = 0;

for (const file of files) {
  const cards = JSON.parse(readFileSync(join(dir, file), "utf8"));
  for (const card of cards) {
    count++;
    const where = `${file} › ${card.id ?? "(no id)"}`;
    for (const key of required) if (card[key] == null || card[key] === "") errors.push(`${where}: missing ${key}`);
    if (ids.has(card.id)) errors.push(`${where}: duplicate id`);
    ids.add(card.id);
    if (!card.story?.title || !card.story?.text) errors.push(`${where}: story needs title and text`);
    if (!card.teaching?.title || !card.teaching?.practice) errors.push(`${where}: teaching needs title and practice`);
    if (!Array.isArray(card.test) || card.test.length < 2) errors.push(`${where}: needs at least 2 test questions`);
    for (const [i, q] of (card.test ?? []).entries()) {
      if (!q.question || !Array.isArray(q.options) || q.options.length < 2) errors.push(`${where}: test ${i + 1} malformed`);
      else if (!Number.isInteger(q.answer) || q.answer < 0 || q.answer >= q.options.length) errors.push(`${where}: test ${i + 1} answer index out of range`);
    }
  }
}

if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}
console.log(`OK: ${count} cards across ${files.length} files`);
