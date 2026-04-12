import { apiClient } from './client'

export interface ProviderModels {
  high_capability: string
  low_capability: string
}

export interface ProviderPricing {
  high_capability: { input: number; output: number }
  low_capability: { input: number; output: number }
}

export interface ProviderConfig {
  api_key_secret: string
  models: ProviderModels
  pricing_per_million_tokens: ProviderPricing
}

export interface AgentConfig {
  capability: 'high' | 'low'
  max_tokens: number
  temperature: number
  timeout_sec: number
  // Research-agent extras
  max_search_queries?: number
  max_sources?: number
  max_source_chars?: number
}

export interface WebSearchToolConfig {
  bing_secret_name: string
  serpapi_secret_name: string
  results_per_query: number
}

export interface FetchUrlToolConfig {
  timeout_sec: number
  max_content_bytes: number
  user_agent: string
}

export interface ResearchToolsConfig {
  web_search: WebSearchToolConfig
  fetch_url: FetchUrlToolConfig
}

export interface ModelConfig {
  version: string
  active_provider: string
  providers: Record<string, ProviderConfig>
  agents: Record<string, AgentConfig>
  research_tools: ResearchToolsConfig
}

export interface PromptsConfig {
  version: string
  [agent: string]: Record<string, string> | string
}

export interface ConfigResponse<T> {
  config: T
  source: 's3' | 'local'
}

export const configApi = {
  getModels: async (): Promise<ConfigResponse<ModelConfig>> => {
    const res = await apiClient.get('/admin/config/models')
    return res.data
  },

  saveModels: async (config: ModelConfig): Promise<{ message: string; config: ModelConfig }> => {
    const res = await apiClient.put('/admin/config/models', { config })
    return res.data
  },

  getPrompts: async (): Promise<ConfigResponse<PromptsConfig>> => {
    const res = await apiClient.get('/admin/config/prompts')
    return res.data
  },

  savePrompts: async (config: PromptsConfig): Promise<{ message: string; config: PromptsConfig }> => {
    const res = await apiClient.put('/admin/config/prompts', { config })
    return res.data
  },
}
