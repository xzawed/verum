import {
  bigint,
  boolean,
  date,
  doublePrecision,
  integer,
  jsonb,
  numeric,
  pgTable,
  real,
  smallint,
  text,
  timestamp,
  unique,
  uuid,
  varchar,
} from "drizzle-orm/pg-core";

export const users = pgTable("users", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  github_id: bigint("github_id", { mode: "number" }).notNull().unique(),
  github_login: varchar("github_login", { length: 64 }).notNull(),
  email: varchar("email", { length: 255 }),
  avatar_url: varchar("avatar_url", { length: 512 }),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  last_login_at: timestamp("last_login_at", { withTimezone: true }),
});

export const repos = pgTable(
  "repos",
  {
    id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
    github_url: text("github_url").notNull(),
    owner_user_id: uuid("owner_user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    default_branch: varchar("default_branch", { length: 255 }).notNull().default("main"),
    last_analyzed_at: timestamp("last_analyzed_at", { withTimezone: true }),
    created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [unique("uq_repos_owner_github_url").on(t.owner_user_id, t.github_url)],
);

export const analyses = pgTable("analyses", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  repo_id: uuid("repo_id")
    .notNull()
    .references(() => repos.id, { onDelete: "cascade" }),
  status: varchar("status", { length: 32 }).notNull().default("pending"),
  call_sites: jsonb("call_sites"),
  prompt_templates: jsonb("prompt_templates"),
  model_configs: jsonb("model_configs"),
  language_breakdown: jsonb("language_breakdown"),
  error: varchar("error", { length: 1024 }),
  analyzed_at: timestamp("analyzed_at", { withTimezone: true }),
  started_at: timestamp("started_at", { withTimezone: true }).notNull().defaultNow(),
});

export const inferences = pgTable("inferences", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  repo_id: uuid("repo_id").notNull(),
  analysis_id: uuid("analysis_id").notNull(),
  status: varchar("status", { length: 32 }).notNull().default("pending"),
  domain: varchar("domain", { length: 64 }),
  tone: varchar("tone", { length: 32 }),
  language: varchar("language", { length: 16 }),
  user_type: varchar("user_type", { length: 32 }),
  confidence: real("confidence"),
  summary: text("summary"),
  raw_response: jsonb("raw_response"),
  error: varchar("error", { length: 1024 }),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const harvest_sources = pgTable("harvest_sources", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  inference_id: uuid("inference_id")
    .notNull()
    .references(() => inferences.id, { onDelete: "cascade" }),
  url: text("url").notNull(),
  title: varchar("title", { length: 512 }),
  description: text("description"),
  status: varchar("status", { length: 32 }).notNull().default("proposed"),
  chunks_count: integer("chunks_count").notNull().default(0),
  error: varchar("error", { length: 1024 }),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const verum_jobs = pgTable("verum_jobs", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  kind: text("kind").notNull(),
  payload: jsonb("payload").notNull().default({}),
  status: text("status").notNull().default("queued"),
  owner_user_id: uuid("owner_user_id")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  result: jsonb("result"),
  error: text("error"),
  attempts: integer("attempts").notNull().default(0),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  started_at: timestamp("started_at", { withTimezone: true }),
  finished_at: timestamp("finished_at", { withTimezone: true }),
});

export const worker_heartbeat = pgTable("worker_heartbeat", {
  id: integer("id").primaryKey().default(1),
  last_seen_at: timestamp("last_seen_at", { withTimezone: true }).notNull().defaultNow(),
});

export const generations = pgTable("generations", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  inference_id: uuid("inference_id")
    .notNull()
    .references(() => inferences.id, { onDelete: "cascade" }),
  status: varchar("status", { length: 32 }).notNull().default("pending"),
  error: varchar("error", { length: 1024 }),
  metric_profile: jsonb("metric_profile"),
  generated_at: timestamp("generated_at", { withTimezone: true }),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const prompt_variants = pgTable("prompt_variants", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  generation_id: uuid("generation_id")
    .notNull()
    .references(() => generations.id, { onDelete: "cascade" }),
  variant_type: varchar("variant_type", { length: 32 }).notNull(),
  content: text("content").notNull(),
  variables: jsonb("variables"),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const rag_configs = pgTable("rag_configs", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  generation_id: uuid("generation_id")
    .notNull()
    .references(() => generations.id, { onDelete: "cascade" }),
  chunking_strategy: varchar("chunking_strategy", { length: 32 }).notNull().default("recursive"),
  chunk_size: integer("chunk_size").notNull().default(512),
  chunk_overlap: integer("chunk_overlap").notNull().default(50),
  top_k: integer("top_k").notNull().default(5),
  hybrid_alpha: doublePrecision("hybrid_alpha").notNull().default(0.7),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const eval_pairs = pgTable("eval_pairs", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  generation_id: uuid("generation_id")
    .notNull()
    .references(() => generations.id, { onDelete: "cascade" }),
  query: text("query").notNull(),
  expected_answer: text("expected_answer").notNull(),
  context_needed: boolean("context_needed").notNull().default(true),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const deployments = pgTable("deployments", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  generation_id: uuid("generation_id")
    .notNull()
    .references(() => generations.id, { onDelete: "cascade" }),
  status: varchar("status", { length: 32 }).notNull().default("canary"),
  traffic_split: jsonb("traffic_split").notNull().default({ baseline: 0.9, variant: 0.1 }),
  error_count: integer("error_count").notNull().default(0),
  total_calls: integer("total_calls").notNull().default(0),
  experiment_status: text("experiment_status").notNull().default("idle"),
  current_baseline_variant: text("current_baseline_variant").notNull().default("original"),
  apiKeyHash: text("api_key_hash").notNull(),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updated_at: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const model_pricing = pgTable("model_pricing", {
  id: uuid("id").primaryKey().defaultRandom(),
  model_name: text("model_name").notNull().unique(),
  input_per_1m_usd: numeric("input_per_1m_usd", { precision: 10, scale: 6 }).notNull(),
  output_per_1m_usd: numeric("output_per_1m_usd", { precision: 10, scale: 6 }).notNull(),
  provider: text("provider").notNull(),
  effective_from: timestamp("effective_from", { withTimezone: true }).notNull().defaultNow(),
});

export const traces = pgTable("traces", {
  id: uuid("id").primaryKey().defaultRandom(),
  deployment_id: uuid("deployment_id").notNull(),
  variant: text("variant").notNull().default("baseline"),
  user_feedback: smallint("user_feedback"),
  judge_score: doublePrecision("judge_score"),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const spans = pgTable("spans", {
  id: uuid("id").primaryKey().defaultRandom(),
  trace_id: uuid("trace_id").notNull(),
  model: text("model").notNull(),
  input_tokens: integer("input_tokens").notNull().default(0),
  output_tokens: integer("output_tokens").notNull().default(0),
  latency_ms: integer("latency_ms").notNull().default(0),
  cost_usd: numeric("cost_usd", { precision: 10, scale: 6 }).notNull().default("0"),
  error: text("error"),
  started_at: timestamp("started_at", { withTimezone: true }).notNull().defaultNow(),
  // Added migration 0023: raw OTLP span attributes for attribute-level queries
  span_attributes: jsonb("span_attributes"),
});

export const judge_prompts = pgTable("judge_prompts", {
  trace_id: uuid("trace_id").primaryKey(),
  prompt_sent: text("prompt_sent").notNull(),
  raw_response: text("raw_response").notNull(),
  judged_at: timestamp("judged_at", { withTimezone: true }).notNull().defaultNow(),
});

export const experiments = pgTable("experiments", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  deployment_id: uuid("deployment_id")
    .notNull()
    .references(() => deployments.id, { onDelete: "cascade" }),
  baseline_variant: text("baseline_variant").notNull(),
  challenger_variant: text("challenger_variant").notNull(),
  status: text("status").notNull().default("running"),
  winner_variant: text("winner_variant"),
  confidence: doublePrecision("confidence"),
  baseline_wins: integer("baseline_wins").notNull().default(0),
  baseline_n: integer("baseline_n").notNull().default(0),
  challenger_wins: integer("challenger_wins").notNull().default(0),
  challenger_n: integer("challenger_n").notNull().default(0),
  win_threshold: doublePrecision("win_threshold").notNull().default(0.6),
  cost_weight: doublePrecision("cost_weight").notNull().default(0.1),
  started_at: timestamp("started_at", { withTimezone: true }).notNull().defaultNow(),
  converged_at: timestamp("converged_at", { withTimezone: true }),
});

export const chunks = pgTable("chunks", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  source_id: uuid("source_id")
    .notNull()
    .references(() => harvest_sources.id, { onDelete: "cascade" }),
  inference_id: uuid("inference_id")
    .notNull()
    .references(() => inferences.id, { onDelete: "cascade" }),
  content: text("content").notNull(),
  chunk_index: integer("chunk_index").notNull().default(0),
  metadata: jsonb("metadata"),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const usage_quotas = pgTable("usage_quotas", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  user_id: uuid("user_id")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  period_start: date("period_start").notNull(),
  plan: text("plan").notNull().default("free"),
  traces_used: integer("traces_used").notNull().default(0),
  chunks_stored: integer("chunks_stored").notNull().default(0),
  repos_connected: integer("repos_connected").notNull().default(0),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updated_at: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const sdk_pr_requests = pgTable("sdk_pr_requests", {
  id: uuid("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
  repo_id: uuid("repo_id")
    .notNull()
    .references(() => repos.id, { onDelete: "cascade" }),
  owner_user_id: uuid("owner_user_id")
    .notNull()
    .references(() => users.id, { onDelete: "cascade" }),
  analysis_id: uuid("analysis_id")
    .notNull()
    .references(() => analyses.id, { onDelete: "cascade" }),
  mode: varchar("mode", { length: 32 }).notNull().default("observe"),
  status: varchar("status", { length: 32 }).notNull().default("pending"),
  pr_url: text("pr_url"),
  pr_number: integer("pr_number"),
  branch_name: varchar("branch_name", { length: 255 }),
  files_changed: integer("files_changed").notNull().default(0),
  error: text("error"),
  created_at: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updated_at: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export type Experiment = typeof experiments.$inferSelect;

export type User = typeof users.$inferSelect;
export type Repo = typeof repos.$inferSelect;
export type Analysis = typeof analyses.$inferSelect;
export type Inference = typeof inferences.$inferSelect;
export type HarvestSource = typeof harvest_sources.$inferSelect;
export type VerumJob = typeof verum_jobs.$inferSelect;
export type Generation = typeof generations.$inferSelect;
export type PromptVariant = typeof prompt_variants.$inferSelect;
export type RagConfig = typeof rag_configs.$inferSelect;
export type EvalPair = typeof eval_pairs.$inferSelect;
export type Deployment = typeof deployments.$inferSelect;
export type ModelPricing = typeof model_pricing.$inferSelect;
export type Trace = typeof traces.$inferSelect;
export type Span = typeof spans.$inferSelect;
export type JudgePrompt = typeof judge_prompts.$inferSelect;
export type Chunk = typeof chunks.$inferSelect;
export type UsageQuota = typeof usage_quotas.$inferSelect;
export type SdkPrRequest = typeof sdk_pr_requests.$inferSelect;
