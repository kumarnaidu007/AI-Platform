import { Github, LayoutList, Box } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const iconMap: Record<string, LucideIcon> = {
  github: Github,
  jira: LayoutList,
};

export function IntegrationIcon({ integrationKey, className }: { integrationKey: string; className?: string }) {
  const Icon = iconMap[integrationKey] ?? Box;
  return <Icon className={className} />;
}
