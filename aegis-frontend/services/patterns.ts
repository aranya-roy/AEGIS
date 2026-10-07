import type { Incident, Step } from "@/demo/incidents";

function lcs(a: Step[], b: Step[]): number {
  const dp = Array.from({ length: a.length + 1 }, () => Array(b.length + 1).fill(0));
  for (let i = 1; i <= a.length; i++)
    for (let j = 1; j <= b.length; j++)
      dp[i][j] = a[i - 1] === b[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1]);
  return dp[a.length][b.length];
}

const similarity = (a: Step[], b: Step[]) => (2 * lcs(a, b)) / (a.length + b.length);

export function averagePairSimilarity(list: Incident[]): number {
  let sum = 0, n = 0;
  for (let i = 0; i < list.length; i++)
    for (let j = i + 1; j < list.length; j++) {
      sum += similarity(list[i].steps, list[j].steps);
      n++;
    }
  return n ? sum / n : 0;
}

function lastMatchIndex(partial: Step[], steps: Step[]): number {
  let j = 0;
  for (let i = 0; i < steps.length; i++) {
    if (steps[i] === partial[j]) {
      j++;
      if (j === partial.length) return i;
    }
  }
  return -1;
}

export function predictNext(partial: Step[], known: Incident[]) {
  const votes: Partial<Record<Step, number>> = {};
  let matching = 0;
  for (const inc of known) {
    const idx = lastMatchIndex(partial, inc.steps);
    if (idx >= 0 && idx + 1 < inc.steps.length) {
      matching++;
      const next = inc.steps[idx + 1];
      votes[next] = (votes[next] ?? 0) + 1;
    }
  }
  const best = (Object.entries(votes) as [Step, number][]).sort((a, b) => b[1] - a[1])[0];
  return best ? { next: best[0], votes: best[1], total: matching } : null;
}