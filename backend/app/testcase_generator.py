"""
RAG-driven test case generation.

Token-optimization strategy (this is the part that matters for cost):
1. Never send the whole document to the LLM. Group chunks by their source
   section/sheet (a cheap, free, local operation) to get a list of
   "modules" to generate test cases for.
2. For each module, retrieve only the top-K most relevant chunks via
   embedding similarity — including chunks from *other* sections that are
   semantically related (e.g. a shared validation rule) — rather than
   dumping every chunk from every section into every prompt.
3. Ask for compact JSON only (no prose, no markdown) and cap
   max_output_tokens, so output tokens are the other side of the cost
   equation kept in check.
4. One generation call per module instead of one call per individual test
   case — fewer round trips, better use of context than many tiny calls.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from app.gemini_client import GeminiError, embed_query, generate_json
from app.models import DocumentChunk, TestCase, TestCasePriority, TestCaseType
from app.vector_store import InMemoryVectorStore

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """You are a senior QA engineer generating software test cases from \
requirement text. Given requirement/context text for one module, produce test cases covering \
positive, negative, boundary, and edge scenarios for every rule, field, and flow branch \
mentioned. Be specific and concrete — reference actual field names, limits, and values from \
the given text rather than generic placeholders. Output ONLY valid JSON matching this schema, \
no prose, no markdown fences:

{
  "test_cases": [
    {
      "scenario": "string - short test scenario name",
      "preconditions": "string",
      "steps": ["string", "..."],
      "test_data": "string",
      "expected_result": "string",
      "priority": "P1" | "P2" | "P3",
      "case_type": "positive" | "negative" | "boundary" | "edge"
    }
  ]
}

If the given text does not contain enough information for a good test case, skip it rather \
than inventing unrelated content."""


def _group_chunks_by_section(chunks: list[DocumentChunk]) -> dict[str, list[DocumentChunk]]:
    groups: dict[str, list[DocumentChunk]] = defaultdict(list)
    for chunk in chunks:
        key = f"{chunk.document_name} — {chunk.section_title}"
        groups[key].append(chunk)
    return groups


def _build_user_prompt(module_name: str, chunks: list[DocumentChunk]) -> str:
    context = "\n\n---\n\n".join(c.text for c in chunks)
    return f"Module: {module_name}\n\nContext:\n{context}"


async def generate_test_cases_for_document(
    all_chunks: list[DocumentChunk],
    store: InMemoryVectorStore,
    top_k: int,
) -> list[TestCase]:
    """Generates test cases module-by-module using retrieval-augmented
    context. `store` must already contain embeddings for all_chunks."""
    sections = _group_chunks_by_section(all_chunks)
    test_cases: list[TestCase] = []
    tc_counter = 1

    for module_name, primary_chunks in sections.items():
        # Retrieve related context beyond just this section's own chunks —
        # this is the "RAG" part: a validation rule stated once elsewhere
        # in the doc but relevant to this module still gets pulled in.
        query_text = primary_chunks[0].text[:500]
        try:
            query_embedding = await embed_query(query_text)
            retrieved = store.search(query_embedding, top_k=top_k)
        except GeminiError as exc:
            logger.warning("retrieval_failed_falling_back_to_section_only", extra={"module": module_name, "error": str(exc)})
            retrieved = []

        # Merge: this section's own chunks always included, plus any extra
        # retrieved chunks not already covered, capped to keep the prompt small.
        seen_ids = {c.chunk_id for c in primary_chunks}
        merged = list(primary_chunks)
        for chunk in retrieved:
            if chunk.chunk_id not in seen_ids and len(merged) < top_k + len(primary_chunks):
                merged.append(chunk)
                seen_ids.add(chunk.chunk_id)

        prompt = _build_user_prompt(module_name, merged)

        try:
            result = await generate_json(SYSTEM_INSTRUCTION, prompt)
        except GeminiError as exc:
            logger.error("generation_failed_for_module", extra={"module_name": module_name, "error": str(exc)})
            continue

        for raw_tc in result.get("test_cases", []):
            try:
                test_cases.append(
                    TestCase(
                        tc_id=f"TC-{tc_counter:04d}",
                        module=module_name,
                        scenario=raw_tc["scenario"],
                        preconditions=raw_tc.get("preconditions", ""),
                        steps=raw_tc.get("steps", []),
                        test_data=raw_tc.get("test_data", ""),
                        expected_result=raw_tc["expected_result"],
                        priority=TestCasePriority(raw_tc.get("priority", "P2")),
                        case_type=TestCaseType(raw_tc.get("case_type", "positive")),
                        source_section=module_name,
                    )
                )
                tc_counter += 1
            except (KeyError, ValueError) as exc:
                logger.warning("skipping_malformed_test_case", extra={"module": module_name, "error": str(exc)})
                continue

    return test_cases
