import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { configApi, type ModelConfig, type PromptsConfig } from '../api/config'
import styles from './ConfigPage.module.css'

// ── Agent display metadata ────────────────────────────────────────────────────

const AGENT_LABELS: Record<string, string> = {
  planner: 'Planner',
  research: 'Research',
  verifier: 'Verifier',
  writer: 'Writer',
  editor: 'Editor',
  diff: 'Diff',
}

const AGENT_ORDER = ['planner', 'research', 'verifier', 'writer', 'editor', 'diff']

// Prompt key display labels per agent
const PROMPT_KEY_LABELS: Record<string, Record<string, string>> = {
  planner: { system: 'System prompt', user: 'User prompt' },
  research: { synthesis_system: 'Synthesis system', synthesis_user: 'Synthesis user' },
  verifier: { system: 'System prompt', user: 'User prompt' },
  writer: { system: 'System prompt', user: 'User prompt' },
  editor: { system: 'System prompt', user: 'User prompt' },
  diff: {
    first_version_system: 'First version — system',
    first_version_user: 'First version — user',
    incremental_system: 'Incremental — system',
    incremental_user: 'Incremental — user',
  },
}

// ── Model Config Tab ──────────────────────────────────────────────────────────

function ModelConfigTab({ config, onChange }: { config: ModelConfig; onChange: (c: ModelConfig) => void }) {
  const [activeProvider, setActiveProvider] = useState(config.active_provider ?? 'openai')
  const providers = Object.keys(config.providers ?? {})

  const setProvider = (p: string) => {
    setActiveProvider(p)
    onChange({ ...config, active_provider: p })
  }

  const setProviderField = (provider: string, field: string, value: string) => {
    onChange({
      ...config,
      providers: {
        ...config.providers,
        [provider]: {
          ...config.providers[provider],
          [field]: value,
        },
      },
    })
  }

  const setProviderModel = (provider: string, tier: 'high_capability' | 'low_capability', value: string) => {
    onChange({
      ...config,
      providers: {
        ...config.providers,
        [provider]: {
          ...config.providers[provider],
          models: { ...config.providers[provider].models, [tier]: value },
        },
      },
    })
  }

  const setProviderPricing = (
    provider: string,
    tier: 'high_capability' | 'low_capability',
    dir: 'input' | 'output',
    value: string,
  ) => {
    const num = parseFloat(value) || 0
    onChange({
      ...config,
      providers: {
        ...config.providers,
        [provider]: {
          ...config.providers[provider],
          pricing_per_million_tokens: {
            ...config.providers[provider].pricing_per_million_tokens,
            [tier]: {
              ...config.providers[provider].pricing_per_million_tokens?.[tier],
              [dir]: num,
            },
          },
        },
      },
    })
  }

  const setAgentField = (agent: string, field: string, value: string | number) => {
    onChange({
      ...config,
      agents: {
        ...config.agents,
        [agent]: { ...config.agents[agent], [field]: value },
      },
    })
  }

  const setResearchTool = (tool: 'web_search' | 'fetch_url', field: string, value: string | number) => {
    onChange({
      ...config,
      research_tools: {
        ...config.research_tools,
        [tool]: { ...config.research_tools?.[tool], [field]: value },
      },
    })
  }

  const prov = config.providers?.[activeProvider] ?? {}
  const pricing = prov.pricing_per_million_tokens ?? {}

  return (
    <div>
      {/* ── Active provider ── */}
      <div className={styles.section}>
        <p className={styles.sectionTitle}>Active Provider</p>
        <div className={styles.field}>
          <label className={styles.label}>Provider</label>
          <select
            className={styles.select}
            style={{ maxWidth: 200 }}
            value={config.active_provider}
            onChange={(e) => setProvider(e.target.value)}
          >
            {providers.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <span className={styles.hint}>All agents will use this provider's models.</span>
        </div>
      </div>

      {/* ── Provider settings ── */}
      <div className={styles.section}>
        <p className={styles.sectionTitle}>Provider Settings</p>
        <div className={styles.providerTabs}>
          {providers.map((p) => (
            <button
              key={p}
              className={`${styles.providerTab} ${activeProvider === p ? styles.providerTabActive : ''}`}
              onClick={() => setActiveProvider(p)}
            >
              {p}
            </button>
          ))}
        </div>

        <div className={styles.field}>
          <label className={styles.label}>API Key Secret (Secrets Manager name)</label>
          <input
            className={styles.input}
            value={prov.api_key_secret ?? ''}
            onChange={(e) => setProviderField(activeProvider, 'api_key_secret', e.target.value)}
          />
        </div>

        <div className={styles.grid2} style={{ marginTop: 12 }}>
          <div className={styles.field}>
            <label className={styles.label}>High-capability model</label>
            <input
              className={styles.input}
              value={prov.models?.high_capability ?? ''}
              onChange={(e) => setProviderModel(activeProvider, 'high_capability', e.target.value)}
            />
            <span className={styles.hint}>Used by Writer agent</span>
          </div>
          <div className={styles.field}>
            <label className={styles.label}>Low-capability model</label>
            <input
              className={styles.input}
              value={prov.models?.low_capability ?? ''}
              onChange={(e) => setProviderModel(activeProvider, 'low_capability', e.target.value)}
            />
            <span className={styles.hint}>Used by all other agents</span>
          </div>
        </div>

        <p className={styles.sectionTitle} style={{ marginTop: 16 }}>Pricing (per million tokens)</p>
        <div className={styles.grid2}>
          <div>
            <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-muted)', marginBottom: 8 }}>High-capability</p>
            <div className={styles.grid2}>
              <div className={styles.field}>
                <label className={styles.label}>Input $</label>
                <input
                  className={styles.input}
                  type="number"
                  step="0.01"
                  value={pricing.high_capability?.input ?? ''}
                  onChange={(e) => setProviderPricing(activeProvider, 'high_capability', 'input', e.target.value)}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>Output $</label>
                <input
                  className={styles.input}
                  type="number"
                  step="0.01"
                  value={pricing.high_capability?.output ?? ''}
                  onChange={(e) => setProviderPricing(activeProvider, 'high_capability', 'output', e.target.value)}
                />
              </div>
            </div>
          </div>
          <div>
            <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-muted)', marginBottom: 8 }}>Low-capability</p>
            <div className={styles.grid2}>
              <div className={styles.field}>
                <label className={styles.label}>Input $</label>
                <input
                  className={styles.input}
                  type="number"
                  step="0.01"
                  value={pricing.low_capability?.input ?? ''}
                  onChange={(e) => setProviderPricing(activeProvider, 'low_capability', 'input', e.target.value)}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>Output $</label>
                <input
                  className={styles.input}
                  type="number"
                  step="0.01"
                  value={pricing.low_capability?.output ?? ''}
                  onChange={(e) => setProviderPricing(activeProvider, 'low_capability', 'output', e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Agent routing ── */}
      <div className={styles.section}>
        <p className={styles.sectionTitle}>Agent Model Routing</p>
        <table className={styles.agentTable}>
          <thead>
            <tr>
              <th>Agent</th>
              <th>Capability</th>
              <th>Max tokens</th>
              <th>Temperature</th>
              <th>Timeout (s)</th>
            </tr>
          </thead>
          <tbody>
            {AGENT_ORDER.filter((a) => config.agents?.[a]).map((agent) => {
              const ag = config.agents[agent]
              return (
                <tr key={agent}>
                  <td>
                    <span className={styles.agentName}>{AGENT_LABELS[agent] ?? agent}</span>
                  </td>
                  <td>
                    <select
                      className={styles.tableSelect}
                      value={ag.capability}
                      onChange={(e) => setAgentField(agent, 'capability', e.target.value)}
                    >
                      <option value="high">high</option>
                      <option value="low">low</option>
                    </select>
                  </td>
                  <td>
                    <input
                      className={styles.tableInput}
                      type="number"
                      value={ag.max_tokens}
                      onChange={(e) => setAgentField(agent, 'max_tokens', parseInt(e.target.value) || 0)}
                    />
                  </td>
                  <td>
                    <input
                      className={styles.tableInput}
                      type="number"
                      step="0.05"
                      value={ag.temperature}
                      onChange={(e) => setAgentField(agent, 'temperature', parseFloat(e.target.value) || 0)}
                    />
                  </td>
                  <td>
                    <input
                      className={styles.tableInput}
                      type="number"
                      value={ag.timeout_sec}
                      onChange={(e) => setAgentField(agent, 'timeout_sec', parseInt(e.target.value) || 0)}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {/* Research agent extras */}
        {config.agents?.research && (
          <div style={{ marginTop: 16 }}>
            <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-muted)', marginBottom: 10 }}>
              Research agent extra settings
            </p>
            <div className={styles.grid3}>
              <div className={styles.field}>
                <label className={styles.label}>Max search queries</label>
                <input
                  className={styles.input}
                  type="number"
                  value={config.agents.research.max_search_queries ?? 6}
                  onChange={(e) => setAgentField('research', 'max_search_queries', parseInt(e.target.value) || 0)}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>Max sources</label>
                <input
                  className={styles.input}
                  type="number"
                  value={config.agents.research.max_sources ?? 10}
                  onChange={(e) => setAgentField('research', 'max_sources', parseInt(e.target.value) || 0)}
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label}>Max source chars</label>
                <input
                  className={styles.input}
                  type="number"
                  value={config.agents.research.max_source_chars ?? 4000}
                  onChange={(e) => setAgentField('research', 'max_source_chars', parseInt(e.target.value) || 0)}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Research tools ── */}
      <div className={styles.section}>
        <p className={styles.sectionTitle}>Research Tool Settings</p>
        <div className={styles.grid2}>
          <div className={styles.field}>
            <label className={styles.label}>Results per query</label>
            <input
              className={styles.input}
              type="number"
              value={config.research_tools?.web_search?.results_per_query ?? 5}
              onChange={(e) => setResearchTool('web_search', 'results_per_query', parseInt(e.target.value) || 0)}
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label}>Fetch URL timeout (s)</label>
            <input
              className={styles.input}
              type="number"
              value={config.research_tools?.fetch_url?.timeout_sec ?? 15}
              onChange={(e) => setResearchTool('fetch_url', 'timeout_sec', parseInt(e.target.value) || 0)}
            />
          </div>
        </div>
        <div className={styles.grid2}>
          <div className={styles.field}>
            <label className={styles.label}>Bing API key secret name</label>
            <input
              className={styles.input}
              placeholder="Leave empty to skip"
              value={config.research_tools?.web_search?.bing_secret_name ?? ''}
              onChange={(e) => setResearchTool('web_search', 'bing_secret_name', e.target.value)}
            />
          </div>
          <div className={styles.field}>
            <label className={styles.label}>SerpAPI key secret name</label>
            <input
              className={styles.input}
              placeholder="Leave empty to skip"
              value={config.research_tools?.web_search?.serpapi_secret_name ?? ''}
              onChange={(e) => setResearchTool('web_search', 'serpapi_secret_name', e.target.value)}
            />
          </div>
        </div>
        <div className={styles.field}>
          <label className={styles.label}>Fetch URL user agent</label>
          <input
            className={styles.input}
            value={config.research_tools?.fetch_url?.user_agent ?? ''}
            onChange={(e) => setResearchTool('fetch_url', 'user_agent', e.target.value)}
          />
        </div>
      </div>
    </div>
  )
}

// ── Prompts Tab ───────────────────────────────────────────────────────────────

function PromptsTab({ config, onChange }: { config: PromptsConfig; onChange: (c: PromptsConfig) => void }) {
  const [openAgents, setOpenAgents] = useState<Set<string>>(new Set(['planner']))

  const toggleAgent = (agent: string) => {
    setOpenAgents((prev) => {
      const next = new Set(prev)
      next.has(agent) ? next.delete(agent) : next.add(agent)
      return next
    })
  }

  const setPromptKey = (agent: string, key: string, value: string) => {
    onChange({
      ...config,
      [agent]: {
        ...(config[agent] as Record<string, string>),
        [key]: value,
      },
    })
  }

  const agents = AGENT_ORDER.filter((a) => config[a])

  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--color-muted)', marginBottom: 20 }}>
        Use <code style={{ background: 'var(--color-surface)', padding: '1px 5px', borderRadius: 4 }}>{'${variable_name}'}</code> syntax for template variables.
        Changes are saved to S3 and picked up by workers on their next cold start.
      </p>

      {agents.map((agent) => {
        const isOpen = openAgents.has(agent)
        const agentData = config[agent] as Record<string, string>
        const keyLabels = PROMPT_KEY_LABELS[agent] ?? {}

        return (
          <div key={agent} className={styles.promptAgent}>
            <button
              className={styles.promptAgentHeader}
              onClick={() => toggleAgent(agent)}
            >
              <span>{AGENT_LABELS[agent] ?? agent} Agent</span>
              <span className={`${styles.chevron} ${isOpen ? styles.chevronOpen : ''}`}>▼</span>
            </button>

            {isOpen && (
              <div className={styles.promptAgentBody}>
                {Object.entries(agentData).map(([key, value]) => (
                  <div key={key}>
                    <div className={styles.promptKeyLabel}>
                      {keyLabels[key] ?? key}
                    </div>
                    <textarea
                      className={styles.textarea}
                      style={{ minHeight: key.includes('user') || key.includes('User') ? 200 : 120 }}
                      value={value}
                      onChange={(e) => setPromptKey(agent, key, e.target.value)}
                      spellCheck={false}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ConfigPage() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<'models' | 'prompts'>('models')
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [errMsg, setErrMsg] = useState<string | null>(null)

  // Local edits (start as null until data loads)
  const [modelEdits, setModelEdits] = useState<ModelConfig | null>(null)
  const [promptEdits, setPromptEdits] = useState<PromptsConfig | null>(null)

  const { data: modelData, isLoading: modelLoading } = useQuery({
    queryKey: ['config-models'],
    queryFn: configApi.getModels,
  })

  const { data: promptData, isLoading: promptLoading } = useQuery({
    queryKey: ['config-prompts'],
    queryFn: configApi.getPrompts,
  })

  // Seed local edit state once data arrives
  useEffect(() => {
    if (modelData && !modelEdits) setModelEdits(modelData.config)
  }, [modelData]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (promptData && !promptEdits) setPromptEdits(promptData.config)
  }, [promptData]) // eslint-disable-line react-hooks/exhaustive-deps

  const modelMutation = useMutation({
    mutationFn: configApi.saveModels,
    onSuccess: (_data: { message: string; config: ModelConfig }) => {
      qc.invalidateQueries({ queryKey: ['config-models'] })
      setSaveMsg('Model config saved.')
      setErrMsg(null)
      setTimeout(() => setSaveMsg(null), 3000)
    },
    onError: (e: Error) => { setErrMsg(e.message); setSaveMsg(null) },
  })

  const promptMutation = useMutation({
    mutationFn: configApi.savePrompts,
    onSuccess: (_data: { message: string; config: PromptsConfig }) => {
      qc.invalidateQueries({ queryKey: ['config-prompts'] })
      setSaveMsg('Prompts saved.')
      setErrMsg(null)
      setTimeout(() => setSaveMsg(null), 3000)
    },
    onError: (e: Error) => { setErrMsg(e.message); setSaveMsg(null) },
  })

  // Seed local state from query once
  const activeModel = modelEdits ?? modelData?.config
  const activePrompts = promptEdits ?? promptData?.config

  const handleSave = () => {
    setSaveMsg(null)
    setErrMsg(null)
    if (tab === 'models' && activeModel) {
      modelMutation.mutate(activeModel)
    } else if (tab === 'prompts' && activePrompts) {
      promptMutation.mutate(activePrompts)
    }
  }

  const handleReset = () => {
    if (tab === 'models') setModelEdits(modelData?.config ?? null)
    if (tab === 'prompts') setPromptEdits(promptData?.config ?? null)
    setSaveMsg(null)
    setErrMsg(null)
  }

  const isSaving = modelMutation.isPending || promptMutation.isPending
  const isLoading = tab === 'models' ? modelLoading : promptLoading
  const source = tab === 'models' ? modelData?.source : promptData?.source

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>LLM Configuration</h1>
        <p className={styles.subtitle}>
          Manage model routing and agent prompts. Changes are saved to S3 and picked up on the next Lambda cold start.
        </p>
      </div>

      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${tab === 'models' ? styles.tabActive : ''}`}
          onClick={() => { setTab('models'); setSaveMsg(null); setErrMsg(null) }}
        >
          Model Config
        </button>
        <button
          className={`${styles.tab} ${tab === 'prompts' ? styles.tabActive : ''}`}
          onClick={() => { setTab('prompts'); setSaveMsg(null); setErrMsg(null) }}
        >
          Prompts
        </button>
      </div>

      {isLoading ? (
        <div style={{ padding: 40, textAlign: 'center' }}><span className="spin" /></div>
      ) : (
        <>
          {tab === 'models' && activeModel && (
            <ModelConfigTab
              config={activeModel}
              onChange={setModelEdits}
            />
          )}
          {tab === 'prompts' && activePrompts && (
            <PromptsTab
              config={activePrompts}
              onChange={setPromptEdits}
            />
          )}

          <div className={styles.actions}>
            <button className="btn-primary" onClick={handleSave} disabled={isSaving}>
              {isSaving ? <span className="spin" /> : 'Save changes'}
            </button>
            <button className="btn-secondary" onClick={handleReset} disabled={isSaving}>
              Reset
            </button>
            {source && (
              <span className={styles.sourceBadge}>
                source: {source}
              </span>
            )}
            {saveMsg && <span className={styles.saveMsg}>✓ {saveMsg}</span>}
            {errMsg && <span className={styles.errMsg}>✗ {errMsg}</span>}
          </div>
        </>
      )}
    </div>
  )
}
