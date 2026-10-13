# Bài viết ngắn — GPU FinOps cho NimbusAI

Dữ liệu lab được sinh với seed 25, giá GPU và hệ số điện lấy từ bộ dữ liệu minh họa tháng 6/2026. Trong một tháng mô phỏng, tổng chi phí từ **18.005 USD** xuống **8.848 USD**, tức tiết kiệm dự kiến **9.157 USD (50,9%)**. Riêng inference phục vụ 7.533.027 token/ngày: giá chuẩn hóa giảm từ **6,488** xuống **1,126 USD/1 triệu token** (82,6%). Chỉ số trên token quan trọng vì giá thuê GPU/giờ thấp chưa bảo đảm chi phí trên mỗi câu trả lời thấp nếu thông lượng kém.

## Đòn bẩy và hiện tượng GPU-Util “nói dối”

Mua GPU bằng spot/reserved đóng góp lớn nhất: **6.690 USD/tháng**, khoảng 73% tổng tiết kiệm dự kiến. Công việc có thể gián đoạn dùng spot kèm checkpoint; inference chạy ổn định dùng reserved. Phép tính đã xét số ngày chạy thực tế của từng job, không mặc định mọi job chạy đủ 30 ngày. Cascade, cache và batch tiết kiệm **1.212 USD/tháng**; đây là bước tiếp theo vì có thể áp dụng trên từng loại request và đo chất lượng đầu ra. Tắt giờ GPU nhàn rỗi đem lại **600 USD/tháng**.

`gpu-h100-4` có GPU-Util **98,2%** nhưng MFU chỉ **0,19**; `gpu-a10g-1` tương ứng **96,9%** và **0,27**. GPU-Util ghi nhận thời gian kernel hoạt động, không đo FLOPs hữu ích. Chờ bộ nhớ hoặc overhead khởi chạy kernel có thể làm thiết bị trông bận trong khi thông lượng thấp. Nếu đổi H100 sang A100 và A10G sang L4 theo bảng giá, mức giảm tiền thuê *ước tính tối đa* là **655 USD/tháng**. Đây chưa phải tiết kiệm đã xác nhận: cần benchmark độ trễ, thông lượng, VRAM và băng thông trước khi đổi máy.

## Hai phần mở rộng đã đo

**Ngân sách reasoning.** Có **201/2.400 request (8,4%)** dùng reasoning, chiếm **16,5%** chi phí inference tối ưu nhưng **94,0%** năng lượng truy vấn trong mô hình. Bộ sinh dữ liệu cho output reasoning dài gấp sáu lần và hàm năng lượng áp hệ số 80×. Giới hạn 10% đã được đáp ứng; giả lập giới hạn **5%** cần chuyển 81 request/ngày về đường xử lý thường. Với đầu ra thường ngắn bằng một phần sáu, tiết kiệm dự kiến **0,41 USD** và **11,93 kWh/ngày**. Chỉ bật reasoning cho tác vụ khó hoặc độ tin cậy thấp, sau đó kiểm tra chất lượng câu trả lời; dữ liệu hiện không có nhãn chất lượng để tự động quyết định.

**Lập lịch theo carbon.** Các job có thể gián đoạn tiêu thụ ước tính **1.789 kWh/tháng** khi nhân GPU giờ với công suất danh định trong catalog. Chuyển từ `us-east-1` sang vùng sạch nhất `europe-north1` giảm mô phỏng **626,15 kgCO₂e/tháng** và **53,67 USD/tháng** tiền điện. `us-east-wa` rẻ điện nhất, còn `europe-north1` sạch nhất. Cần kiểm tra năng lực vùng, vị trí dữ liệu và độ trễ. Con số điện chưa được cộng vào tiết kiệm GPU vì giá thuê theo vùng và chi phí chuyển vùng không có trong dataset.

## Ba hành động đầu tiên

1. Thí điểm spot cho job training/batch có checkpoint; đo số lần gián đoạn và thời gian chạy lại so với giả định.
2. Triển khai cascade cho request đơn giản, sau đó bật cache/batch với request phù hợp; theo dõi chất lượng, độ trễ và USD/1 triệu token.
3. Tắt GPU nhàn rỗi và profile hai GPU có MFU thấp. Dùng tag coverage **92%** để showback chi phí cho các nhóm trước khi chargeback.

Các mức tiết kiệm là kịch bản từ dữ liệu tổng hợp, chưa phải hóa đơn hay điện năng đo thực tế. Phần mua GPU và telemetry fleet có thể đại diện cho cùng công suất; cần đối soát tài nguyên để loại trùng trước khi cam kết mục tiêu tài chính. Giá và hệ số lưới điện cần cập nhật khi triển khai.
