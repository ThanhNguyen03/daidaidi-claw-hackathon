# Reference - Bug Intake

## Mapping nickname dev → Jira username
Sale thường gọi dev bằng nickname thân mật, không phải tên Jira. Tự nhận diện nickname và map sang username Jira tương ứng:

| Nickname (sale hay gọi) | Jira username |
|---|---|
| a Cóc | coc.dev |
| a Minh | minh.dev |
| a Hiên | hien.dev |
| a Minh nhỏ | minhnho.dev |
| Thông | thong.dev |

Lưu ý: "a Minh" và "a Minh nhỏ" là 2 dev khác nhau - nếu sale chỉ nói "Minh" mà không rõ Minh nào, hỏi lại để xác nhận đúng người trước khi assign.

Khi tóm tắt issue và tạo ticket, hiển thị cả nickname lẫn Jira username, ví dụ: "Dev phụ trách: a Cóc (coc.dev)".

Nếu sale nhắc tên dev không có trong bảng, hỏi lại để xác nhận username Jira hoặc note "chưa rõ - cần PM assign sau".

## Mức độ ưu tiên (Priority)
Tự gợi ý priority dựa theo loại lỗi/màn hình, không để trống mặc định:

| Loại lỗi/màn hình | Priority gợi ý |
|---|---|
| Thanh toán/Checkout, mất tiền, sai số tiền | High |
| Đăng nhập/OTP không vào được app | High |
| Crash app, màn hình trắng | High |
| Lỗi hiển thị UI, sai chính tả, lệch layout | Low |
| Các lỗi khác chưa rõ mức độ | Medium |

Sau khi tự gợi ý, show cho sale xác nhận: "Mình đề xuất priority: [X] vì [lý do ngắn]. Đồng ý không, hay đổi mức khác?" - không tự chốt priority mà không hỏi qua sale.

## Validate: common error (not a bug)
Trước khi nhận issue là bug thật, đối chiếu với danh sách lỗi thường gặp KHÔNG phải bug hệ thống. Nếu mô tả khớp pattern dưới đây, giải thích nguyên nhân và hỏi xác nhận lại trước khi tạo ticket:

| Hiện tượng | Nguyên nhân thường gặp (not a bug) | Cách phản hồi |
|---|---|---|
| Bấm OTP không nhận được mã | Mạng yếu, sai số điện thoại, SMS bị delay từ nhà mạng, hoặc đã quá số lần gửi OTP trong khoảng thời gian (rate limit) | "Trường hợp này thường do mạng/nhà mạng delay SMS hoặc do giới hạn số lần gửi OTP, không phải lỗi hệ thống. Khách đã thử gửi lại sau 1-2 phút chưa? Nếu vẫn không nhận được sau nhiều lần thử thì mình tạo ticket để check kỹ hơn." |
| Chưa được cấp quyền / không vào được tính năng | Tài khoản chưa được phân quyền (role/permission) theo đúng gói dịch vụ hoặc role hiện tại, không phải bug code | "Trường hợp này có thể do tài khoản chưa được cấp quyền/role phù hợp, không phải lỗi hệ thống. Kiểm tra giúp tài khoản đang ở gói/role nào, hoặc liên hệ admin để cấp quyền. Nếu đã đúng quyền mà vẫn lỗi thì mình tạo ticket." |

Nếu sau khi giải thích mà sale vẫn khẳng định đây là bug thật (vd: đã đúng quyền/đã thử nhiều lần vẫn lỗi) → tiếp tục flow tạo ticket bình thường, không chặn.

Nếu hiện tượng không khớp pattern nào trong bảng → coi là bug hợp lệ, tiếp tục flow thu thập thông tin bình thường.

## Mẫu câu hỏi khi thiếu thông tin

Thiếu **màn hình lỗi**:
> Màn hình nào bị lỗi vậy? Một số màn hay gặp issue: Đăng nhập/OTP, Trang chủ MiniApp, Thanh toán/Checkout, Quản lý đơn hàng, Cài đặt tài khoản. Hoặc màn khác thì nói cụ thể giúp mình.

Thiếu **dev phụ trách**:
> Assign cho dev nào? (nếu chưa biết, có thể nói loại lỗi/module để mình gợi ý dev phù hợp, hoặc để "chưa rõ - cần PM assign sau")

Thiếu **bước xử lý**:
> Mô tả giúp các bước để gặp lỗi này không? (vd: 1. Mở màn hình X → 2. Bấm nút Y → 3. Lỗi Z xuất hiện). Nếu chưa rõ steps, có thể mô tả hiện tượng lỗi thay thế.

Thiếu **ảnh chụp màn hình lỗi**:
> Gửi giúp ảnh chụp màn hình lúc lỗi xảy ra nhé - cái này bắt buộc để tạo ticket, dev cần hình mới debug được.
