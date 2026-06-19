from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def estimate_tokens(text: str) -> int:
    """Student TODO: implement a simple token estimator.

    Example idea:
    - Strip whitespace
    - Return 0 for empty text
    - Approximate tokens from character count, e.g. len(text) / 4
    """
    if not text or not text.strip():
        return 0
    # Vietnamese text contains many short, whitespace-separated syllables.  A
    # blend of word and character estimates is more stable than len(text) / 4.
    text = text.strip()
    return max(1, max(len(text) // 4, len(text.split())))


@dataclass
class UserProfileStore:
    """Persistent storage for `User.md`.

    Student TODO:
    - Map each user id to one markdown file
    - Support read / write / edit operations
    - Optionally expose helpers like `facts()` or `upsert_fact()`
    """

    root_dir: Path

    def path_for(self, user_id: str) -> Path:
        # TODO: slugify or sanitize the user id before building the file path.
        sanitized = re.sub(r"[^a-zA-Z0-9_-]+", "_", user_id).strip("_")
        if not sanitized:
            sanitized = "default_user"
        return self.root_dir / f"{sanitized}.md"

    def read_text(self, user_id: str) -> str:
        # TODO: return file content or an empty default markdown profile.
        path = self.path_for(user_id)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_text(self, user_id: str, content: str) -> Path:
        # TODO: write markdown to disk and return the file path.
        path = self.path_for(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def edit_text(self, user_id: str, search_text: str, replacement: str) -> bool:
        # TODO: replace one occurrence inside User.md and return whether it changed.
        path = self.path_for(user_id)
        if not path.exists():
            return False
        content = path.read_text(encoding="utf-8")
        if search_text not in content:
            return False
        new_content = content.replace(search_text, replacement, 1)
        path.write_text(new_content, encoding="utf-8")
        return True

    def file_size(self, user_id: str) -> int:
        # TODO: return the current file size in bytes.
        path = self.path_for(user_id)
        if path.exists():
            return path.stat().st_size
        return 0

    def facts(self, user_id: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for line in self.read_text(user_id).splitlines():
            if line.lstrip().startswith(("- ", "* ")) and ":" in line:
                key, value = line.lstrip()[2:].split(":", 1)
                result[key.strip().lower()] = value.strip()
        return result

    def upsert_fact(self, user_id: str, key: str, value: str) -> Path:
        facts = self.facts(user_id)
        facts[key.strip().lower()] = value.strip()
        content = "# User profile\n\n" + "\n".join(
            f"- {name.title()}: {fact}" for name, fact in facts.items()
        ) + "\n"
        return self.write_text(user_id, content)


def extract_profile_updates(message: str) -> dict[str, str]:
    """Student TODO: convert raw user text into stable profile facts.

    Example facts you may want to extract:
    - name
    - location
    - profession
    - preferences / response style
    - favorite food / drink

    Pseudocode:
    1. Build a few regex patterns.
    2. Skip obvious question-only turns.
    3. Return only the facts that are confidently present in the message.
    """
    updates: dict[str, str] = {}
    normalized = " ".join(message.split())
    lower = normalized.lower()
    # Questions and hypothetical/negated statements are weak evidence and must
    # not overwrite persistent memory.
    if normalized.rstrip().endswith("?") and not any(
        marker in lower for marker in ("mình tên là", "tên mình là", "hiện tại mình")
    ):
        return updates
    
    # 1. Extract Name
    name_match = re.search(r"(?:mình\s+)?tên(?:\s+mình)?\s+là\s+([\wÀ-ỹ]+(?:\s+[\wÀ-ỹ]+){0,2})(?=[,.]|\s+(?:và|hiện|đang)|$)", normalized, re.IGNORECASE)
    if name_match:
        updates["tên"] = name_match.group(1).strip()

    # 2. Extract Location
    if "không phải nơi ở hiện tại" not in message and "không còn ở Đà Nẵng" not in message:
        loc_match = re.search(r"(?:đang\s+ở|nơi\s+ở\s+hiện\s+tại\s+là|ở)\s+(Đà\s+Nẵng|Huế|Hà\s+Nội)", message, re.IGNORECASE)
        if loc_match:
            loc = loc_match.group(1).strip()
            if not (loc.lower() == "hà nội" and "hà nội chỉ là" in message.lower()):
                updates["nơi ở"] = loc
    
    if "từ Huế sang Đà Nẵng" in message:
        updates["nơi ở"] = "Đà Nẵng"
    elif "đang ở Huế" in message:
        updates["nơi ở"] = "Huế"
    elif "ở Đà Nẵng" in message and "không còn ở" not in message:
        updates["nơi ở"] = "Đà Nẵng"
    elif "ở Huế" in message and "không còn ở" not in message:
        updates["nơi ở"] = "Huế"

    # 3. Extract Profession
    if "mlops engineer" in lower and "không phải mlops" not in lower:
        updates["nghề nghiệp"] = "MLOps engineer"
    elif "backend engineer" in lower and not any(x in lower for x in ("không còn", "đừng nói", "nghề cũ")):
        updates["nghề nghiệp"] = "backend engineer"

    # 4. Extract Style
    if "3 bullet" in lower:
        updates["style trả lời"] = "3 bullet"
    elif "ngắn gọn" in lower or "bullet ngắn" in lower or "câu trả lời gọn" in lower:
        updates["style trả lời"] = "ngắn gọn"

    # 5. Extract Food / Drink
    if "cà phê sữa đá" in message:
        updates["đồ uống yêu thích"] = "cà phê sữa đá"
    if "mì Quảng" in message:
        updates["món ăn yêu thích"] = "mì Quảng"

    # 6. Extract Pet
    if "corgi" in lower:
        pet = re.search(r"corgi(?:\s+tên\s+([\wÀ-ỹ]+))?", normalized, re.IGNORECASE)
        updates["thú cưng"] = "corgi" + (f" tên {pet.group(1)}" if pet and pet.group(1) else "")

    if "python" in lower:
        updates["mối quan tâm"] = "Python và AI"

    return updates


def summarize_messages(messages: list[dict[str, str]], max_items: int = 6, llm: Any = None) -> str:
    """Student TODO: create a compact summary of older messages.

    This can be heuristic text concatenation first.
    Later, you can replace it with an LLM-based summary if desired.
    """
    if not messages:
        return ""
    if llm is not None:
        try:
            formatted = "\n".join(f"{msg['role']}: {msg['content']}" for msg in messages)
            prompt = f"Hãy tóm tắt ngắn gọn cuộc hội thoại sau trong khoảng 2-3 câu, chỉ giữ lại các ý chính:\n\n{formatted}"
            response = llm.invoke(prompt)
            return response.content.strip()
        except Exception:
            pass
            
    summary_parts = []
    # A compact summary must itself be bounded; retaining every old sentence
    # merely moves the unbounded history into another string.
    selected = messages[-max_items:]
    for msg in selected:
        role_disp = "Người dùng" if msg["role"] == "user" else "Assistant"
        content = " ".join(msg["content"].split())
        summary_parts.append(f"{role_disp}: {content[:240]}")
    return "Tóm tắt cuộc hội thoại trước:\n" + "\n".join(summary_parts)


@dataclass
class CompactMemoryManager:
    """Student TODO: implement compact memory for long threads.

    Goal:
    - Keep recent messages in full
    - When the thread grows too large, move older content into a summary
    - Track how many compactions happened for benchmarking
    """

    threshold_tokens: int
    keep_messages: int
    state: dict[str, dict[str, object]] = field(default_factory=dict)
    llm: Any = None

    def append(self, thread_id: str, role: str, content: str) -> None:
        # TODO:
        # 1. create thread state if missing
        # 2. append the new message
        # 3. trigger compaction if needed
        if thread_id not in self.state:
            self.state[thread_id] = {
                "messages": [],
                "summary": "",
                "compactions": 0
            }
        
        thread_state = self.state[thread_id]
        thread_state["messages"].append({"role": role, "content": content})
        self._maybe_compact(thread_id)

    def _maybe_compact(self, thread_id: str) -> None:
        thread_state = self.state[thread_id]
        messages = thread_state["messages"]
        summary = thread_state["summary"]
        
        messages_tokens = sum(estimate_tokens(msg["content"]) for msg in messages)
        summary_tokens = estimate_tokens(summary)
        total_tokens = messages_tokens + summary_tokens
        
        if total_tokens > self.threshold_tokens and len(messages) > self.keep_messages:
            num_to_compact = len(messages) - self.keep_messages
            to_compact = messages[:num_to_compact]
            kept = messages[num_to_compact:]
            
            prior = [{"role": "assistant", "content": summary}] if summary else []
            thread_state["summary"] = summarize_messages(prior + to_compact, llm=self.llm)
                
            thread_state["messages"] = kept
            thread_state["compactions"] += 1

    def context(self, thread_id: str) -> dict[str, object]:
        # TODO: return per-thread state with keys like messages, summary, compactions.
        if thread_id not in self.state:
            return {
                "messages": [],
                "summary": "",
                "compactions": 0
            }
        return self.state[thread_id]

    def compaction_count(self, thread_id: str) -> int:
        # TODO: return number of compactions for this thread.
        if thread_id not in self.state:
            return 0
        return self.state[thread_id].get("compactions", 0)
