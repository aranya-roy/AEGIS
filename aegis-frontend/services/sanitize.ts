export function sanitize(input: string): { text: string; count: number } {
  let count = 0;
  const sub = (re: RegExp, tag: string) => {
    input = input.replace(re, () => {
      count++;
      return tag;
    });
  };

  sub(/\b[\w.+-]+@[\w-]+\.[\w.]+\b/g, "[EMAIL]");
  sub(/\b[\w.-]{2,}@[a-z]{2,}\b/gi, "[UPI]");
  sub(/\b(?:\+?91[\s-]?)?[6-9]\d{9}\b/g, "[PHONE]");
  sub(/\bending\s+(?:in\s+)?\d{4}\b/gi, "ending [ACCOUNT]");
  sub(/\b\d{9,18}\b/g, "[ACCOUNT]");
  sub(/\b(?:Mr|Mrs|Ms|Dr)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?/g, "[NAME]");

  input = input.replace(
    /\b([Tt]his is|I am|I'm|my name is|Hi|Hello|Dear)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)/g,
    (_m, lead) => {
      count++;
      return `${lead} [NAME]`;
    }
  );

  return { text: input, count };
}