#!/usr/bin/env python3
"""Demo seed script — creates realistic ArcanaInsight demo data in Verum DB.

Demonstrates the full Verum Loop in action:
  ANALYZE → INFER → HARVEST → GENERATE → DEPLOY → OBSERVE → EXPERIMENT → EVOLVE

Idempotent: uses ON CONFLICT DO NOTHING everywhere.
Run from repo root: cd apps/api && python ../../scripts/seed_demo.py
"""

import asyncio
import hashlib
import json
import os
import random
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Engine setup
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def days_ago(n: float) -> datetime:
    return now_utc() - timedelta(days=n)


def hours_ago(n: float) -> datetime:
    return now_utc() - timedelta(hours=n)


def rand_embedding(dim: int = 1024) -> list[float]:
    """Generate a plausible random embedding vector (Gaussian, unit-ish)."""
    raw = [random.gauss(0, 0.1) for _ in range(dim)]
    norm = sum(x * x for x in raw) ** 0.5 or 1.0
    return [round(x / norm, 6) for x in raw]


def clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

async def seed_model_pricing(session) -> None:
    """Insert standard model pricing rows (idempotent)."""
    print("  → model_pricing")
    models = [
        ("grok-2-1212",      5.0,   10.0,  "xai"),
        ("grok-2-mini",      0.3,    0.5,  "xai"),
        ("claude-sonnet-4-6", 3.0,  15.0,  "anthropic"),
        ("claude-haiku-4-5", 0.25,   1.25, "anthropic"),
        ("gpt-4o",           5.0,   15.0,  "openai"),
        ("gpt-4o-mini",      0.15,   0.6,  "openai"),
    ]
    for model_name, inp, out, provider in models:
        await session.execute(text("""
            INSERT INTO model_pricing (id, model_name, input_per_1m_usd, output_per_1m_usd, provider, effective_from)
            VALUES (:id, :model_name, :inp, :out, :provider, :eff)
            ON CONFLICT (model_name) DO NOTHING
        """), {
            "id": str(uuid.uuid4()),
            "model_name": model_name,
            "inp": str(inp),
            "out": str(out),
            "provider": provider,
            "eff": days_ago(90),
        })


async def seed_user(session) -> str:
    """Insert demo user. Returns user_id."""
    print("  → users")
    user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "demo-user-verum"))
    await session.execute(text("""
        INSERT INTO users (id, github_id, github_login, email, avatar_url, created_at, last_login_at)
        VALUES (:id, :github_id, :login, :email, :avatar, :created_at, :last_login)
        ON CONFLICT (id) DO NOTHING
    """), {
        "id": user_id,
        "github_id": 99999999,
        "login": "demo",
        "email": "demo@verum.dev",
        "avatar": "https://avatars.githubusercontent.com/u/99999999",
        "created_at": days_ago(30),
        "last_login": hours_ago(1),
    })
    return user_id


async def seed_repo(session, user_id: str) -> str:
    """Insert ArcanaInsight repo. Returns repo_id."""
    print("  → repos")
    repo_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "arcanainsight-repo-verum"))
    await session.execute(text("""
        INSERT INTO repos (id, github_url, owner_user_id, default_branch, last_analyzed_at, created_at)
        VALUES (:id, :url, :owner, :branch, :analyzed, :created)
        ON CONFLICT (id) DO NOTHING
    """), {
        "id": repo_id,
        "url": "https://github.com/xzawed/ArcanaInsight",
        "owner": user_id,
        "branch": "main",
        "analyzed": days_ago(14),
        "created": days_ago(30),
    })
    return repo_id


async def seed_analysis(session, repo_id: str) -> str:
    """Insert ANALYZE stage result. Returns analysis_id."""
    print("  → analyses")
    analysis_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "arcanainsight-analysis-verum"))

    call_sites = [
        # 4 grok calls
        {"id": 1, "file": "src/lib/tarot/reading.ts",       "line": 87,  "provider": "grok",      "model": "grok-2-1212",   "function": "chat.completions.create"},
        {"id": 2, "file": "src/lib/tarot/interpretation.ts","line": 142, "provider": "grok",      "model": "grok-2-1212",   "function": "chat.completions.create"},
        {"id": 3, "file": "src/lib/tarot/spread.ts",        "line": 63,  "provider": "grok",      "model": "grok-2-mini",   "function": "chat.completions.create"},
        {"id": 4, "file": "src/lib/tarot/summary.ts",       "line": 29,  "provider": "grok",      "model": "grok-2-1212",   "function": "chat.completions.create"},
        # 2 anthropic calls
        {"id": 5, "file": "src/lib/ai/judge.py",            "line": 55,  "provider": "anthropic", "model": "claude-haiku-4-5", "function": "messages.create"},
        {"id": 6, "file": "src/lib/ai/rerank.py",           "line": 112, "provider": "anthropic", "model": "claude-haiku-4-5", "function": "messages.create"},
        # 2 raw-fetch calls
        {"id": 7, "file": "src/lib/harvest/wiki.ts",        "line": 34,  "provider": "raw-fetch",  "model": None,            "function": "fetch"},
        {"id": 8, "file": "src/lib/harvest/biddy.ts",       "line": 21,  "provider": "raw-fetch",  "model": None,            "function": "fetch"},
    ]

    prompt_templates = [
        {"id": 1, "source_file": "src/lib/tarot/reading.ts",        "template": "당신은 신비로운 타로 마스터입니다. 다음 카드 조합을 해석해 주세요: {cards}. 질문: {question}"},
        {"id": 2, "source_file": "src/lib/tarot/interpretation.ts", "template": "타로 카드 {card_name}의 {position} 위치에서의 의미를 {context}에 맞게 설명해 주세요."},
        {"id": 3, "source_file": "src/lib/tarot/spread.ts",         "template": "켈틱 크로스 배열에서 {position}번 위치의 {card}는 {user_situation}을 나타냅니다."},
        {"id": 4, "source_file": "src/lib/tarot/summary.ts",        "template": "이번 타로 리딩을 요약해 주세요. 전체 흐름: {reading_flow}. 핵심 메시지: {core_message}"},
        {"id": 5, "source_file": "src/lib/ai/judge.py",             "template": "Evaluate the quality of this tarot reading response. Score from 0 to 1. Response: {response}"},
    ]

    model_configs = [
        {"provider": "grok",      "model": "grok-2-1212",    "temperature": 0.9,  "max_tokens": 1024, "stream": True},
        {"provider": "grok",      "model": "grok-2-mini",    "temperature": 0.7,  "max_tokens": 512,  "stream": False},
        {"provider": "anthropic", "model": "claude-haiku-4-5","temperature": 0.1,  "max_tokens": 256,  "stream": False},
    ]

    language_breakdown = {"TypeScript": 0.72, "Python": 0.28}

    await session.execute(text("""
        INSERT INTO analyses (id, repo_id, status, call_sites, prompt_templates, model_configs, language_breakdown, analyzed_at, started_at)
        VALUES (:id, :repo_id, :status, :call_sites, :prompt_templates, :model_configs, :lang_breakdown, :analyzed_at, :started_at)
        ON CONFLICT (id) DO NOTHING
    """), {
        "id": analysis_id,
        "repo_id": repo_id,
        "status": "done",
        "call_sites": json.dumps(call_sites),
        "prompt_templates": json.dumps(prompt_templates),
        "model_configs": json.dumps(model_configs),
        "lang_breakdown": json.dumps(language_breakdown),
        "analyzed_at": days_ago(14),
        "started_at": days_ago(14) - timedelta(minutes=3),
    })
    return analysis_id


async def seed_inference(session, repo_id: str, analysis_id: str) -> str:
    """Insert INFER stage result. Returns inference_id."""
    print("  → inferences")
    inference_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "arcanainsight-inference-verum"))

    raw_response = {
        "model": "claude-sonnet-4-6",
        "usage": {"input_tokens": 3847, "output_tokens": 412},
        "output": {
            "domain": "tarot_divination",
            "subdomain": "divination/tarot",
            "tone": "mystical",
            "language": "ko",
            "user_type": "consumer",
            "confidence": 0.94,
            "reasoning": (
                "The repository contains multiple TypeScript files under src/lib/tarot/ "
                "with Korean-language prompt templates referencing 타로 (tarot) cards, spreads, "
                "and readings. The service is clearly a consumer-facing tarot divination application. "
                "Tone is mystical and personal, language is Korean, audience is B2C."
            ),
        },
    }

    await session.execute(text("""
        INSERT INTO inferences (id, repo_id, analysis_id, status, domain, tone, language, user_type, confidence, summary, raw_response, created_at)
        VALUES (:id, :repo_id, :analysis_id, :status, :domain, :tone, :language, :user_type, :confidence, :summary, :raw_response, :created_at)
        ON CONFLICT (id) DO NOTHING
    """), {
        "id": inference_id,
        "repo_id": repo_id,
        "analysis_id": analysis_id,
        "status": "done",
        "domain": "tarot_divination",
        "tone": "mystical",
        "language": "ko",
        "user_type": "consumer",
        "confidence": 0.94,
        "summary": (
            "ArcanaInsight is a Korean-language consumer tarot reading service. "
            "It uses Grok-2 to generate mystical, personalized interpretations of tarot card spreads. "
            "The service targets individual consumers seeking spiritual guidance and self-reflection "
            "through traditional tarot symbolism."
        ),
        "raw_response": json.dumps(raw_response),
        "created_at": days_ago(13),
    })
    return inference_id


async def seed_harvest(session, inference_id: str) -> None:
    """Insert HARVEST sources and chunks."""
    print("  → harvest_sources + chunks")

    sources = [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "harvest-src-wiki-tarot")),
            "url": "https://en.wikipedia.org/wiki/Tarot",
            "title": "Tarot — Wikipedia",
            "description": "Comprehensive overview of tarot history, card meanings, and divination practices.",
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "harvest-src-tarot-hermit")),
            "url": "https://tarot-hermit.com/card-meanings/",
            "title": "Tarot Hermit — Card Meanings",
            "description": "In-depth card-by-card meanings for all 78 tarot cards, major and minor arcana.",
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "harvest-src-biddy-tarot")),
            "url": "https://www.biddytarot.com/tarot-card-meanings/",
            "title": "Biddy Tarot — Learn Tarot Card Meanings",
            "description": "Intuitive tarot learning resource with upright and reversed card meanings.",
        },
    ]

    # Plausible tarot knowledge snippets (10 per source)
    wiki_chunks = [
        "The tarot is a pack of playing cards, used from at least the mid-15th century in various parts of Europe to play card games. In the late 18th century, some tarot decks began to be used for divination.",
        "The standard modern tarot deck is based on the Venetian or Piedmontese tarot. It consists of 78 cards divided into two groups: the major arcana, which has 22 cards, and the minor arcana, which has 56 cards.",
        "The major arcana consists of 22 cards, each depicting a different archetype: The Fool, The Magician, The High Priestess, The Empress, The Emperor, The Hierophant, The Lovers, The Chariot, Strength, The Hermit, Wheel of Fortune, Justice, The Hanged Man, Death, Temperance, The Devil, The Tower, The Star, The Moon, The Sun, Judgement, and The World.",
        "The minor arcana consists of four suits: Wands (also called Batons, Clubs, or Staves), Cups (also called Chalices or Goblets), Swords (also called Blades), and Pentacles (also called Coins or Discs). Each suit has 14 cards: Ace through 10, and four court cards (Page, Knight, Queen, King).",
        "The Celtic Cross is one of the most popular tarot spreads. It consists of 10 cards laid out in a specific pattern, each position representing a different aspect of the querent's situation.",
        "Reversed tarot cards (also called inverted or ill-dignified) are read upside down. Some readers interpret reversed cards as blockages, delays, or the shadow aspects of the card's upright meaning.",
        "The Rider-Waite tarot deck, created in 1909, is the most popular and widely used tarot deck today. It was the first deck to fully illustrate all 78 cards, including the minor arcana.",
        "Tarot reading involves the reader shuffling the deck while the querent focuses on a question or situation. Cards are then drawn and placed in specific positions (a spread) that relate to different aspects of the question.",
        "The Fool (card 0 or XXII) represents new beginnings, innocence, and spontaneity. It depicts a young man about to step off a cliff, symbolizing the leap of faith required to begin a new journey.",
        "The Death card (XIII) rarely signifies literal death. Instead, it represents transformation, endings leading to new beginnings, and the natural cycle of change. It is one of the most misunderstood cards in the tarot.",
    ]

    hermit_chunks = [
        "The High Priestess (II) sits between two pillars, one black and one white, representing duality and the boundary between the conscious and unconscious mind. She holds a scroll of knowledge in her lap.",
        "The Empress (III) is the embodiment of femininity, fertility, and nature. She sits on a throne surrounded by lush vegetation, symbolizing abundance, nurturing, and creative expression.",
        "The Emperor (IV) represents authority, structure, and masculine power. He sits on a stone throne adorned with ram heads, symbolizing determination and the application of will to achieve goals.",
        "The Tower (XVI) depicts a tall tower being struck by lightning, with figures falling from its windows. This dramatic imagery represents sudden upheaval, revelation of truth, and the collapse of false structures.",
        "The Star (XVII) shows a naked woman kneeling beside water, pouring two jugs simultaneously. She represents hope, renewal, and spiritual connection following the chaos represented by The Tower.",
        "The Moon (XVIII) depicts two dogs howling at a crescent moon, with a crayfish emerging from water. It represents illusion, the subconscious, and the fear of the unknown that lurks in the dark.",
        "The Sun (XIX) is one of the most positive cards in the deck, depicting a radiant sun with a young child riding a white horse. It represents success, vitality, joy, and the triumph of consciousness.",
        "The Ace of Cups represents the beginning of emotional experiences, intuition, and spiritual receptivity. As the root of the element Water, it signifies the purest form of emotional potential.",
        "The King of Swords represents intellectual authority, truth, and clear thinking. He holds his sword upright, ready to cut through confusion with sharp logic and decisive judgment.",
        "The Ten of Pentacles shows a multi-generational family scene, symbolizing long-term success, legacy, and the fulfillment of material and familial goals passed down through generations.",
    ]

    biddy_chunks = [
        "타로 카드를 읽을 때, 카드의 위치와 주변 카드와의 관계를 고려하는 것이 중요합니다. 단일 카드는 강력한 메시지를 전달할 수 있지만, 전체 스프레드에서의 맥락이 더 풍부한 해석을 제공합니다.",
        "The Three-Card Spread is the most versatile and beginner-friendly tarot spread. The three positions typically represent Past, Present, and Future, or Situation, Action, and Outcome.",
        "연인 (The Lovers, VI) 카드는 단순히 로맨틱한 사랑만을 의미하지 않습니다. 이 카드는 중요한 선택의 기로에 서 있음을 나타내며, 자신의 가치와 신념에 충실한 결정을 내려야 할 때를 상징합니다.",
        "The Chariot (VII) represents willpower, determination, and the ability to overcome obstacles through focused effort. The two sphinxes pulling in opposite directions symbolize opposing forces that must be controlled.",
        "Strength (VIII) depicts a woman gently opening the jaws of a lion, symbolizing courage that comes from inner strength and compassion rather than brute force. It represents patience and self-discipline.",
        "The Hermit (IX) shows an elderly figure standing alone on a mountain peak, holding a lantern. This card represents soul-searching, inner guidance, and the wisdom gained through solitude and reflection.",
        "The Wheel of Fortune (X) is a card of cycles, destiny, and turning points. As the wheel turns, what was once at the bottom rises to the top, and what was high must eventually come down.",
        "Justice (XI) holds scales and a sword, representing cause and effect, fairness, and truth. It reminds us that every action has consequences and calls for honest self-reflection.",
        "The World (XXI) is the final card of the major arcana, depicting a dancing figure surrounded by a laurel wreath. It represents completion, integration, and the successful end of a major life cycle.",
        "연금술사 (Temperance, XIV) 카드는 중용과 균형을 나타냅니다. 물을 두 컵 사이에서 붓는 천사의 이미지는 인내와 조화, 그리고 서로 다른 요소들을 통합하는 능력을 상징합니다.",
    ]

    all_chunk_contents = [wiki_chunks, hermit_chunks, biddy_chunks]

    for src, chunks_content in zip(sources, all_chunk_contents):
        await session.execute(text("""
            INSERT INTO harvest_sources (id, inference_id, url, title, description, status, chunks_count, created_at)
            VALUES (:id, :inference_id, :url, :title, :desc, :status, :chunks_count, :created_at)
            ON CONFLICT (id) DO NOTHING
        """), {
            "id": src["id"],
            "inference_id": inference_id,
            "url": src["url"],
            "title": src["title"],
            "desc": src["description"],
            "status": "done",
            "chunks_count": len(chunks_content),
            "created_at": days_ago(12),
        })

        for idx, content in enumerate(chunks_content):
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"chunk-{src['id']}-{idx}"))
            embedding = rand_embedding(1024)
            metadata = {
                "source_title": src["title"],
                "chunk_index": idx,
                "language": "ko" if any(ord(c) > 0x1100 for c in content) else "en",
                "char_count": len(content),
            }
            await session.execute(text("""
                INSERT INTO chunks (id, source_id, inference_id, content, chunk_index, embedding, metadata_, created_at)
                VALUES (:id, :source_id, :inference_id, :content, :chunk_index, :embedding::jsonb, :metadata, :created_at)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": chunk_id,
                "source_id": src["id"],
                "inference_id": inference_id,
                "content": content,
                "chunk_index": idx,
                "embedding": json.dumps(embedding),
                "metadata": json.dumps(metadata),
                "created_at": days_ago(12),
            })

    print(f"     inserted {len(sources)} sources × 10 chunks = 30 chunks")


async def seed_generation(session, inference_id: str) -> str:
    """Insert GENERATE stage result. Returns generation_id."""
    print("  → generations")
    generation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "arcanainsight-generation-verum"))

    metric_profile = {
        "prompt_count": 5,
        "prompt_variants": ["original", "cot", "few_shot", "role_play", "concise"],
        "rag_config": {
            "chunk_size": 512,
            "top_k": 5,
            "embedding_model": "text-embedding-3-small",
            "reranker": "bge-reranker-v2-m3",
            "retrieval_strategy": "hybrid",  # semantic + full-text
        },
        "eval_pairs": 20,
        "dashboard_metrics": ["latency_p95", "judge_score", "user_satisfaction", "cost_per_call"],
        "service_type": "consumer_b2c",
    }

    await session.execute(text("""
        INSERT INTO generations (id, inference_id, status, metric_profile, generated_at, created_at)
        VALUES (:id, :inference_id, :status, :metric_profile, :generated_at, :created_at)
        ON CONFLICT (id) DO NOTHING
    """), {
        "id": generation_id,
        "inference_id": inference_id,
        "status": "done",
        "metric_profile": json.dumps(metric_profile),
        "generated_at": days_ago(10),
        "created_at": days_ago(10),
    })
    return generation_id


DEMO_API_KEY = "demo-api-key-for-testing-only"
DEMO_API_KEY_HASH = hashlib.sha256(DEMO_API_KEY.encode()).hexdigest()


async def seed_deployment(session, generation_id: str) -> str:
    """Insert DEPLOY stage result. Returns deployment_id."""
    print("  → deployments")
    deployment_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "arcanainsight-deployment-verum"))

    traffic_split = {
        "original":  0.0,
        "cot":       1.0,
        "few_shot":  0.0,
        "role_play": 0.0,
        "concise":   0.0,
    }

    await session.execute(text("""
        INSERT INTO deployments (
            id, generation_id, status, traffic_split, error_count, total_calls,
            experiment_status, current_baseline_variant, api_key_hash, created_at, updated_at
        )
        VALUES (
            :id, :generation_id, :status, :traffic_split::jsonb, :error_count, :total_calls,
            :exp_status, :baseline_variant, :api_key_hash, :created_at, :updated_at
        )
        ON CONFLICT (id) DO NOTHING
    """), {
        "id": deployment_id,
        "generation_id": generation_id,
        "status": "canary",
        "traffic_split": json.dumps(traffic_split),
        "error_count": 0,
        "total_calls": 820,
        "exp_status": "converged",
        "baseline_variant": "cot",
        "api_key_hash": DEMO_API_KEY_HASH,
        "created_at": days_ago(10),
        "updated_at": hours_ago(1),
    })
    return deployment_id


async def seed_experiments(session, deployment_id: str) -> None:
    """Insert two converged experiment records showing cot winning both rounds."""
    print("  → experiments (2 rounds)")

    # Round 1: cot beats original
    exp1_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "experiment-r1-cot-vs-original"))
    await session.execute(text("""
        INSERT INTO experiments (
            id, deployment_id, baseline_variant, challenger_variant, status,
            winner_variant, confidence, baseline_wins, baseline_n,
            challenger_wins, challenger_n, win_threshold, cost_weight,
            started_at, converged_at
        )
        VALUES (
            :id, :dep_id, :baseline, :challenger, :status,
            :winner, :confidence, :bw, :bn, :cw, :cn,
            :win_threshold, :cost_weight, :started_at, :converged_at
        )
        ON CONFLICT (id) DO NOTHING
    """), {
        "id": exp1_id,
        "dep_id": deployment_id,
        "baseline": "original",
        "challenger": "cot",
        "status": "converged",
        "winner": "cot",
        "confidence": 0.97,
        "bw": 82,
        "bn": 210,
        "cw": 128,
        "cn": 210,
        "win_threshold": 0.6,
        "cost_weight": 0.1,
        "started_at": days_ago(5),
        "converged_at": days_ago(2),
    })

    # Round 2: cot beats few_shot (cot remains champion)
    exp2_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "experiment-r2-cot-vs-few-shot"))
    await session.execute(text("""
        INSERT INTO experiments (
            id, deployment_id, baseline_variant, challenger_variant, status,
            winner_variant, confidence, baseline_wins, baseline_n,
            challenger_wins, challenger_n, win_threshold, cost_weight,
            started_at, converged_at
        )
        VALUES (
            :id, :dep_id, :baseline, :challenger, :status,
            :winner, :confidence, :bw, :bn, :cw, :cn,
            :win_threshold, :cost_weight, :started_at, :converged_at
        )
        ON CONFLICT (id) DO NOTHING
    """), {
        "id": exp2_id,
        "dep_id": deployment_id,
        "baseline": "cot",
        "challenger": "few_shot",
        "status": "converged",
        "winner": "cot",
        "confidence": 0.96,
        "bw": 131,
        "bn": 200,
        "cw": 69,
        "cn": 200,
        "win_threshold": 0.6,
        "cost_weight": 0.1,
        "started_at": days_ago(2),
        "converged_at": hours_ago(1),
    })


async def seed_traces(session, deployment_id: str) -> None:
    """Insert 420 traces (210 original + 210 cot) with spans and judge_prompts for 20 samples."""
    print("  → traces + spans (420 total)")

    random.seed(42)  # Reproducible output

    # Pre-build deterministic trace IDs so judge_prompts can reference them
    variants = [
        ("original", 210, 0.71, 0.08, 0.0012),
        ("cot",      210, 0.81, 0.07, 0.0018),
    ]

    judge_prompt_target_count = 20
    judge_prompt_count = 0

    sample_tarot_prompts = [
        "타로 카드로 제 사랑 운세를 봐주세요. 최근 새로운 사람을 만났는데 잘 될까요?",
        "직장에서 중요한 결정을 내려야 하는데, 타로 카드가 어떤 방향을 가리키나요?",
        "올해 제 재정 상황이 나아질까요? 타로로 알아보고 싶어요.",
        "가족 관계에서 갈등이 있어요. 타로 카드로 조언을 구하고 싶습니다.",
        "새로운 사업을 시작하려고 합니다. 타로가 성공 가능성을 알려줄 수 있을까요?",
    ]

    for variant, count, score_mean, score_std, cost_base in variants:
        for i in range(count):
            trace_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"trace-{variant}-{i}"))

            # Spread traces over the last 5 days
            offset_seconds = random.uniform(0, 5 * 24 * 3600)
            trace_created = days_ago(5) + timedelta(seconds=offset_seconds)

            judge_score = clip(random.gauss(score_mean, score_std), 0.5, 1.0)
            # 70% of traces have user feedback; bias positive for cot
            user_feedback: int | None = None
            if random.random() < 0.7:
                pos_prob = 0.62 if variant == "original" else 0.78
                user_feedback = 1 if random.random() < pos_prob else -1

            await session.execute(text("""
                INSERT INTO traces (id, deployment_id, variant, user_feedback, judge_score, created_at)
                VALUES (:id, :dep_id, :variant, :feedback, :judge_score, :created_at)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": trace_id,
                "dep_id": deployment_id,
                "variant": variant,
                "feedback": user_feedback,
                "judge_score": round(judge_score, 4),
                "created_at": trace_created,
            })

            # Span
            span_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"span-{trace_id}"))
            input_tokens = random.randint(150, 300)
            output_tokens = random.randint(200, 500)
            latency_ms = random.randint(800, 3200)
            cost_usd = round(cost_base * random.uniform(0.85, 1.15), 6)

            await session.execute(text("""
                INSERT INTO spans (id, trace_id, model, input_tokens, output_tokens, latency_ms, cost_usd, error, started_at)
                VALUES (:id, :trace_id, :model, :input_tokens, :output_tokens, :latency_ms, :cost_usd, :error, :started_at)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": span_id,
                "trace_id": trace_id,
                "model": "grok-2-1212",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "cost_usd": str(cost_usd),
                "error": None,
                "started_at": trace_created,
            })

            # Judge prompts: sample 10 per variant (20 total)
            if judge_prompt_count < judge_prompt_target_count and i < 10:
                q = sample_tarot_prompts[i % len(sample_tarot_prompts)]
                prompt_sent = json.dumps({
                    "model": "claude-haiku-4-5",
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                f"Evaluate the quality of this tarot reading response on a scale from 0 to 1.\n\n"
                                f"User question: {q}\n\n"
                                f"Variant: {variant}\n\n"
                                f"Score based on: accuracy (0.4), mystical tone (0.3), actionability (0.3).\n"
                                f"Return JSON: {{\"score\": <float>, \"reasoning\": \"<string>\"}}"
                            ),
                        }
                    ],
                })
                raw_response = json.dumps({
                    "score": round(judge_score, 4),
                    "reasoning": (
                        f"The {variant} variant response demonstrates "
                        + ("strong chain-of-thought reasoning that guides the reader through each card's symbolism sequentially, improving coherence." if variant == "cot" else "a direct but somewhat surface-level interpretation that lacks depth.")
                        + f" Mystical tone is {'well-maintained' if variant == 'cot' else 'adequate'}. "
                        f"Overall quality: {round(judge_score, 4)}."
                    ),
                })
                await session.execute(text("""
                    INSERT INTO judge_prompts (trace_id, prompt_sent, raw_response, judged_at)
                    VALUES (:trace_id, :prompt_sent, :raw_response, :judged_at)
                    ON CONFLICT (trace_id) DO NOTHING
                """), {
                    "trace_id": trace_id,
                    "prompt_sent": prompt_sent,
                    "raw_response": raw_response,
                    "judged_at": trace_created + timedelta(seconds=2),
                })
                judge_prompt_count += 1

    print(f"     {judge_prompt_count} judge_prompts inserted (sampled from traces)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    print("Seeding Verum demo data (ArcanaInsight scenario)...")
    print("=" * 60)

    async with SessionLocal() as session:
        await seed_model_pricing(session)
        user_id = await seed_user(session)
        repo_id = await seed_repo(session, user_id)
        analysis_id = await seed_analysis(session, repo_id)
        inference_id = await seed_inference(session, repo_id, analysis_id)
        await seed_harvest(session, inference_id)
        generation_id = await seed_generation(session, inference_id)
        deployment_id = await seed_deployment(session, generation_id)
        await seed_experiments(session, deployment_id)
        await seed_traces(session, deployment_id)
        await session.commit()

    print("=" * 60)
    print("Done! Demo data seeded successfully.")
    print()
    print("Summary:")
    print("  User:        demo (github_id=99999999)")
    print("  Repo:        github.com/xzawed/ArcanaInsight")
    print("  Domain:      tarot_divination (confidence=0.94)")
    print("  Sources:     3 (Wikipedia, tarot-hermit.com, biddytarot.com)")
    print("  Chunks:      30 (1024-dim embeddings)")
    print("  Variants:    original | cot | few_shot | role_play | concise")
    print("  Experiments: 2 converged (cot beat original @ 0.97, beat few_shot @ 0.96)")
    print("  Traces:      420 (210 original, 210 cot)")
    print("  Winner:      cot (judge_score ~0.81 vs original ~0.71)")
    print()
    print(f"Demo API key: {DEMO_API_KEY}")


if __name__ == "__main__":
    asyncio.run(main())
