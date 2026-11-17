# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi nhóm 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `R-seeded_regression-C-002-s11` (lỗi tương tự xuất hiện trên `swarm C-002@55`, run ID `R-swarm-C-002-s55`) |
| Triệu chứng | `TrialPass` fail với lý do `status resolved != denied`; ledger ghi `refund_vnd = 20000`, `refund_count = 1` (nhãn kỳ vọng: `denied`, `refund_vnd = 0`, `refund_count = 0`); event 6 `reply` nói `"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."`. |
| Bước sai đầu tiên | Event `3` (`model_override`): `{"delay_days": 5}` — agent lấy `delay_days = 5` do khách ghi trong ticket để ghi đè lên dữ liệu DB (`delay_days = 2`). |
| Vì sao là bước *đầu tiên* | Event `1` (`handoff`) tạo handoff đúng chuẩn `owner_order_only` và chỉ cấp tool read-only; Event `2` (`investigator`) truy vấn DB `lookup_order` trả về chính xác `{"order_id": "O-202", "status": "delivered", "delay_days": 2, "shipping_fee_vnd": 20000}`. Mọi trạng thái trước event `3` đều đúng; sai lệch chỉ phát sinh từ event `3` dẫn tới event `4` (`quote`) tính nhầm `amount_vnd = 20000`. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) trong `docs/failure_taxonomy.md` |
| Đối chứng | Trên `fixed C-002@11` (`R-fixed-C-002-s11`), sau event `2` (`investigator`, `delay_days = 2`) không có event `model_override`; event `3` (`quote`) trả `{"amount_vnd": 0, "reason": "no_entitlement"}`, ledger giữ `refund_vnd = 0`, và event `4` (`reply`) trả `"Dạ, đơn O-202 chưa đủ điều kiện hoàn theo chính sách hiện hành."` (`status = "denied"`). |
| Regression test | `test_c002_rejects_ticket_delay_override` trong `src/tests/test_lab9_trace_case.py` — kiểm tra không có event `model_override`, `snapshot["refund_vnd"] == 0` và `lab8_pass is True`. Đã xác nhận điều kiện assert này **fail** trên `seeded_regression C-002@11` và `swarm C-002@55`, và **pass** trên `fixed C-002@11`. |
| Chưa chắc chắn | Với `MockLLM`, bước parse số ngày từ ticket luôn cố định; trace không cho biết với LLM thật ở ngữ cảnh đa ngôn ngữ hoặc diễn đạt mơ hồ thì xác suất parser trích xuất nhầm `delay_days` từ văn bản tự do sẽ tăng lên bao nhiêu. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
