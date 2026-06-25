import {
  Cloud,
  Container,
  Github,
  Gitlab,
  LayoutList,
  Mail,
  MessageSquare,
  FileText,
  Box,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

const iconMap: Record<string, LucideIcon> = {
  github: Github,
  gitlab: Gitlab,
  azure_devops: Cloud,
  bitbucket: Box,
  jira: LayoutList,
  azure_boards: LayoutList,
  linear: LayoutList,
  notion: FileText,
  confluence: FileText,
  teams: MessageSquare,
  slack: MessageSquare,
  email: Mail,
  azure: Cloud,
  aws: Cloud,
  gcp: Cloud,
  docker_registry: Container,
};

export function IntegrationIcon({ integrationKey, className }: { integrationKey: string; className?: string }) {
  const Icon = iconMap[integrationKey] ?? Box;
  return <Icon className={className} />;
}
