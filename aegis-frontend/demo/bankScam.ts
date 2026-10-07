import { AegisEvent } from "@/types/events";

export const bankScam: AegisEvent[] = [
  { type: "transcript", at: 500, speaker: "caller", text: "Hello Mr. Ravi Kumar, this is Amit Sharma calling from SBI head office. Your account ending 4821 has suspicious activity." },
  { type: "signal", at: 1200, label: "Authority impersonation", severity: "warn", evidence: "Claims to represent the bank" },
  { type: "graph_node", at: 1300, id: "n1", label: "Bank impersonation" },
  { type: "stage", at: 1400, stage: "AUTHORITY", progress: 0.3, reason: "Caller invoked institutional authority." },
  { type: "risk", at: 1500, level: "WATCH", drivers: ["Unexpected contact", "Authority claim"] },

  { type: "transcript", at: 4000, speaker: "caller", text: "Sir, your account will be frozen in 10 minutes. Call me back on 9876543210 only." },
  { type: "signal", at: 4600, label: "Urgency created", severity: "warn", evidence: "10-minute deadline" },
  { type: "graph_node", at: 4700, id: "n2", label: "Account threat", parent: "n1" },
  { type: "graph_node", at: 4900, id: "n3", label: "Urgency", parent: "n2" },
  { type: "stage", at: 5000, stage: "URGENCY", progress: 0.6, reason: "Caller applied time pressure with a short deadline." },
  { type: "scam_dna", at: 5400, matchPct: 71, pattern: "Remote-access financial fraud", incidents: 3 },
  { type: "risk", at: 5600, level: "INTERVENE", drivers: ["Urgency being created", "71% pattern match"] },

  { type: "transcript", at: 8000, speaker: "caller", text: "Do not disconnect. Install this app, then confirm with your UPI ID ravi.k@oksbi." },
  { type: "signal", at: 8600, label: "Remote-access request", severity: "critical", evidence: "Asked to install another application" },
  { type: "graph_node", at: 8700, id: "n4", label: "Isolation", parent: "n3" },
  { type: "graph_node", at: 8900, id: "n5", label: "Remote access", parent: "n4" },
  { type: "stage", at: 9000, stage: "COMPLIANCE", progress: 0.85, reason: "Caller told the user not to disconnect and to install software." },
  { type: "scam_dna", at: 9200, matchPct: 87, pattern: "Remote-access financial fraud", incidents: 3 },
  { type: "shadowpath", at: 9800, next: "Credential request", confidence: 84, evidence: ["Remote access already requested", "Same sequence seen in matched pattern"] },
  { type: "graph_node", at: 9900, id: "n6", label: "Credential request", parent: "n5", predicted: true },
  { type: "risk", at: 10200, level: "CRITICAL", drivers: ["Remote-access request", "87% pattern match", "Financial action approaching"] },
  { type: "reality_pause", at: 11500, reasons: ["Unexpected contact", "Urgency being created", "Request to install another app", "Financial action approaching"] },
];