import {
  bigint,
  boolean,
  doublePrecision,
  integer,
  jsonb,
  pgTable,
  real,
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
