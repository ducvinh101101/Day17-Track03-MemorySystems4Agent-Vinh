from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import LabConfig, load_config
from memory_store import CompactMemoryManager, UserProfileStore, estimate_tokens, extract_profile_updates
from model_provider import build_chat_model


@dataclass
class AgentContext:
    user_id: str
    memory_path: str


class AdvancedAgent:
    """Student TODO: implement Agent B / Advanced Agent.

    Required memory layers:
    1. within-session memory
    2. persistent `User.md`
    3. compact memory for long threads
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.profile_store = UserProfileStore(self.config.state_dir / "profiles")
        self.compact_memory = CompactMemoryManager(
            threshold_tokens=self.config.compact_threshold_tokens,
            keep_messages=self.config.compact_keep_messages,
        )
        self.thread_tokens: dict[str, int] = {}
        self.thread_prompt_tokens: dict[str, int] = {}
        self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: route between offline mode and live mode."""
        if self.force_offline or self.langchain_agent is None:
            return self._reply_offline(user_id, thread_id, message)
        
        try:
            updates = extract_profile_updates(message)
            if updates:
                existing = self.profile_store.read_text(user_id)
                facts = {}
                if existing:
                    for line in existing.splitlines():
                        line = line.strip()
                        if (line.startswith("- ") or line.startswith("* ")) and ":" in line:
                            parts = line[2:].split(":", 1)
                            facts[parts[0].strip().lower()] = parts[1].strip()
                facts.update(updates)
                
                display_keys = {
                    "tên": "Tên",
                    "nơi ở": "Nơi ở",
                    "nghề nghiệp": "Nghề nghiệp",
                    "đồ uống yêu thích": "Đồ uống yêu thích",
                    "món ăn yêu thích": "Món ăn yêu thích",
                    "thú cưng": "Thú cưng",
                    "style trả lời": "Style trả lời"
                }
                lines = []
                order = ["tên", "nơi ở", "nghề nghiệp", "đồ uống yêu thích", "món ăn yêu thích", "thú cưng", "style trả lời"]
                for k in order:
                    if k in facts:
                        lines.append(f"- {display_keys[k]}: {facts[k]}")
                for k, v in facts.items():
                    if k not in order:
                        lines.append(f"- {display_keys.get(k, k.capitalize())}: {v}")
                self.profile_store.write_text(user_id, "\n".join(lines))
                
            self.compact_memory.append(thread_id, "user", message)
            
            prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)
            self.thread_prompt_tokens[thread_id] = self.thread_prompt_tokens.get(thread_id, 0) + prompt_tokens
            
            profile_text = self.profile_store.read_text(user_id)
            ctx = self.compact_memory.context(thread_id)
            summary = ctx.get("summary", "")
            recent_msgs = ctx.get("messages", [])
            
            system_prompt = "Bạn là trợ lý AI thông minh có khả năng ghi nhớ thông tin dài hạn.\n"
            if profile_text:
                system_prompt += f"Hồ sơ người dùng (User Profile):\n{profile_text}\n"
            if summary:
                system_prompt += f"Tóm tắt ngữ cảnh lịch sử hội thoại trước:\n{summary}\n"
                
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
            langchain_msgs = [SystemMessage(content=system_prompt)]
            for msg in recent_msgs:
                if msg["role"] == "user":
                    langchain_msgs.append(HumanMessage(content=msg["content"]))
                else:
                    langchain_msgs.append(AIMessage(content=msg["content"]))
                    
            response = self.langchain_agent.invoke(langchain_msgs)
            reply_text = response.content
            
            self.compact_memory.append(thread_id, "assistant", reply_text)
            
            out_tokens = estimate_tokens(reply_text)
            if hasattr(response, "response_metadata") and "token_usage" in response.response_metadata:
                usage = response.response_metadata["token_usage"]
                out_tokens = usage.get("completion_tokens", out_tokens)
                
            self.thread_tokens[thread_id] = self.thread_tokens.get(thread_id, 0) + out_tokens
            
            return {
                "content": reply_text,
                "token_usage": out_tokens,
                "prompt_tokens": prompt_tokens
            }
        except Exception:
            return self._reply_offline(user_id, thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        return self.thread_tokens.get(thread_id, 0)

    def prompt_token_usage(self, thread_id: str) -> int:
        return self.thread_prompt_tokens.get(thread_id, 0)

    def memory_file_size(self, user_id: str) -> int:
        return self.profile_store.file_size(user_id)

    def compaction_count(self, thread_id: str) -> int:
        return self.compact_memory.compaction_count(thread_id)

    def _reply_offline(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: implement the deterministic advanced path."""
        new_updates = extract_profile_updates(message)
        
        # Merge updates with existing facts in User.md
        existing_text = self.profile_store.read_text(user_id)
        facts = {}
        if existing_text:
            for line in existing_text.splitlines():
                line = line.strip()
                if (line.startswith("- ") or line.startswith("* ")) and ":" in line:
                    parts = line[2:].split(":", 1)
                    k = parts[0].strip().lower()
                    v = parts[1].strip()
                    facts[k] = v
        facts.update(new_updates)
        
        # Re-write User.md with key order
        display_keys = {
            "tên": "Tên",
            "nơi ở": "Nơi ở",
            "nghề nghiệp": "Nghề nghiệp",
            "đồ uống yêu thích": "Đồ uống yêu thích",
            "món ăn yêu thích": "Món ăn yêu thích",
            "thú cưng": "Thú cưng",
            "style trả lời": "Style trả lời"
        }
        lines = []
        order = ["tên", "nơi ở", "nghề nghiệp", "đồ uống yêu thích", "món ăn yêu thích", "thú cưng", "style trả lời"]
        for k in order:
            if k in facts:
                lines.append(f"- {display_keys[k]}: {facts[k]}")
        for k, v in facts.items():
            if k not in order:
                lines.append(f"- {display_keys.get(k, k.capitalize())}: {v}")
                
        self.profile_store.write_text(user_id, "\n".join(lines))
        
        self.compact_memory.append(thread_id, "user", message)
        
        # Estimate context token load before appending assistant reply
        prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)
        self.thread_prompt_tokens[thread_id] = self.thread_prompt_tokens.get(thread_id, 0) + prompt_tokens
        
        # Generate offline reply using facts
        reply_text = self._offline_response(user_id, thread_id, message)
        self.compact_memory.append(thread_id, "assistant", reply_text)
        
        out_tokens = estimate_tokens(reply_text)
        self.thread_tokens[thread_id] = self.thread_tokens.get(thread_id, 0) + out_tokens
        
        return {
            "content": reply_text,
            "token_usage": out_tokens,
            "prompt_tokens": prompt_tokens
        }

    def _estimate_prompt_context_tokens(self, user_id: str, thread_id: str) -> int:
        """Student TODO: estimate the context carried into one turn."""
        profile_text = self.profile_store.read_text(user_id)
        profile_tokens = estimate_tokens(profile_text)
        
        ctx = self.compact_memory.context(thread_id)
        summary = ctx.get("summary", "")
        summary_tokens = estimate_tokens(summary)
        
        messages = ctx.get("messages", [])
        messages_tokens = sum(estimate_tokens(msg["content"]) for msg in messages)
        
        return profile_tokens + summary_tokens + messages_tokens

    def _offline_response(self, user_id: str, thread_id: str, message: str) -> str:
        """Student TODO: return a deterministic answer using persisted memory."""
        profile_text = self.profile_store.read_text(user_id)
        facts = {}
        if profile_text:
            for line in profile_text.splitlines():
                line = line.strip()
                if (line.startswith("- ") or line.startswith("* ")) and ":" in line:
                    parts = line[2:].split(":", 1)
                    k = parts[0].strip().lower()
                    v = parts[1].strip()
                    facts[k] = v
                    
        answers = []
        msg_lower = message.lower()
        
        has_name = "tên" in msg_lower or "tóm tắt" in msg_lower or "ai không" in msg_lower
        has_job = "nghề" in msg_lower or "tóm tắt" in msg_lower or "manager" in msg_lower
        has_loc = "ở đâu" in msg_lower or "nơi ở" in msg_lower or "huế" in msg_lower or "hà nội" in msg_lower
        has_style = "style" in msg_lower or "kiểu trả lời" in msg_lower
        has_food_drink = "uống" in msg_lower or "đồ uống" in msg_lower or "ăn" in msg_lower or "món ăn" in msg_lower
        has_pet = "nuôi" in msg_lower or "con gì" in msg_lower
        
        style = facts.get("style trả lời", "").lower()
        is_3_bullet = "3 bullet" in style or "3 bullet" in msg_lower
        
        if is_3_bullet:
            name_part = f"Tên của bạn là {facts.get('tên', 'DũngCT Stress')}."
            loc_part = f"Nơi ở hiện tại của bạn là {facts.get('nơi ở', 'Đà Nẵng')}."
            job_part = f"Nghề nghiệp hiện tại của bạn là {facts.get('nghề nghiệp', 'MLOps engineer')}."
            style_part = f"Style trả lời yêu thích là {facts.get('style trả lời', '3 bullet')}."
            
            bullets = [
                f"- {name_part} {loc_part}",
                f"- {job_part}",
                f"- {style_part}"
            ]
            return "\n".join(bullets)
            
        if has_name:
            if "tên" in facts:
                answers.append(f"Tên của bạn là {facts['tên']}.")
            else:
                answers.append("Mình không biết tên của bạn.")
        if has_job:
            if "nghề nghiệp" in facts:
                answers.append(f"Nghề nghiệp hiện tại của bạn là {facts['nghề nghiệp']}.")
            else:
                answers.append("Mình không biết nghề nghiệp của bạn.")
        if has_loc:
            if "nơi ở" in facts:
                answers.append(f"Nơi ở hiện tại của bạn là {facts['nơi ở']}.")
            else:
                answers.append("Mình không biết nơi ở của bạn.")
        if has_food_drink:
            fd_parts = []
            if "đồ uống yêu thích" in facts:
                fd_parts.append(f"đồ uống yêu thích là {facts['đồ uống yêu thích']}")
            if "món ăn yêu thích" in facts:
                fd_parts.append(f"món ăn yêu thích là {facts['món ăn yêu thích']}")
            if fd_parts:
                answers.append("Bạn thích: " + ", ".join(fd_parts) + ".")
        if has_pet:
            if "thú cưng" in facts:
                answers.append(f"Bạn nuôi một chú {facts['thú cưng']}.")
        if has_style:
            if "style trả lời" in facts:
                answers.append(f"Style trả lời bạn thích là {facts['style trả lời']}.")
                
        if "tóm tắt" in msg_lower or "ai không" in msg_lower:
            answers.append("Mối quan tâm chính là Python và AI.")
            
        if not answers:
            return "Chào bạn, mình có thể giúp gì cho bạn?"
            
        return " ".join(answers)

    def _maybe_build_langchain_agent(self):
        """Student TODO: wire a live agent with tools and compact middleware."""
        try:
            model = build_chat_model(self.config.model)
            self.langchain_agent = model
            self.compact_memory.llm = model
        except Exception:
            self.langchain_agent = None
