# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case đã điều tra: `seeded_regression C-002@11`

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (đối chứng `fixed C-002@11`) |
| Triệu chứng | `lab8` grader FAIL (`status resolved != denied`); `reply` nói `"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."`, `ledger`: `refund_vnd=20000`, `refund_count=1` (nhãn `expected`: `refund_vnd=0`, `refund_count=0`, `status=denied`). |
| Bước sai đầu tiên | Event `3 model_override {"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event `1 handoff` truyền đúng `claim_id: "C-002"`, event `2 investigator` gọi `lookup_order` trả về đúng dữ liệu đơn `O-202` từ DB; tới event `3` mới xuất hiện `model_override` lấy `delay_days: 5` từ ticket để ghi đè sự thật DB, kéo theo event `4 quote` tính `20000` (`SHIP-LATE-03`). |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) trong `docs/failure_taxonomy.md` |
| Đối chứng | Trên `fixed C-002@11`: event `1 handoff` → event `2 investigator` (`lookup_order`) → event `3 quote` (`amount_vnd: 0, reason: "no_entitlement"`) → event `4 reply` từ chối; không có event `model_override`, `ledger=0`, `status=denied`. |
| Regression test | Grader `DbFactKept` (`db_fact_kept`) trong `src/lab9/graders.py` bắt mọi event `model_override`; kết hợp `RefundAmountCorrect` và `TrialPass` (`pass_rate`) trong `tests/test_lab9_graders.py` (đã xác minh fail trên `seeded_regression` với `db_fact_kept=0.9286`, `pass_rate=0.7143`, và pass trên `fixed` với `1.0`). |
| Chưa chắc chắn | Trace chỉ ghi `{"delay_days": 5}` ở event `3`, không ghi prompt nội bộ khiến model ưu tiên ticket hơn kết quả `lookup_order`. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
