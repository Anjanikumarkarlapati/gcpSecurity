import {
  CheckCircle, Warning, WarningOctagon, Info, MinusCircle,
} from "@phosphor-icons/react";
import { STATE_LABEL } from "../api.js";

// Status is never colour alone: every tone has a colour, an icon shape and a word.
const TONES = {
  good: CheckCircle,
  warning: Warning,
  critical: WarningOctagon,
  info: Info,
  muted: MinusCircle,
};

export function Status({ tone, children }) {
  const Icon = TONES[tone];
  return (
    <span className={`status status-${tone}`}>
      <Icon size={16} weight="fill" aria-hidden="true" />
      {children}
    </span>
  );
}

const PRIORITY_TONE = { P1: "critical", P2: "warning", P3: "info", P4: "muted" };
const PRIORITY_WORD = { P1: "P1 Immediate", P2: "P2 Important", P3: "P3 Standard", P4: "P4 Low" };

export const PriorityStatus = ({ priority }) => (
  <Status tone={PRIORITY_TONE[priority] || "muted"}>{PRIORITY_WORD[priority] || priority}</Status>
);

const STATE_TONE = {
  NEW: "warning", TRIAGING: "info", ASSIGNED: "info", IN_REMEDIATION: "info",
  PENDING_VERIFICATION: "info", RESOLVED: "good", ACCEPTED_RISK: "muted", MUTED: "muted",
};

export const StateStatus = ({ state }) => (
  <Status tone={STATE_TONE[state] || "muted"}>{STATE_LABEL[state] || state}</Status>
);
