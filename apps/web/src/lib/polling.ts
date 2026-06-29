/** Shared polling intervals and status sets — keep API load predictable. */

export const POLL_INTAKE_MS = 5_000;
export const POLL_PIPELINE_MS = 5_000;
export const POLL_NOTIFICATIONS_MS = 60_000;
export const POLL_PROJECT_RUNS_MS = 5_000;

/** Intake statuses where we poll the intake API (spec generation, etc.). */
export const INTAKE_POLL_STATUSES = new Set(["analyzing", "drafting_specs"]);

/** Pipeline is running — poll run detail for agent step progress. */
export const PIPELINE_ACTIVE_STATUSES = new Set(["pending", "running", "awaiting_approval"]);

export function shouldPollIntake(status: string | undefined): boolean {
  return !!status && INTAKE_POLL_STATUSES.has(status);
}

export function shouldPollPipeline(status: string | undefined): boolean {
  return !!status && PIPELINE_ACTIVE_STATUSES.has(status);
}
