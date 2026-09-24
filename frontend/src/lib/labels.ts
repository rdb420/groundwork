// Plain-language labels shared by the upload form and the library.
export const KINDS: [string, string][] = [
  ["spreadsheet", "Spreadsheet or tracker"],
  ["procedure", "Procedure, policy or instructions"],
  ["form", "Form, template or checklist"],
  ["report", "Report or export from a system"],
  ["email", "Email or message thread"],
  ["photo", "Photo or screenshot"],
  ["diagram", "Diagram or process map"],
  ["other", "Something else"],
];

export const LAYERS: [string, string, string][] = [
  ["declared", "How it's meant to be done", "An official procedure, policy or training material."],
  ["system", "What a system produces or needs", "A report, export or screen from software we use."],
  ["actual", "How I actually do it", "My own notes, checklist or the file I work from."],
  ["workaround", "A workaround we built", "Something we made because another tool didn't do the job."],
  ["unsure", "Not sure", "That's fine. We'll work it out together."],
];

export const FREQ: [string, string][] = [
  ["", "Not sure"], ["daily", "Daily"], ["weekly", "Weekly"], ["monthly", "Monthly"],
  ["quarterly", "Quarterly"], ["yearly", "Yearly"], ["adhoc", "When something comes up"],
];

export const STATUS: Record<string, string> = {
  received: "Waiting", processing: "Reading", processed: "Read", failed: "Needs a look", withdrawn: "Withdrawn",
  quarantined: "Blocked", purged: "Deleted",
};

export const label = (pairs: [string, string, ...string[]][], key: string) => pairs.find((p) => p[0] === key)?.[1] ?? key;

export const size = (b: number) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`);
