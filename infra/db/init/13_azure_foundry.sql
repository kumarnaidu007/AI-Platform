-- Microsoft Foundry (Azure OpenAI-compatible) LLM provider
INSERT INTO platform_services (service_key, display_name, description, is_enabled, config_metadata_json)
VALUES (
  'azure_foundry',
  'Microsoft Foundry',
  'Azure AI Foundry project endpoint — powers all agents via your deployed models',
  FALSE,
  '{"deployment_name":"claude-sonnet-4-6","embedding_deployment":"text-embedding-3-small"}'
)
ON CONFLICT (service_key) DO NOTHING;

INSERT INTO plan_platform_services (plan_id, platform_service_id)
SELECT p.id, ps.id
FROM plans p
CROSS JOIN platform_services ps
WHERE ps.service_key = 'azure_foundry'
ON CONFLICT DO NOTHING;
