import {
  Bot,
  CheckCircle2,
  ClipboardList,
  Code2,
  FileSearch,
  FlaskConical,
  GitPullRequest,
  Layers,
  PlayCircle,
  Rocket,
  Search,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

const iconMap: Record<string, LucideIcon> = {
  requirements: ClipboardList,
  architecture: Layers,
  task_planner: FileSearch,
  code_writer: Code2,
  review: GitPullRequest,
  test_writer: FlaskConical,
  test_runner: PlayCircle,
  deploy: Rocket,
  smoke_test: Search,
  validation: CheckCircle2,
};

export function AgentIcon({ agentKey, className }: { agentKey: string; className?: string }) {
  const Icon = iconMap[agentKey] ?? Bot;
  return <Icon className={className} />;
}
