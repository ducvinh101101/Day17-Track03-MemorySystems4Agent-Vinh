from __future__ import annotations

from dataclasses import dataclass
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


@dataclass
class BenchmarkRow:
    agent_name: str
    agent_tokens_only: int
    prompt_tokens_processed: int
    recall_score: float
    response_quality: float
    memory_growth_bytes: int
    compactions: int


def load_conversations(path: Path) -> list[dict[str, Any]]:
    """Student TODO: read JSON conversations from disk."""

    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, list):
        raise ValueError(f"Benchmark dataset must be a JSON list: {path}")
    return value


def recall_points(answer: str, expected: list[str]) -> float:
    """Student TODO: return 0 / 0.5 / 1 depending on how many expected facts appear."""

    if not expected:
        return 1.0
    folded = answer.casefold()
    hits = sum(item.casefold() in folded for item in expected)
    ratio = hits / len(expected)
    return 1.0 if ratio == 1 else 0.5 if ratio > 0 else 0.0


def heuristic_quality(answer: str, expected: list[str]) -> float:
    """Student TODO: add a lightweight quality score for offline mode."""

    recall = recall_points(answer, expected)
    if not answer.strip():
        return 0.0
    # Reward correct content and a readable, reasonably concise answer.
    readability = 1.0 if 5 <= len(answer.split()) <= 160 else 0.5
    return round(0.8 * recall + 0.2 * readability, 3)


def run_agent_benchmark(agent_name: str, agent, conversations: list[dict[str, Any]], config) -> BenchmarkRow:
    """Student TODO: evaluate one agent over many conversations.

    Pseudocode:
    1. Feed all turns to the agent.
    2. Track `agent tokens only`.
    3. Track `prompt tokens processed`.
    4. Ask recall questions in a fresh thread.
    5. Compute average recall and quality.
    6. Record memory file growth and compaction count.
    """

    recalls: list[float] = []
    qualities: list[float] = []
    users: set[str] = set()
    thread_ids: list[str] = []
    benchmark_users = {item["user_id"] for item in conversations}
    initial_memory = sum(agent.memory_file_size(u) for u in benchmark_users) if hasattr(agent, "memory_file_size") else 0

    for conversation in conversations:
        user_id = conversation["user_id"]
        users.add(user_id)
        thread_id = f"{agent_name}-{conversation['id']}-learn"
        thread_ids.append(thread_id)
        for turn in conversation.get("turns", []):
            agent.reply(user_id, thread_id, turn)

        # A fresh thread is deliberate: this measures cross-session memory.
        for index, check in enumerate(conversation.get("recall_questions", [])):
            recall_thread = f"{agent_name}-{conversation['id']}-recall-{index}"
            thread_ids.append(recall_thread)
            answer = agent.reply(user_id, recall_thread, check["question"])["content"]
            expected = check.get("expected_contains", [])
            recalls.append(recall_points(answer, expected))
            qualities.append(heuristic_quality(answer, expected))

    agent_tokens = sum(agent.token_usage(t) for t in thread_ids)
    prompt_tokens = sum(agent.prompt_token_usage(t) for t in thread_ids)
    final_memory = sum(agent.memory_file_size(u) for u in users) if hasattr(agent, "memory_file_size") else 0
    return BenchmarkRow(
        agent_name=agent_name,
        agent_tokens_only=agent_tokens,
        prompt_tokens_processed=prompt_tokens,
        recall_score=round(sum(recalls) / len(recalls), 3) if recalls else 0.0,
        response_quality=round(sum(qualities) / len(qualities), 3) if qualities else 0.0,
        memory_growth_bytes=max(0, final_memory - initial_memory),
        compactions=sum(agent.compaction_count(t) for t in thread_ids),
    )


def format_rows(rows: list[BenchmarkRow]) -> str:
    """Student TODO: print a markdown table or tabulated output."""

    headers = ["Agent", "Agent tokens only", "Prompt tokens processed", "Cross-session recall", "Response quality", "Memory growth (bytes)", "Compactions"]
    values = [[r.agent_name, r.agent_tokens_only, r.prompt_tokens_processed, f"{r.recall_score:.2f}", f"{r.response_quality:.2f}", r.memory_growth_bytes, r.compactions] for r in rows]
    try:
        from tabulate import tabulate
        return tabulate(values, headers=headers, tablefmt="github")
    except ImportError:
        all_rows = [headers, *[[str(v) for v in row] for row in values]]
        widths = [max(len(str(row[i])) for row in all_rows) for i in range(len(headers))]
        render = lambda row: "| " + " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(row)) + " |"
        return "\n".join([render(headers), "| " + " | ".join("-" * w for w in widths) + " |", *map(render, values)])


def main() -> None:
    """Student TODO: run both benchmark suites.

    Required benchmark sections:
    - Standard benchmark from `data/conversations.json`
    - Long-context stress benchmark from `data/advanced_long_context.json`

    Compare:
    - Baseline
    - Advanced

    Keep the same output columns as the solved lab:
    - Agent tokens only
    - Prompt tokens processed
    - Cross-session recall
    - Response quality
    - Memory growth (bytes)
    - Compactions
    """

    config = load_config(Path(__file__).resolve().parent.parent)
    live = os.getenv("BENCHMARK_LIVE", "0").strip().lower() in {"1", "true", "yes", "on"}

    suites = [
        ("Standard Benchmark", config.data_dir / "conversations.json"),
        ("Long-Context Stress Benchmark", config.data_dir / "advanced_long_context.json"),
    ]
    for title, path in suites:
        conversations = load_conversations(path)
        # Each suite gets fresh persistent storage so repeated benchmark runs
        # are deterministic and never mutate the user's normal state directory.
        with tempfile.TemporaryDirectory(prefix="memory-lab-") as state:
            suite_config = load_config(config.base_dir)
            suite_config.state_dir = Path(state)
            baseline = BaselineAgent(suite_config, force_offline=not live)
            advanced = AdvancedAgent(suite_config, force_offline=not live)
            rows = [
                run_agent_benchmark("Baseline", baseline, conversations, suite_config),
                run_agent_benchmark("Advanced", advanced, conversations, suite_config),
            ]
        mode = "LIVE LLM" if live else "OFFLINE"
        print(f"\n## {title} ({mode})\n")
        print(format_rows(rows))


if __name__ == "__main__":
    main()
