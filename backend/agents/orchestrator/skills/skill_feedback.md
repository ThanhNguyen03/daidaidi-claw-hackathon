# AdtimaBox Sales Agent — User Feedback & Skill Adjustments

Dưới đây là các feedback của người dùng để điều chỉnh lại hành vi của Agent và các file Skill nhằm tối ưu hóa trải nghiệm thực tế cho đội ngũ Sale/Account (non-tech):

## 1. Loại bỏ Jargon & Các log kỹ thuật hiển thị trên chat
*   **Vấn đề:** Các thuật ngữ viết tắt và các log kỹ thuật (masking, mapping table, system tags) làm giảm tính thẩm mỹ của cuộc hội thoại.
*   **Giải pháp:** 
    *   Ẩn hoàn toàn các log kỹ thuật và bảng mapping khỏi màn hình chat (chỉ xử lý ngầm ở backend).
    *   Việt hóa các thuật ngữ chuyên ngành sang ngôn ngữ tự nhiên, chuyên nghiệp (Zalo OA -> Trang Zalo chính thức, ZNS -> Tin nhắn Zalo chăm sóc khách hàng, API -> Cổng kết nối dữ liệu mở, migrate -> đồng bộ dữ liệu cũ, O2O -> Kết nối cửa hàng vật lý lên môi trường số).

## 2. Chuẩn hóa Định vị Tính năng & Kiến trúc Kỹ thuật
*   **Kết nối OA/ZNS:** Nêu rõ AdtimaBox kết nối thông qua **Cổng kết nối mở (Open API)**.
*   **Native:** Mô tả trải nghiệm mượt mà trực tiếp trên Zalo Mini App và đội ngũ phát triển am hiểu sâu sắc hành vi người dùng Zalo.
*   **Zalo DMP & Auto EDA:** Định vị đúng là công cụ **phân tích khám phá chân dung khách hàng** (insight exploration), không dùng để trực tiếp kích hoạt/gửi tin nhắn tự động.

## 3. Quy trình Điều phối mới (Strict Sales Orchestration Pipeline)
*   **Bước 1: Thu thập & Xác minh thông tin (Elicitation & Verification):** Hỏi kỹ từng câu. Nếu người dùng chưa trả lời, **phải hỏi lại** câu đó để làm rõ, không tự ý giả định.
*   **Bước 2: Đề xuất Chiến lược & Case Study (Strategy & Case Studies):** Hỏi Sale xác nhận định hướng chiến lược.
*   **Bước 3: Đánh giá Pháp lý & Chính sách (Compliance):** Chạy SAU bước Chiến lược. Hỏi Sale xác nhận nhãn hàng đáp ứng được.
*   **Bước 4: Thiết kế Giải pháp & Đặc tả Luồng Mini App (Solution Design & Wireframe Spec):** 
    *   *Lưu ý quan trọng:* Bước này phải chạy **TRƯỚC** bước Báo giá, để xác định rõ tất cả các tính năng, trang màn hình (UX modules) và luồng đi của khách hàng. Từ đó mới biết chính xác có phát sinh thêm chi phí module nào không.
    *   **CỔNG XÁC NHẬN:** Hỏi Sale duyệt trước luồng Mini App và đặc tả tính năng.
*   **Bước 5: Thiết kế Giải pháp (Solution Design)**
*   Đưa ra luồng hành trình khách hàng chi tiết (Customer Journey) và các điểm cần làm rõ về kỹ thuật (Technical Gaps).
*   **CỔNG XÁC NHẬN:** Đợi phản hồi và xác nhận từ Sale.

### Bước 5.5: Xác nhận Đề cương Đề xuất (Draft Proposal Confirmation)
*   **QUY TẮC MỚI:** Trước khi thực hiện lắp ráp bản đề xuất chi tiết (bước tạo bản thuyết trình, vẽ sơ đồ và hoàn thiện nội dung chi tiết), Agent phải trình bày một bảng đề cương tóm tắt (Draft Outline) gồm các lựa chọn cốt lõi để người dùng phê duyệt trước.
*   **CỔNG XÁC NHẬN:** Sale xác nhận đề cương OK mới tiến hành bước 6 (tạo bản đề xuất hoàn chỉnh).

### Bước 6: Lắp ráp đề xuất cuối cùng (Proposal Assembler)
*   Tạo bản Proposal hoàn chỉnh dựa trên tất cả các bước đã được đồng thuận ở trên.

## 4. Quy tắc Định dạng Bảng (Table Formatting)
*   **Phản hồi:** Các thông tin như báo giá, tùy chọn thời gian, danh sách tính năng, đặc tả màn hình cần được định dạng dưới dạng bảng biểu thay vì dạng văn bản gạch đầu dòng để tăng tính trực quan, chuyên nghiệp và dễ đọc.
*   **Giải pháp:** Mọi thông tin có cấu trúc so sánh hoặc danh sách số liệu/mốc thời gian đều phải mặc định chuyển sang Markdown Table.

## 5. Điều chỉnh Chi tiết Báo giá & Thuật ngữ
*   **UTC 80M:** Chi phí phát triển (development cost), không gọi là phí bản quyền.
*   **Unique Code / UTC Code:** Sử dụng cụm từ **"unique code"** hoặc **"UTC code"** thay vì "mã độc bản" để dễ hiểu và phổ thông hơn.

## 6. Chủ động đưa ra các Tùy chọn (Options/Variants)
*   **Nguyên tắc:** Khi phản hồi yêu cầu hoặc lên báo giá, Agent cần chủ động chia nhỏ và đề xuất các **tùy chọn (Option 1, Option 2, Option 3)** về mặt thời gian chạy, phương án lưu trữ dữ liệu hoặc quy mô giải pháp. Việc này giúp Account Executive (AE) dễ dàng lựa chọn phương án phù hợp nhất để trình bày với khách hàng.

## 6. Đối chiếu Thời gian Thực tế (Time-Awareness Constraint)
*   **Nguyên tắc:** Khi lên các phương án về mặt thời gian (timeline) cho các chiến dịch gắn liền với sự kiện, Agent bắt buộc phải **đối chiếu ngày hiện tại trên lịch hệ thống** với lịch trình diễn ra sự kiện thực tế.

## 7. Tư vấn Chuyển giao Dữ liệu ra Nước ngoài
*   **Phản hồi:** Các vấn đề liên quan đến hạ tầng kỹ thuật và thủ tục pháp lý để chuyển dữ liệu ra nước ngoài rất nhạy cảm và phức tạp.
*   **Giải pháp:** Agent không được tự ý xác nhận phương án lưu trữ, đồng bộ dữ liệu ra nước ngoài mà phải hướng dẫn người dùng liên hệ trực tiếp với Đội ngũ Kỹ thuật (Tech Team) để được tư vấn chính xác.
