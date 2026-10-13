# Bài viết ngắn — GPU FinOps cho NimbusAI

Dữ liệu lab được sinh với seed 25, giá GPU và hệ số điện lấy từ bộ dữ liệu minh họa tháng 6/2026. Trong một tháng mô phỏng, tổng chi phí từ **18.005 USD** xuống **10.355 USD**, tức tiết kiệm dự kiến **7.650 USD (42,5%)**. Riêng inference phục vụ 7.533.027 token/ngày: giá chuẩn hóa giảm từ **6,488** xuống **1,229 USD/1 triệu token** (81,1%). Giá thuê GPU/giờ thấp chưa bảo đảm chi phí trên mỗi câu trả lời thấp nếu thông lượng kém; do đó USD/1 triệu token là chỉ số vận hành chính.

## Đòn bẩy và hiện tượng GPU-Util “nói dối”

Mua GPU bằng spot/reserved đóng góp lớn nhất: **5.063 USD/tháng**, khoảng 66% tổng tiết kiệm dự kiến. Cascade, cache và batch tiết kiệm **1.188 USD/tháng**; right sizing sau khi loại trùng **799 USD/tháng**; tắt GPU nhàn rỗi **600 USD/tháng**. Chính sách mua ban đầu dự báo giảm 40,5% nhưng chưa tính đủ số giờ phải trả theo hợp đồng reserved. Chính sách mới xét thời gian cam kết và rủi ro gián đoạn, dự báo **30,6%**. Mức tiết kiệm thấp hơn nhưng phản ánh chi phí hợp đồng sát hơn.

`gpu-h100-4` có GPU-Util **98,2%** nhưng MFU chỉ **0,19**; `gpu-a10g-1` tương ứng **96,9%** và **0,27**. GPU-Util ghi nhận thời gian kernel hoạt động, không đo FLOPs hữu ích. Chờ bộ nhớ hoặc overhead khởi chạy kernel có thể làm thiết bị trông bận trong khi thông lượng thấp. Đổi loại GPU theo giá chỉ là giả thuyết: phải benchmark độ trễ, thông lượng, VRAM và băng thông trước khi chuyển.

## Năm phần mở rộng đã đo

| Mở rộng | Kết quả chính | Ý nghĩa |
|---|---|---|
| **Tier policy** | Chat 36 tháng chọn reserved 3 năm; RAG 24 tháng chọn reserved 1 năm; search 12 tháng, 18 giờ/ngày giữ on-demand. Spot dùng tỷ lệ gián đoạn giả định 4–12%/giờ tùy GPU. | Một mức giá rẻ theo giờ vẫn có thể thua khi trả tiền cho giờ cam kết không dùng. |
| **Right sizing theo MBU** | Hai A10G inference có MBU thấp được đề xuất L4, tiết kiệm mô phỏng **288 USD/tháng**. L4 vẫn đáp ứng VRAM quan sát với 10% headroom và băng thông với 20% headroom. | Chọn GPU bằng cả USD/GB HBM, sức chứa và băng thông, không chỉ USD/GPU-giờ. Khoản của `gpu-a10g-1` chỉ tính một lần trong tổng. |
| **Cache break-even** | Prefix nhỏ cần **3** lần đọc lại, prefix lớn cần **1** lần với phụ phí ghi/lưu trữ giả định 0,50 USD/1 triệu input token. Dữ liệu có trung bình **3,04** và **0,59** lần đọc lại/prefix; chính sách bật cache cho 278/471 prefix nhỏ và 132/314 prefix lớn. Lợi ích ròng **0,402 USD/ngày**. | Đọc cache rẻ chỉ sinh lợi nếu tái sử dụng đủ để bù phí ghi. |
| **Ngân sách reasoning** | **201/2.400 request (8,4%)** chiếm **15,2%** chi phí inference tối ưu và **94,0%** năng lượng truy vấn theo mô hình. Cap 5% giả lập chuyển 81 request/ngày về đường thường, tiết kiệm **0,41 USD** và **11,93 kWh/ngày**. | Chỉ dùng reasoning cho tác vụ khó hoặc độ tin cậy thấp; cần đo chất lượng trước khi áp dụng cap. |
| **Lập lịch theo carbon** | Job có thể gián đoạn tiêu thụ ước tính **1.789 kWh/tháng**. Chuyển từ `us-east-1` sang `europe-north1` giảm mô phỏng **626,15 kgCO₂e** và **53,67 USD** tiền điện/tháng. | `us-east-wa` rẻ điện nhất nhưng `europe-north1` sạch nhất; lựa chọn còn phụ thuộc năng lực vùng, dữ liệu và độ trễ. |

## Ba hành động đầu tiên

1. Thí điểm spot cho training/batch có checkpoint, đo số lần gián đoạn, thời gian chạy lại và chi phí thực trả.
2. Route request đơn giản sang model nhỏ, rồi bật cache/batch khi phù hợp; theo dõi chất lượng, độ trễ và USD/1 triệu token.
3. Tắt GPU nhàn rỗi và profile GPU có MFU thấp. Dùng tag coverage **92%** để showback chi phí trước khi chargeback.

Các con số là kịch bản từ dữ liệu tổng hợp, chưa phải hóa đơn hay điện năng đo thực tế. Thời gian cần GPU, tỷ lệ gián đoạn spot, ID prefix cache và phụ phí ghi là giả định minh họa. Phần mua GPU và telemetry fleet có thể cùng đại diện một công suất; phải đối soát để tránh trùng trước khi cam kết mục tiêu tài chính. Tiết kiệm điện theo vùng chưa cộng vào tổng vì thiếu giá thuê GPU theo vùng và chi phí di chuyển. Giá và hệ số lưới điện cần cập nhật khi triển khai.
