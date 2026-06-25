export type IntegrationCategory =
  | "vcs"
  | "pm"
  | "notify"
  | "deploy"
  | "requirements"
  | "identity";

export type IntegrationAuthType =
  | "oauth2"
  | "api_key"
  | "webhook"
  | "smtp"
  | "service_principal";

export type ConnectionStatus =
  | "not_configured"
  | "connected"
  | "error"
  | "disabled";

export interface ConfigSchemaField {
  key: string;
  label: string;
  type: "text" | "secret" | "number" | "email";
  required: boolean;
  default?: string | number;
}

export interface PlatformIntegration {
  id: string;
  integrationKey: string;
  name: string;
  description: string;
  category: IntegrationCategory;
  authType: IntegrationAuthType;
  isEnabled: boolean;
  configSchema: { fields: ConfigSchemaField[] };
  documentationUrl?: string;
  connectionStatus: ConnectionStatus;
  connectionName?: string;
  lastTestedAt?: string;
  lastTestStatus?: boolean;
  lastErrorMessage?: string;
  configMetadata?: Record<string, string>;
}

export interface PlatformService {
  id: string;
  serviceKey: string;
  displayName: string;
  description: string;
  isEnabled: boolean;
  isConfigured: boolean;
  configMetadata: Record<string, string | number>;
  lastTestedAt?: string;
  lastTestStatus?: boolean;
  lastErrorMessage?: string;
}

export interface PlatformSetting {
  key: string;
  label: string;
  description: string;
  type: "string" | "boolean" | "number";
  value: string | boolean | number;
}

export const categoryLabels: Record<IntegrationCategory, string> = {
  vcs: "Source Control",
  pm: "Project Management",
  notify: "Notifications",
  deploy: "Deploy Targets",
  requirements: "Requirements",
  identity: "Identity",
};

export const authTypeLabels: Record<IntegrationAuthType, string> = {
  oauth2: "OAuth 2.0",
  api_key: "API Key",
  webhook: "Webhook",
  smtp: "SMTP",
  service_principal: "Service Principal",
};
