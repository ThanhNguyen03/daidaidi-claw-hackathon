<!-- Ghi chú nội bộ: tài liệu mô phỏng cho mục đích test/dev, không phải spec vận hành chính thức của AdtimaBox. -->

# CSHub Reference

## 1. Đăng ký, Đăng nhập và Quản lý Tài khoản
- **Truy cập & Bảo mật:** Đăng nhập bằng email doanh nghiệp và mật khẩu mạnh (tối thiểu 14 ký tự gồm chữ hoa, chữ thường, số, ký tự đặc biệt). Hệ thống yêu cầu xác thực OTP qua email cho mỗi lần đăng nhập, mã OTP có hiệu lực trong 10 phút.
- **Xử lý sự cố:** Tài khoản sẽ bị tạm khóa nếu nhập sai mật khẩu quá 3 lần/ngày hoặc sai OTP quá 5 lần/phiên. Khi đó, người dùng cần gửi email cho bộ phận hỗ trợ hoặc nhân viên Account phụ trách để yêu cầu mở khóa.
- **Quản lý tổ chức:** Quản trị viên (Admin) có thể mời thành viên mới tham gia vào hệ thống và phân các vai trò như Admin, Quản trị viên vận hành, Quản trị nội dung hoặc Người xem.

## 2. Phân quyền Vận hành (Role Matrix)
Hệ thống được thiết kế theo nguyên tắc "chỉ cấp đúng quyền cần thiết" (Least Privilege) với 6 vai trò chính:
- **Vận hành Loyalty:** Quản lý điểm thưởng, hạng thành viên, quà tặng, voucher và chiến dịch.
- **Vận hành Booking:** Quản lý đơn hàng, sản phẩm, cửa hàng, doanh thu và nhân sự PG.
- **Vận hành Event:** Tạo sự kiện, quản lý danh sách khách tham dự và thao tác check-in.
- **Vận hành Bài viết:** Đăng tải, phân loại bài viết và gửi thông báo Miniapp.
- **Vận hành Tin nhắn:** Quản lý gửi tin hàng loạt (Broadcast), thiết lập luồng tự động (Automation) và quản lý biểu mẫu (Lead Form).
- **Vận hành Khảo sát:** Tạo bảng hỏi, quản lý bài kiểm tra và khóa học.

**Quy tắc bảo mật tối thượng:** Tuyệt đối không có vai trò nào (dù là Admin) được phép xóa (Delete) hoặc xuất dữ liệu thô (Export Raw Data) của người dùng/khách hàng nhằm bảo vệ tài sản dữ liệu.

## 3. Quản lý Gói dịch vụ (Package)
- Hệ thống sẽ gửi email và hiển thị banner cảnh báo trước 30, 15 và 7 ngày khi gói dịch vụ sắp hết hạn.
- Nếu quá hạn từ 1 đến 30 ngày: Các luồng tự động (Automation), thông báo Broadcast và Miniapp sẽ ngừng hoạt động; Quản trị viên chỉ có thể xem và tải dữ liệu, không thể thao tác thêm.
- Từ ngày thứ 31 trở đi: Hệ thống khóa toàn bộ truy cập vào tổ chức và dữ liệu có thể bị xóa sau thời hạn lưu trữ này nếu không gia hạn.

## 4. Khai thác các Tính năng (Module) Chính

**Xây dựng Phân khúc (Segment):** Người dùng có thể lọc khách hàng dựa trên Nhãn (Tag) có sẵn, Đặc điểm (nhân khẩu học, nguồn) hoặc Hành vi (tương tác bài viết, đổi quà...). Dữ liệu này dùng để gửi tin nhắn Broadcast chính xác hoặc phân tích báo cáo Chân dung khách hàng.

**Tự động hóa (Automation Flow):** Thiết lập kịch bản chăm sóc khách hàng bằng cách kéo thả. Luồng bắt đầu từ một "Sự kiện kích hoạt" (như khách theo dõi OA, gửi form) nối đến các "Hành động" (gửi tin nhắn Zalo, gán nhãn, cập nhật trạng thái) thông qua các điểm kiểm tra điều kiện và thời gian chờ.

**Thu thập dữ liệu (Zalo Lead):** Kết nối trực tiếp "Mã biểu mẫu" (Form ID) từ Zalo OA để đồng bộ thông tin khách điền (Họ tên, SĐT) tự động về hệ thống CSHub và tự động gán nhãn.

**Sự kiện (Event):** Tạo sự kiện với thông tin thời gian, địa điểm, banner và cấu hình mã QR check-in. Tại thực địa, PG dùng Miniapp quét mã QR của khách để đổi trạng thái từ "REGISTER" (Đăng ký) sang "CHECKIN" (Đã có mặt).

**Khách hàng thân thiết (Loyalty):** Xây dựng Cấp độ/Hạng thành viên dựa trên tiêu chí điểm tích lũy. Tổ chức các Chiến dịch và Nhiệm vụ (thực hiện một lần, hàng ngày...) để khách hàng lấy điểm đổi Voucher/Quà tặng từ kho.

**Nội dung & Tin nhắn (Article & Messaging):** Trình soạn thảo giúp xuất bản bài viết, quản lý danh mục và gửi thông báo trực tiếp qua Miniapp. Thống kê chi tiết số lượt xem, người xem duy nhất (Unique View) và lượt chia sẻ. Ngoài ra, có thể lên lịch gửi tin nhắn hàng loạt (Broadcast) qua ZNS/ZBS cho các phân khúc mục tiêu.

**Đặt hàng & Dịch vụ (Booking):** Thiết lập danh sách Chi nhánh, Nhân viên trực thuộc và Sản phẩm/Dịch vụ (hỗ trợ nhiều phiên bản cấu hình như Giá, Đơn vị SKU). Quản lý cập nhật trạng thái vòng đời của đơn hàng: Chờ xác nhận → Đang giao → Hoàn thành → Hủy.
