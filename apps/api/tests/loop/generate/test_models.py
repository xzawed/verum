"""Tests for GENERATE stage models."""
import uuid

import pytest

from src.loop.generate.models import (
    EvalPair,
    GenerateResult,
    PromptVariant,
    RagConfig,
    VARIANT_TYPES,
)


class TestPromptVariant:
    """Test PromptVariant model."""

    def test_minimal_variant(self):
        """Test PromptVariant with minimal fields."""
        variant = PromptVariant(
            variant_type="original",
            content="You are a helpful assistant.",
        )
        assert variant.variant_type == "original"
        assert variant.content == "You are a helpful assistant."
        assert variant.variables == []

    def test_variant_with_variables(self):
        """Test PromptVariant with extracted variables."""
        variant = PromptVariant(
            variant_type="cot",
            content="Question: {query}\nContext: {context}",
            variables=["query", "context"],
        )
        assert len(variant.variables) == 2
        assert "query" in variant.variables

    def test_variant_all_types(self):
        """Test that all variant types are valid."""
        for vtype in VARIANT_TYPES:
            variant = PromptVariant(
                variant_type=vtype,
                content="Test prompt",
            )
            assert variant.variant_type == vtype

    def test_invalid_variant_type(self):
        """Test that invalid variant type is accepted (not validated in model)."""
        # Note: variant_type is string without enum validation
        variant = PromptVariant(
            variant_type="invalid_type",
            content="Test",
        )
        assert variant.variant_type == "invalid_type"


class TestRagConfig:
    """Test RagConfig model."""

    def test_default_rag_config(self):
        """Test RagConfig with defaults."""
        config = RagConfig()
        assert config.chunking_strategy == "recursive"
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        assert config.top_k == 5
        assert config.hybrid_alpha == pytest.approx(0.7)

    def test_semantic_chunking(self):
        """Test semantic chunking configuration."""
        config = RagConfig(
            chunking_strategy="semantic",
            chunk_size=768,
            top_k=10,
        )
        assert config.chunking_strategy == "semantic"
        assert config.chunk_size == 768
        assert config.top_k == 10

    def test_vector_only_search(self):
        """Test vector-only search (hybrid_alpha=1.0)."""
        config = RagConfig(hybrid_alpha=1.0)
        assert config.hybrid_alpha == pytest.approx(1.0)

    def test_text_only_search(self):
        """Test text-only search (hybrid_alpha=0.0)."""
        config = RagConfig(hybrid_alpha=0.0)
        assert config.hybrid_alpha == pytest.approx(0.0)

    def test_chunk_size_bounds(self):
        """Test chunk size validation."""
        # Minimum
        config = RagConfig(chunk_size=128)
        assert config.chunk_size == 128

        # Maximum
        config = RagConfig(chunk_size=2048)
        assert config.chunk_size == 2048

        # Too small should raise
        with pytest.raises(ValueError):
            RagConfig(chunk_size=127)

        # Too large should raise
        with pytest.raises(ValueError):
            RagConfig(chunk_size=2049)

    def test_top_k_bounds(self):
        """Test top_k validation."""
        # Minimum
        config = RagConfig(top_k=1)
        assert config.top_k == 1

        # Maximum
        config = RagConfig(top_k=20)
        assert config.top_k == 20

        # Invalid bounds
        with pytest.raises(ValueError):
            RagConfig(top_k=0)

        with pytest.raises(ValueError):
            RagConfig(top_k=21)

    def test_hybrid_alpha_bounds(self):
        """Test hybrid_alpha validation."""
        with pytest.raises(ValueError):
            RagConfig(hybrid_alpha=-0.1)

        with pytest.raises(ValueError):
            RagConfig(hybrid_alpha=1.1)


class TestEvalPair:
    """Test EvalPair model."""

    def test_eval_pair_with_context(self):
        """Test EvalPair requiring RAG context."""
        pair = EvalPair(
            query="What does the Tower card mean?",
            expected_answer="Sudden change, upheaval, revelation",
            context_needed=True,
        )
        assert pair.context_needed is True

    def test_eval_pair_without_context(self):
        """Test EvalPair not requiring RAG context."""
        pair = EvalPair(
            query="What is 2+2?",
            expected_answer="4",
            context_needed=False,
        )
        assert pair.context_needed is False

    def test_eval_pair_defaults(self):
        """Test EvalPair defaults."""
        pair = EvalPair(
            query="Test query",
            expected_answer="Test answer",
        )
        assert pair.context_needed is True


class TestGenerateResult:
    """Test GenerateResult model."""

    def test_generate_result_minimal(self):
        """Test GenerateResult with minimal valid data."""
        inference_id = uuid.uuid4()
        result = GenerateResult(
            inference_id=inference_id,
            prompt_variants=[
                PromptVariant(variant_type="original", content="Base prompt"),
            ],
            rag_config=RagConfig(),
            eval_pairs=[
                EvalPair(
                    query="Test query",
                    expected_answer="Test answer",
                ),
            ],
        )
        assert result.inference_id == inference_id
        assert len(result.prompt_variants) == 1
        assert len(result.eval_pairs) == 1

    def test_generate_result_full(self):
        """Test GenerateResult with multiple variants and eval pairs."""
        inference_id = uuid.uuid4()
        result = GenerateResult(
            inference_id=inference_id,
            prompt_variants=[
                PromptVariant(variant_type="original", content="Original"),
                PromptVariant(variant_type="cot", content="Think step by step"),
                PromptVariant(
                    variant_type="few_shot",
                    content="Example: {input}",
                    variables=["input"],
                ),
            ],
            rag_config=RagConfig(
                chunking_strategy="semantic",
                chunk_size=1024,
                top_k=10,
            ),
            eval_pairs=[
                EvalPair(query="Q1", expected_answer="A1", context_needed=True),
                EvalPair(query="Q2", expected_answer="A2", context_needed=False),
                EvalPair(query="Q3", expected_answer="A3"),
            ],
        )
        assert len(result.prompt_variants) == 3
        assert len(result.eval_pairs) == 3
        assert result.rag_config.chunking_strategy == "semantic"

    def test_generate_result_round_trip(self):
        """Test serialization and deserialization."""
        inference_id = uuid.uuid4()
        original = GenerateResult(
            inference_id=inference_id,
            prompt_variants=[
                PromptVariant(variant_type="original", content="You are a tarot reader."),
                PromptVariant(variant_type="cot", content="Let's think step by step."),
            ],
            rag_config=RagConfig(
                chunking_strategy="semantic",
                chunk_size=512,
                top_k=5,
                hybrid_alpha=0.7,
            ),
            eval_pairs=[
                EvalPair(
                    query="What does the Tower card mean?",
                    expected_answer="Sudden change.",
                    context_needed=True,
                ),
            ],
        )

        # Serialize to dict
        dumped = original.model_dump()

        # Deserialize from dict
        loaded = GenerateResult(**dumped)

        # Verify
        assert loaded.inference_id == inference_id
        assert loaded.rag_config.chunking_strategy == "semantic"
        assert len(loaded.prompt_variants) == 2
        assert loaded.prompt_variants[0].variant_type == "original"
        assert loaded.eval_pairs[0].query == "What does the Tower card mean?"

    def test_generate_result_json_schema(self):
        """Test that GenerateResult can generate JSON schema."""
        schema = GenerateResult.model_json_schema()
        assert "properties" in schema
        assert "inference_id" in schema["properties"]
        assert "prompt_variants" in schema["properties"]
        assert "rag_config" in schema["properties"]
        assert "eval_pairs" in schema["properties"]


# ---------------------------------------------------------------------------
# Additional edge-case tests (appended)
# ---------------------------------------------------------------------------


class TestRagConfigChunkOverlapBoundaries:
    """Explicit boundary tests for chunk_overlap — not covered by existing suite."""

    def test_chunk_overlap_min_boundary(self):
        """chunk_overlap=0 (exact minimum) must be accepted."""
        config = RagConfig(chunk_overlap=0)
        assert config.chunk_overlap == 0

    def test_chunk_overlap_max_boundary(self):
        """chunk_overlap=256 (exact maximum) must be accepted."""
        config = RagConfig(chunk_overlap=256)
        assert config.chunk_overlap == 256

    def test_chunk_overlap_below_min_rejected(self):
        """chunk_overlap=-1 (below minimum) must be rejected."""
        with pytest.raises(ValueError):
            RagConfig(chunk_overlap=-1)

    def test_chunk_overlap_above_max_rejected(self):
        """chunk_overlap=257 (above maximum) must be rejected."""
        with pytest.raises(ValueError):
            RagConfig(chunk_overlap=257)


class TestRagConfigChunkOverlapExceedsChunkSize:
    """Document the current model behaviour when chunk_overlap >= chunk_size.

    The Pydantic model has no cross-field validator enforcing
    chunk_overlap < chunk_size.  This test pins the *current* behaviour so
    that any future validator addition produces an explicit, intentional
    test failure rather than a silent regression.
    """

    def test_chunk_overlap_greater_than_chunk_size_is_currently_accepted(self):
        """chunk_overlap > chunk_size is NOT validated — this is a known gap.

        If a cross-field validator is ever added (recommended), flip the
        assertion to expect ValueError and remove this comment.
        """
        # chunk_size=128 is the minimum; overlap=200 exceeds it — still accepted
        config = RagConfig(chunk_size=128, chunk_overlap=200)
        # Document current (permissive) behaviour explicitly
        assert config.chunk_overlap > config.chunk_size


class TestGenerateResultEmptyVariants:
    """GenerateResult with an empty prompt_variants list is currently accepted.

    The model has no min-length constraint on the list.  This test pins the
    behaviour so that any future min_length=1 annotation is an intentional,
    visible change.
    """

    def test_empty_prompt_variants_currently_accepted(self):
        """GenerateResult accepts prompt_variants=[] — known permissive behaviour."""
        result = GenerateResult(
            inference_id=uuid.uuid4(),
            prompt_variants=[],
            rag_config=RagConfig(),
            eval_pairs=[EvalPair(query="q", expected_answer="a")],
        )
        assert result.prompt_variants == []
