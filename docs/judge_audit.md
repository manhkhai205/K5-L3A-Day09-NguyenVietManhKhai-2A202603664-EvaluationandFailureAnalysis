# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có (κ=0.757, P=0.857, R=0.800; observed=0.28 → RG=0.30) | **dùng** |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không (κ=0.375 < 0.6, R=0.300 < 0.7; observed=0.09 → RG=0.30) | **loại** |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | `H-008` (`tone_ok`) | PASS | FAIL | Người đúng | `"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."` — xưng `"em"` + `"nha"` quá suồng sã; sửa rubric `tone_ok`: cấm xưng hô thân mật/khẩu ngữ (`nha`, `nhé`, `em/bạn`). |
| 2 | `H-029` (`tone_ok`) | PASS | FAIL | Người đúng | `"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."` — giọng ra lệnh/đẩy khách; sửa rubric: tách rule không đánh dấu PASS chỉ vì có từ `"Dạ"`/`"vui lòng"` nếu câu mang hàm ý chặn giao tiếp. |
| 3 | `H-051` (`tone_ok`) | FAIL | PASS | Người đúng | `"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."` — CS LogiX cho phép dùng `"refund"`; bổ sung whitelist thuật ngữ CS vào rubric để giảm FP. |
| 4 | `H-081` (`tone_ok`) | FAIL | PASS | Judge đúng | `"Dạ, đơn O-107 chưa đủ điều kiện hoàn..."` — người gán nhãn đọc nhầm ticket; cần sửa lại nhãn ground truth trong bộ calibration. |
| 5 | `HL-015` (`helpful`) | PASS | FAIL | Người đúng | `"Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ."` nhưng ledger chỉ ghi `40.000đ` (`sai tiền`). Judge chỉ đọc reply, không có dữ liệu ledger nên không thể phát hiện FM-08. |
| 6 | `HL-016` (`helpful`) | PASS | FAIL | Người đúng | Reply xin lỗi rất dài dòng nhưng báo sai `55.000đ` so với ledger `35.000đ`. Judge bị thiên lệch theo văn phong lịch sự/dài dòng (verbosity bias) và mù thông tin ledger. |
| 7 | `HL-047` (`helpful`) | PASS | FAIL | Người đúng | `"Ok bạn, đơn O-515 xử lý rồi nhé."` (`sai xưng hô` + thiếu số tiền cụ thể); rubric `helpful` quá lỏng, cần chuyển kiểm tra xưng hô sang `tone_ok` và kiểm tra số tiền bằng code. |

## Kết luận
- **Tiêu chí bị loại và lý do:** Loại `judge_helpful` khỏi mọi cổng chặn release vì không đạt ngưỡng hiệu chuẩn (`κ = 0.375 < 0.6`, `Recall = 0.300 < 0.7`). Ma trận nhầm lẫn của `helpful` là `tp=9, fp=0, fn=21, tn=70`: judge bỏ sót tới **21/30 ca lỗi thật (70% false negative)**, khiến tỉ lệ lỗi quan sát chỉ là `0.09` trong khi tỉ lệ lỗi thực tế sau hiệu chỉnh Rogan-Gladen là `0.30`. Nguyên nhân gốc: 18/21 ca `FN` là lỗi **sai số tiền so với ledger** (judge không được cung cấp ledger và dễ bị đánh lừa bởi câu xin lỗi dài dòng) và 3/21 ca là **sai xưng hô**.
- **Hành động sửa rubric & phân vai grader:**
  1. Không dùng LLM judge để chấm tính đúng đắn số tiền — thay bằng **code grader** đối chiếu trực tiếp `reply` với `snapshot["refund_vnd"]` (bắt FM-08 ở M3).
  2. Giữ `tone_ok` (đã đạt FLOORS: `tp=24, fp=4, fn=6, tn=66`, `κ=0.757`, `P=0.857`, `R=0.800`, RG=`0.30`) làm chỉ số theo dõi chất lượng giao tiếp và cập nhật rubric: whitelist từ `"refund"`, cấm emoji/xưng hô suồng sã (`nha`, `nhé`, `bạn`), kiểm tra giọng ra lệnh.
- **Rủi ro còn lại:** Judge chỉ được kiểm trên dữ liệu replay đã công khai (`judge_tone_public.csv`, `judge_helpful_public.csv`); cần thu thập nhãn người mới trên tập held-out thật trước khi dùng `tone_ok` làm cổng blocking.
