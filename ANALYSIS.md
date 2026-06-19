# Phân tích kết quả benchmark

Baseline chỉ giữ lịch sử trong một thread, nên câu hỏi ở thread mới gần như không
có dữ kiện để recall. Advanced ghi các fact ổn định vào `User.md`, cập nhật fact
mới khi có đính chính, vì vậy nhớ được tên, nghề nghiệp, nơi ở và preference qua
nhiều phiên.

Ở hội thoại ngắn, Advanced có thể tốn token hơn vì mỗi prompt còn mang theo hồ sơ
người dùng và summary. Đây là chi phí cố định để đổi lấy cross-session recall tốt
hơn; compact memory không mặc nhiên thắng khi lịch sử vẫn còn ngắn.

Ở stress benchmark, Baseline gửi lại toàn bộ lịch sử nên tổng `Prompt tokens
processed` tăng nhanh theo số lượt. Advanced nén phần cũ thành summary có giới
hạn, chỉ giữ các message gần nhất và profile ổn định. Vì vậy lợi ích chính của
compact nằm ở lượng context được xử lý, không nhất thiết ở số token câu trả lời.

`User.md` vẫn tăng theo số fact được lưu. Nếu extraction sai, profile có thể vừa
phình vừa củng cố thông tin sai. Bản cài đặt dùng guardrail đơn giản: bỏ qua câu
hỏi thuần túy, tránh một số phát biểu phủ định/giả định, và upsert theo key để
correction thay thế fact cũ. Production cần thêm confidence, provenance, TTL hoặc
memory decay và cơ chế để người dùng xem/xóa/sửa memory.
