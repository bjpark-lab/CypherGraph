import { z } from 'zod'

// ─── 그래프 관련 스키마 ───────────────────────────────────────────────────────

export const GraphNodeSchema = z.object({
  id: z.string(),
  labels: z.array(z.string()),
  properties: z.record(z.string(), z.unknown()).default({}),
})

export const GraphEdgeSchema = z.object({
  id: z.string(),
  type: z.string(),
  source: z.string(),
  target: z.string(),
  properties: z.record(z.string(), z.unknown()),
})

export const GraphResultSchema = z.object({
  nodes: z.array(GraphNodeSchema),
  edges: z.array(GraphEdgeSchema),
  raw: z.array(z.record(z.string(), z.unknown())),
})

// ─── 채팅 액션 스키마 ─────────────────────────────────────────────────────────

// 백엔드 ChatAction은 모든 필드를 플랫하게 반환하므로 단일 객체 스키마로 정의
export const ChatActionSchema = z.object({
  type: z.enum([
    'apply_query',
    'open_tab',
    'focus_node',
    'select_row',
    'set_filters',
    'create_chart',
    'highlight_series',
  ]),
  tab: z.string().nullable().optional(),
  query: z.string().nullable().optional(),
  node_id: z.string().nullable().optional(),
  row_id: z.string().nullable().optional(),
  filters: z.record(z.string(), z.unknown()).nullable().optional(),
  chart_config: z.record(z.string(), z.unknown()).nullable().optional(),
  series_id: z.string().nullable().optional(),
})

export const ToolResultSchema = z.object({
  graph: GraphResultSchema.nullable().optional(),
  table: z.array(z.record(z.string(), z.unknown())).nullable().optional(),
  chart: z.record(z.string(), z.unknown()).nullable().optional(),
  analytics: z.unknown().nullable().optional(),
  cypher: z.string().nullable().optional(),
  sql: z.string().nullable().optional(),
  sources: z.array(z.string()).nullable().optional(),
  summary: z.string().nullable().optional(),
})

export const ChatMessageSchema = z.object({
  role: z.enum(['user', 'assistant']),
  content: z.string(),
})

export const StepInfoSchema = z.object({
  tool: z.string(),
  tool_key: z.string(),
  input: z.string(),
  output: z.string(),
  reasoning: z.string().nullable().optional(),
})

export const ChatResponseSchema = z.object({
  message: z.string(),
  actions: z.array(ChatActionSchema).nullable().optional().default([]),
  tool_results: ToolResultSchema.nullable().optional(),
  steps: z.array(StepInfoSchema).optional().default([]),
  reasoning: z.string().nullable().optional(),
  trace_id: z.string().nullable().optional(),
  question_type: z.string().nullable().optional(),
  sources: z.array(z.string()).optional().default([]),
})

// ─── 쿼리 관련 스키마 ─────────────────────────────────────────────────────────

export const QueryResponseSchema = z.object({
  result: GraphResultSchema,
  cypher: z.string(),
  row_count: z.number(),
  execution_time_ms: z.number(),
})

// ─── 스키마 관련 ──────────────────────────────────────────────────────────────

export const SchemaResponseSchema = z.object({
  node_labels: z.array(z.string()),
  relationship_types: z.array(z.string()),
  node_properties: z.record(z.string(), z.array(z.string())),
  relationship_properties: z.record(z.string(), z.array(z.string())),
})

// ─── 헬스체크 ─────────────────────────────────────────────────────────────────

export const HealthResponseSchema = z.object({
  status: z.string(),
  neo4j_connected: z.boolean(),
  version: z.string().optional(),
})

// ─── 타입 추출 ────────────────────────────────────────────────────────────────

export type GraphNode = z.infer<typeof GraphNodeSchema>
export type GraphEdge = z.infer<typeof GraphEdgeSchema>
export type GraphResult = z.infer<typeof GraphResultSchema>
export type ChatAction = z.infer<typeof ChatActionSchema>
export type ToolResult = z.infer<typeof ToolResultSchema>
export type StepInfo = z.infer<typeof StepInfoSchema>
export type ChatMessage = z.infer<typeof ChatMessageSchema>
export type ChatResponse = z.infer<typeof ChatResponseSchema>
export type QueryResponse = z.infer<typeof QueryResponseSchema>
export type SchemaResponse = z.infer<typeof SchemaResponseSchema>
export type HealthResponse = z.infer<typeof HealthResponseSchema>
