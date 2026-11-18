# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt (`PASS floors`, fail rate observed `0.28` -> corrected `0.30`) | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt (`FAIL floors`, fail rate observed `0.09` -> corrected `0.30`) | loại |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & cách sửa rubric |
|---|---|---|---|---|---|
| 1 | `H-008` (`tone_ok`) | PASS | FAIL | Người đúng | Câu `"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."` dùng đại từ thân mật quá mức ("em/anh", "nha", "check giúp"), sai chuẩn CSKH; sửa rubric: cấm xưng hô thân mật/từ lóng ("nha", "check giúp"). |
| 2 | `H-017` (`tone_ok`) | PASS | FAIL | Người đúng | Câu `"Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha."` dùng "bạn ơi", "rồi nha" thiếu trang trọng dù có "Dạ"; sửa rubric: không đánh PASS chỉ vì có từ "Dạ" ở đầu câu. |
| 3 | `H-029` (`tone_ok`) | PASS | FAIL | Người đúng | Câu `"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."` cụt lủn, mang sắc thái đuổi khéo; sửa rubric: bổ sung tiêu chí không được cộc lốc/ngăn khách phản hồi. |
| 4 | `H-042` (`tone_ok`) | FAIL | PASS | Người đúng | Câu `"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."` lịch sự, rõ ràng, ngắn gọn; sửa rubric: không phạt các câu trả lời ngắn nhưng đầy đủ kính ngữ. |
| 5 | `HL-016` (`helpful`) | PASS | FAIL | Người đúng | Câu `"Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này..."` chỉ xin lỗi chung chung, không nêu hướng xử lý hay bước tiếp theo; sửa rubric `helpful`: bắt buộc có hành động/bước tiếp theo cụ thể, không chấm PASS chỉ vì giọng xin lỗi lịch sự. |
| 6 | `HL-020` (`helpful`) | PASS | FAIL | Người đúng | Câu `"Dạ, LogiX đã hoàn 90.000đ cho đơn O-303 ạ."` có vẻ đầy đủ nhưng thiếu thông tin xác nhận/thời gian nhận tiền hoặc bối cảnh yêu cầu; sửa rubric: kiểm tra đủ thông tin hành động theo từng loại tình huống. |

## Kết luận
- **Tiêu chí bị loại:** `helpful` bị loại và **không được dùng làm gate**, vì đạt `κ = 0.375` (< 0.6) và `Recall = 0.300` (< 0.7) với ma trận nhầm lẫn `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}`. Judge bỏ sót tới 21/30 ca lỗi (`fn = 21`), khiến tỉ lệ lỗi quan sát chỉ là `0.09` trong khi tỉ lệ lỗi thực (sau hiệu chỉnh Rogan-Gladen) là `0.30` — dùng làm gate sẽ cho qua phần lớn các câu trả lời vô ích nhưng lịch sự.
- **Tiêu chí được giữ:** `tone_ok` đạt cả 3 sàn (`κ = 0.757`, `P = 0.857`, `R = 0.800`), có thể dùng làm tín hiệu phụ trợ sau khi tiếp tục tinh chỉnh các biên giới xưng hô/cộc lốc trong rubric.
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
