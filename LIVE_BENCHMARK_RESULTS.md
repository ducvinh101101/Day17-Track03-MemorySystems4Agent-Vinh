# Kết quả so sánh hai agent bằng LLM thật

Gateway: Antco AI Gateway (OpenAI-compatible)  
Model: `gemini-3.1-flash-lite`  
Chế độ: `LIVE LLM`

## Standard Benchmark

| Agent | Agent tokens only | Prompt tokens processed | Cross-session recall | Response quality | Memory growth (bytes) | Compactions |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 46,653 | 184,262 | 0.21 | 0.33 | 0 | 0 |
| Advanced | 10,636 | 46,272 | 0.82 | 0.86 | 241 | 7 |

Advanced tăng recall từ `0.21` lên `0.82` và giảm khoảng `74.9%` prompt tokens.
Đổi lại, nó tạo file memory 241 bytes và thực hiện 7 lần compaction.

## Long-Context Stress Benchmark

| Agent | Agent tokens only | Prompt tokens processed | Cross-session recall | Response quality | Memory growth (bytes) | Compactions |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 5,604 | 48,632 | 0.00 | 0.13 | 0 | 0 |
| Advanced | 4,337 | 18,129 | 1.00 | 1.00 | 147 | 26 |

Trong hội thoại dài, Advanced đạt recall tuyệt đối và giảm khoảng `62.7%` prompt
tokens. 26 lần compaction cho thấy lịch sử cũ thực sự được nén thay vì tiếp tục
đưa nguyên văn vào mọi prompt.

## Kết luận

- Baseline đơn giản và không phát sinh persistent memory, nhưng quên khi đổi
  thread và chi phí context tăng mạnh theo độ dài hội thoại.
- Advanced nhớ qua phiên nhờ `User.md`; summary và recent messages giữ context
  cần thiết với prompt nhỏ hơn.
- Advanced có thêm rủi ro vận hành: memory có thể lưu sai hoặc tăng dần, và
  compaction có thể làm mất chi tiết. Vì vậy cần extraction guardrail, conflict
  handling và quyền xem/sửa/xóa memory.
