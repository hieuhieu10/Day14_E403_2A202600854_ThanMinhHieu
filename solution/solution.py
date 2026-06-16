"""
Day 14 — AI Evaluation & Benchmarking Pipeline
AICB-P1: AI Practical Competency Program, Phase 1

Implemented Solution File.
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Task 1 — Data Models (Golden Dataset + Evaluation Results)
# ---------------------------------------------------------------------------

@dataclass
class QAPair:
    """
    A question-answer pair for evaluation (part of the Golden Dataset).

    Fields:
        question:        The question to answer.
        expected_answer: The reference/ground-truth answer (expert-written).
        context:            Source context (may be empty string if not applicable).
        metadata:           Optional metadata dict (difficulty, category, etc.).
        retrieved_contexts: List of retrieved chunks (ORDER = retriever rank).
                            Used by the retrieval-side metrics (Task 2b).
    """
    question: str
    expected_answer: str
    context: str | None = ""
    metadata: dict = field(default_factory=dict)
    retrieved_contexts: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """
    Evaluation result for a single Q&A pair.

    Fields:
        qa_pair:        The original QAPair.
        actual_answer:  What the agent actually returned.
        faithfulness:   Float 0-1, how grounded the answer is in context.
        relevance:      Float 0-1, how relevant the answer is to the question.
        completeness:   Float 0-1, how complete the answer is vs expected.
        passed:         True if all three scores >= 0.5.
        failure_type:   None if passed, otherwise one of:
                        "hallucination", "irrelevant", "incomplete", "off_topic".
        context_precision: Float 0-1 or None — quality of retrieval ranking.
        context_recall:    Float 0-1 or None — coverage of expected by context.
    """
    qa_pair: QAPair
    actual_answer: str
    faithfulness: float
    relevance: float
    completeness: float
    passed: bool
    failure_type: str | None = None
    context_precision: float | None = None
    context_recall: float | None = None

    def overall_score(self) -> float:
        """Compute the average of faithfulness, relevance, and completeness."""
        return (self.faithfulness + self.relevance + self.completeness) / 3.0


# ---------------------------------------------------------------------------
# Task 2 — RAGAS Evaluator (Simplified word-overlap heuristic)
# ---------------------------------------------------------------------------

COMMON_STOPWORDS: set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "with", "as", "by", "and", "or",
    "it", "its", "this", "that", "these", "those", "from", "into", "than",
}


def _tokenize(text: str) -> set[str]:
    """Lowercase word tokenization, ignoring punctuation and stopwords."""
    if not text:
        return set()
    tokens = re.findall(r"\b\w+\b", text.lower())
    return {t for t in tokens if t not in COMMON_STOPWORDS}


class RAGASEvaluator:
    """
    Evaluates RAG pipeline outputs using RAGAS-inspired heuristics.
    """

    def evaluate_faithfulness(self, answer: str, context: str) -> float:
        """
        Measure how grounded the answer is in the context.
        """
        answer_tokens = _tokenize(answer)
        if not answer_tokens:
            return 1.0
        context_tokens = _tokenize(context)
        overlap = answer_tokens & context_tokens
        score = len(overlap) / len(answer_tokens)
        return min(max(score, 0.0), 1.0)

    def evaluate_relevance(self, answer: str, question: str) -> float:
        """
        Measure how relevant the answer is to the question.
        """
        question_tokens = _tokenize(question)
        if not question_tokens:
            return 1.0
        answer_tokens = _tokenize(answer)
        overlap = answer_tokens & question_tokens
        score = len(overlap) / len(question_tokens)
        return min(max(score, 0.0), 1.0)

    def evaluate_completeness(self, answer: str, expected: str) -> float:
        """
        Measure how well the answer covers the expected answer.
        """
        expected_tokens = _tokenize(expected)
        if not expected_tokens:
            return 1.0
        answer_tokens = _tokenize(answer)
        overlap = answer_tokens & expected_tokens
        score = len(overlap) / len(expected_tokens)
        return min(max(score, 0.0), 1.0)

    # -----------------------------------------------------------------------
    # Task 2b — Retrieval-side metrics (evaluate the GET-CONTEXT step)
    # -----------------------------------------------------------------------

    def evaluate_context_recall(self, contexts: list[str], expected: str) -> float:
        """Context Recall — how much of the expected answer is covered by the
        UNION of retrieved chunks.
        """
        expected_tokens = _tokenize(expected)
        if not expected_tokens:
            return 1.0
        union_tokens = set()
        for chunk in contexts:
            union_tokens.update(_tokenize(chunk))
        overlap = expected_tokens & union_tokens
        score = len(overlap) / len(expected_tokens)
        return min(max(score, 0.0), 1.0)

    def evaluate_context_precision(
        self,
        contexts: list[str],
        expected: str,
        relevance_threshold: float = 0.1,
    ) -> float:
        """Context Precision — RANK-AWARE Average Precision (AP@K), like RAGAS.
        Rewards retrievers that place RELEVANT chunks BEFORE noise.
        """
        expected_tokens = _tokenize(expected)
        if not expected_tokens:
            return 1.0
        if not contexts:
            return 0.0

        relevances = []
        for chunk in contexts:
            chunk_tokens = _tokenize(chunk)
            overlap = chunk_tokens & expected_tokens
            rel = (len(overlap) / len(expected_tokens)) >= relevance_threshold if expected_tokens else False
            relevances.append(rel)

        num_relevant = sum(1 for r in relevances if r)
        if num_relevant == 0:
            return 0.0

        ap_sum = 0.0
        relevant_so_far = 0
        for k, rel in enumerate(relevances, 1):
            if rel:
                relevant_so_far += 1
                precision_k = relevant_so_far / k
                ap_sum += precision_k

        return ap_sum / num_relevant

    def run_full_eval(
        self,
        answer: str,
        question: str,
        context: str,
        expected: str,
        qa_pair: QAPair | None = None,
    ) -> EvalResult:
        """
        Run all three evaluations and combine into an EvalResult.
        """
        faithfulness = self.evaluate_faithfulness(answer, context)
        relevance = self.evaluate_relevance(answer, question)
        completeness = self.evaluate_completeness(answer, expected)

        passed = faithfulness >= 0.5 and relevance >= 0.5 and completeness >= 0.5

        if passed:
            failure_type = None
        elif faithfulness < 0.3:
            failure_type = "hallucination"
        elif relevance < 0.3:
            failure_type = "irrelevant"
        elif completeness < 0.3:
            failure_type = "incomplete"
        else:
            failure_type = "off_topic"

        if qa_pair is None:
            qa_pair = QAPair(
                question=question,
                expected_answer=expected,
                context=context
            )

        context_precision = None
        context_recall = None
        if qa_pair.retrieved_contexts:
            context_precision = self.evaluate_context_precision(qa_pair.retrieved_contexts, expected)
            context_recall = self.evaluate_context_recall(qa_pair.retrieved_contexts, expected)

        return EvalResult(
            qa_pair=qa_pair,
            actual_answer=answer,
            faithfulness=faithfulness,
            relevance=relevance,
            completeness=completeness,
            passed=passed,
            failure_type=failure_type,
            context_precision=context_precision,
            context_recall=context_recall
        )


# ---------------------------------------------------------------------------
# Reranking helper
# ---------------------------------------------------------------------------

def rerank_by_overlap(contexts: list[str], query: str) -> list[str]:
    """A minimal lexical reranker: sort chunks by word overlap with the query,
    most-overlapping first.
    """
    return sorted(contexts, key=lambda c: len(_tokenize(c) & _tokenize(query)), reverse=True)


# ---------------------------------------------------------------------------
# Task 3 — LLM Judge
# ---------------------------------------------------------------------------

class LLMJudge:
    """
    Uses an LLM to score AI responses according to a rubric.
    """

    def __init__(self, judge_llm_fn: Callable[[str], str]) -> None:
        self.judge_llm_fn = judge_llm_fn

    def score_response(
        self,
        question: str,
        answer: str,
        rubric: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Score an AI response using the judge LLM.
        """
        prompt = (
            f"Question: {question}\n"
            f"Answer: {answer}\n"
            f"Rubric: {json.dumps(rubric)}\n"
            "Please score the answer based on the rubric. Return a JSON object containing the scores for each criterion."
        )

        raw_response = ""
        try:
            raw_response = self.judge_llm_fn(prompt)
        except Exception as e:
            raw_response = f"Error calling judge LLM: {str(e)}"

        scores = {}
        reasoning = raw_response

        try:
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                if "scores" in parsed and isinstance(parsed["scores"], dict):
                    scores = parsed["scores"]
                    if "reasoning" in parsed:
                        reasoning = str(parsed["reasoning"])
                else:
                    for key in rubric.keys():
                        if key in parsed:
                            scores[key] = float(parsed[key])
                        elif "scores" in parsed and key in parsed["scores"]:
                            scores[key] = float(parsed["scores"][key])
        except Exception:
            pass

        for key in rubric.keys():
            if key not in scores:
                scores[key] = 0.5

        return {
            "scores": scores,
            "reasoning": reasoning
        }

    def detect_bias(self, scores_batch: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Detect potential bias patterns in a batch of judge scores.
        """
        if not scores_batch:
            return {
                "positional_bias": False,
                "leniency_bias": False,
                "severity_bias": False,
            }

        all_scores = []
        for item in scores_batch:
            scores_dict = item.get("scores", {})
            for score in scores_dict.values():
                if isinstance(score, (int, float)):
                    all_scores.append(score)

        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.5
        leniency_bias = avg_score > 0.8
        severity_bias = avg_score < 0.3

        positional_bias = False
        first_pos_scores = []
        second_pos_scores = []
        for item in scores_batch:
            pos = item.get("position") or item.get("metadata", {}).get("position")
            scores_dict = item.get("scores", {})
            val = list(scores_dict.values())[0] if scores_dict else None
            if val is not None and isinstance(val, (int, float)):
                if pos in (1, "1", "first", "A"):
                    first_pos_scores.append(val)
                elif pos in (2, "2", "second", "B"):
                    second_pos_scores.append(val)

        if first_pos_scores and second_pos_scores:
            avg_first = sum(first_pos_scores) / len(first_pos_scores)
            avg_second = sum(second_pos_scores) / len(second_pos_scores)
            positional_bias = (avg_first - avg_second) > 0.15
        else:
            half = len(scores_batch) // 2
            if half > 0:
                first_half_scores = []
                second_half_scores = []
                for item in scores_batch[:half]:
                    first_half_scores.extend([v for v in item.get("scores", {}).values() if isinstance(v, (int, float))])
                for item in scores_batch[half:]:
                    second_half_scores.extend([v for v in item.get("scores", {}).values() if isinstance(v, (int, float))])
                if first_half_scores and second_half_scores:
                    avg_first = sum(first_half_scores) / len(first_half_scores)
                    avg_second = sum(second_half_scores) / len(second_half_scores)
                    positional_bias = (avg_first - avg_second) > 0.15

        return {
            "positional_bias": positional_bias,
            "leniency_bias": leniency_bias,
            "severity_bias": severity_bias,
        }


# ---------------------------------------------------------------------------
# Task 4 — Benchmark Runner
# ---------------------------------------------------------------------------

class BenchmarkRunner:
    """
    Runs a full evaluation benchmark.
    """

    def run(
        self,
        qa_pairs: list[QAPair],
        agent_fn: Callable[[str], str],
        evaluator: RAGASEvaluator,
    ) -> list[EvalResult]:
        """
        Run all QA pairs through the agent and evaluate each result.
        """
        results = []
        for qa in qa_pairs:
            actual_answer = agent_fn(qa.question)
            eval_result = evaluator.run_full_eval(
                answer=actual_answer,
                question=qa.question,
                context=qa.context or "",
                expected=qa.expected_answer,
                qa_pair=qa,
            )
            results.append(eval_result)
        return results

    def generate_report(self, results: list[EvalResult]) -> dict[str, Any]:
        """
        Generate an aggregate report from evaluation results.
        """
        total = len(results)
        if total == 0:
            return {
                "total": 0,
                "passed": 0,
                "pass_rate": 0.0,
                "avg_faithfulness": 0.0,
                "avg_relevance": 0.0,
                "avg_completeness": 0.0,
                "failure_types": {},
            }

        passed_count = sum(1 for r in results if r.passed)
        sum_faithfulness = sum(r.faithfulness for r in results)
        sum_relevance = sum(r.relevance for r in results)
        sum_completeness = sum(r.completeness for r in results)

        failure_types = {}
        for r in results:
            if not r.passed and r.failure_type:
                failure_types[r.failure_type] = failure_types.get(r.failure_type, 0) + 1

        return {
            "total": total,
            "passed": passed_count,
            "pass_rate": passed_count / total,
            "avg_faithfulness": sum_faithfulness / total,
            "avg_relevance": sum_relevance / total,
            "avg_completeness": sum_completeness / total,
            "failure_types": failure_types,
        }

    def run_regression(self, new_results: list[EvalResult], baseline_results: list[EvalResult]) -> dict:
        """Compare new evaluation results against a baseline."""
        new_report = self.generate_report(new_results)
        baseline_report = self.generate_report(baseline_results)

        new_avg_f = new_report["avg_faithfulness"]
        new_avg_r = new_report["avg_relevance"]
        new_avg_c = new_report["avg_completeness"]

        base_avg_f = baseline_report["avg_faithfulness"]
        base_avg_r = baseline_report["avg_relevance"]
        base_avg_c = baseline_report["avg_completeness"]

        regressions = []
        if base_avg_f - new_avg_f > 0.05:
            regressions.append("faithfulness")
        if base_avg_r - new_avg_r > 0.05:
            regressions.append("relevance")
        if base_avg_c - new_avg_c > 0.05:
            regressions.append("completeness")

        passed = len(regressions) == 0

        return {
            'new_avg_faithfulness': new_avg_f,
            'new_avg_relevance': new_avg_r,
            'new_avg_completeness': new_avg_c,
            'baseline_avg_faithfulness': base_avg_f,
            'baseline_avg_relevance': base_avg_r,
            'baseline_avg_completeness': base_avg_c,
            'regressions': regressions,
            'passed': passed
        }

    def identify_failures(
        self,
        results: list[EvalResult],
        threshold: float = 0.5,
    ) -> list[EvalResult]:
        """
        Return EvalResults where any score is below threshold.
        """
        failures = []
        for r in results:
            if (r.faithfulness < threshold or
                r.relevance < threshold or
                r.completeness < threshold):
                failures.append(r)
        return failures


# ---------------------------------------------------------------------------
# Task 5 — Failure Analyzer
# ---------------------------------------------------------------------------

class FailureAnalyzer:
    """
    Analyzes failed evaluation results to identify patterns and suggest fixes.
    """

    def categorize_failures(
        self, failures: list[EvalResult]
    ) -> dict[str, int]:
        """
        Count failures by failure_type.
        """
        categories = {}
        for f in failures:
            ft = f.failure_type or "unknown"
            categories[ft] = categories.get(ft, 0) + 1
        return categories

    def find_root_cause(self, failure: EvalResult) -> str:
        """
        Suggest a root cause for a single failure based on its scores.
        """
        f = failure.faithfulness
        r = failure.relevance
        c = failure.completeness

        scores = [("faithfulness", f), ("relevance", r), ("completeness", c)]
        min_score = min(f, r, c)

        min_metrics = [name for name, val in scores if val == min_score]

        if len(min_metrics) > 1:
            return "Multiple issues detected — review full pipeline"

        lowest_metric = min_metrics[0]
        if lowest_metric == "faithfulness":
            return "Context is missing or irrelevant — improve retrieval"
        elif lowest_metric == "relevance":
            return "Answer does not address the question — improve prompt clarity"
        else:
            return "Answer is missing key information — increase context window or improve generation"

    def generate_improvement_log(self, failures: list, suggestions: list[str]) -> str:
        """Generate a Markdown table logging failures and improvement actions."""
        table = [
            "| Failure ID | Type | Root Cause | Suggested Fix | Status |",
            "|------------|------|------------|---------------|--------|",
        ]
        for i, f in enumerate(failures):
            f_id = f"F{i+1:03d}"
            f_type = f.failure_type or "Unknown"
            root_cause = self.find_root_cause(f)

            if suggestions:
                suggested_fix = suggestions[i % len(suggestions)]
            else:
                suggested_fix = "Review pipeline configuration"

            table.append(f"| {f_id} | {f_type} | {root_cause} | {suggested_fix} | Open |")

        return "\n".join(table)

    def generate_improvement_suggestions(
        self, failures: list[EvalResult]
    ) -> list[str]:
        """
        Generate a prioritized list of improvement suggestions based on failure patterns.
        """
        if not failures:
            return []

        categories = self.categorize_failures(failures)
        suggestions = []

        if categories.get("hallucination", 0) > 0 or any(f.failure_type == "hallucination" for f in failures):
            suggestions.append("Implement hallucination checker to filter unsupported claims")
            suggestions.append("Verify retriever content alignment to ensure relevant background contexts are loaded")

        if categories.get("irrelevant", 0) > 0 or any(f.failure_type == "irrelevant" for f in failures):
            suggestions.append("Refine prompt clarity and add explicit negative constraints (e.g. do not guess if context is missing)")
            suggestions.append("Add few-shot examples showing how to address the user question precisely")

        if categories.get("incomplete", 0) > 0 or any(f.failure_type == "incomplete" for f in failures):
            suggestions.append("Increase chunk size or retrieve more chunks (higher top-k) in RAG pipeline to reduce context fragmentation")
            suggestions.append("Add structured formatting instructions to prompt (e.g. bullet points) to ensure all facets are answered")

        general_suggestions = [
            "Tune prompt temperature and system instructions to align generation behavior",
            "Clean up noisy background contexts using a reranking step (e.g., cross-encoders)",
            "Implement validation gates in the chatbot backend to verify output structures before responding"
        ]

        for gs in general_suggestions:
            if len(suggestions) < 3:
                suggestions.append(gs)

        return suggestions


if __name__ == "__main__":
    qa_pairs = [
        QAPair(
            question="What is RAG?",
            expected_answer="RAG stands for Retrieval-Augmented Generation, which combines retrieval with text generation.",
            context="RAG is a technique that retrieves relevant documents and uses them to ground LLM generation.",
            metadata={"difficulty": "easy", "category": "definition"},
        ),
        QAPair(
            question="What is the capital of France?",
            expected_answer="Paris is the capital of France.",
            context="France is a country in Western Europe. Its capital city is Paris.",
            metadata={"difficulty": "easy", "category": "factual"},
        ),
        QAPair(
            question="Explain backpropagation and why it matters for training",
            expected_answer="Backpropagation is an algorithm for training neural networks by computing gradients efficiently, enabling deep learning models to learn from errors.",
            context="Neural networks learn through gradient descent. Backpropagation efficiently computes these gradients layer by layer.",
            metadata={"difficulty": "medium", "category": "explanation"},
        ),
        QAPair(
            question="Should I use RAG or fine-tuning for my chatbot?",
            expected_answer="It depends on the use case: RAG is better for frequently updated knowledge, fine-tuning for consistent style/behavior. Consider cost, latency, and data freshness.",
            context="RAG retrieves external documents at inference time. Fine-tuning modifies model weights during training.",
            metadata={"difficulty": "hard", "category": "comparison"},
        ),
        QAPair(
            question="What is the meaning of life?",
            expected_answer="This question is outside the scope of this system. I can help with AI and technology questions.",
            context="This is an AI assistant specialized in technology topics.",
            metadata={"difficulty": "adversarial", "category": "out_of_scope"},
        ),
    ]

    evaluator = RAGASEvaluator()
    runner = BenchmarkRunner()

    def mock_agent(question: str) -> str:
        return f"Based on my knowledge: {question[:30]}... The answer involves key concepts."

    results = runner.run(qa_pairs, mock_agent, evaluator)
    report = runner.generate_report(results)
    print("=== Benchmark Report ===")
    for k, v in report.items():
        print(f"  {k}: {v}")

    failures = runner.identify_failures(results, threshold=0.5)
    print(f"\n=== Failures ({len(failures)}) ===")
    analyzer = FailureAnalyzer()

    categories = analyzer.categorize_failures(failures)
    print("Failure Categories:", categories)

    for f in failures:
        cause = analyzer.find_root_cause(f)
        print(f"  Root cause: {cause}")

    suggestions = analyzer.generate_improvement_suggestions(failures)
    print("\nImprovement Suggestions:")
    for s in suggestions:
        print(f"  - {s}")

    log = analyzer.generate_improvement_log(failures, suggestions)
    print("\n=== Improvement Log ===")
    print(log)
