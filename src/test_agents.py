from __future__ import annotations

from pathlib import Path

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config
from memory_store import UserProfileStore


def make_config(tmp_path: Path):
    """Student TODO: build an isolated config for tests."""

    # Hint:
    # - point `state_dir` into tmp_path
    # - reduce compact threshold so compaction happens quickly in tests
    config = load_config(tmp_path)
    config.state_dir = tmp_path / "state"
    config.state_dir.mkdir(parents=True, exist_ok=True)
    config.data_dir = Path(__file__).resolve().parent.parent / "data"
    config.compact_threshold_tokens = 80
    config.compact_keep_messages = 4
    return config


def test_user_markdown_read_write_edit(tmp_path: Path) -> None:
    """Student TODO: verify `User.md` can be created, updated, and edited."""

    store = UserProfileStore(tmp_path / "profiles")
    path = store.write_text("user/unsafe", "# User\n- Tên: An\n")
    assert path.parent == tmp_path / "profiles"
    assert store.read_text("user/unsafe").endswith("An\n")
    assert store.edit_text("user/unsafe", "An", "Bình")
    assert "Bình" in store.read_text("user/unsafe")
    assert store.file_size("user/unsafe") > 0


def test_compact_trigger(tmp_path: Path) -> None:
    """Student TODO: verify long threads trigger compaction."""

    agent = AdvancedAgent(make_config(tmp_path), force_offline=True)
    for index in range(12):
        agent.reply("u", "long", f"Lượt {index}: " + "ngữ cảnh dài " * 20)
    assert agent.compaction_count("long") > 0
    assert len(agent.compact_memory.context("long")["messages"]) <= 4


def test_cross_session_recall(tmp_path: Path) -> None:
    """Student TODO: verify advanced remembers across sessions and baseline does not."""

    config = make_config(tmp_path)
    advanced = AdvancedAgent(config, force_offline=True)
    baseline = BaselineAgent(config, force_offline=True)
    fact = "Chào bạn, mình tên là Lan và đang ở Huế."
    advanced.reply("lan", "learn", fact)
    baseline.reply("lan", "learn", fact)
    advanced_answer = advanced.reply("lan", "new", "Mình tên gì và đang ở đâu?")["content"]
    baseline_answer = baseline.reply("lan", "new", "Mình tên gì và đang ở đâu?")["content"]
    assert "Lan" in advanced_answer and "Huế" in advanced_answer
    assert "Lan" not in baseline_answer and "Huế" not in baseline_answer


def test_compact_reduces_prompt_load_on_long_thread(tmp_path: Path) -> None:
    """Student TODO: compare prompt load of baseline vs advanced on a long thread."""

    config = make_config(tmp_path)
    baseline = BaselineAgent(config, force_offline=True)
    advanced = AdvancedAgent(config, force_offline=True)
    for index in range(30):
        text = f"Lượt {index}: " + "đây là nội dung dài để đo chi phí prompt " * 16
        baseline.reply("u", "thread", text)
        advanced.reply("u", "thread", text)
    assert advanced.compaction_count("thread") > 0
    assert advanced.prompt_token_usage("thread") < baseline.prompt_token_usage("thread")
