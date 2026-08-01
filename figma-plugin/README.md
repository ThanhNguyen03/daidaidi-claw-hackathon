# AdtimaBox Wireframe — Figma plugin

Vẽ wireframe mobile low-fidelity vào file Figma của bạn từ một mã job (8 ký tự) do
AdtimaBox Sales Agent cấp.

Không cần build, không cần npm — plugin nạp trực tiếp từ `manifest.json`.

## Cài đặt (chỉ làm một lần)

1. Mở **Figma desktop app** (bản web không import được plugin dev).
2. Menu **Plugins → Development → Import plugin from manifest…**
3. Chọn file `figma-plugin/manifest.json` trong repo này.
4. Plugin xuất hiện ở **Plugins → Development → AdtimaBox Wireframe**.

## Sử dụng

1. Mở file Figma (hoặc trang) muốn vẽ vào.
2. Chạy **Plugins → Development → AdtimaBox Wireframe**.
3. **Địa chỉ API**: mặc định `https://zah-28.123c.vn/api`. Nếu chạy backend local thì
   nhập `http://localhost:8000`. Plugin ghi nhớ giá trị này (`figma.clientStorage`),
   chỉ cần nhập một lần.
4. **Mã job**: dán mã 8 ký tự, ví dụ `A1B2C3D4`. Mã có hiệu lực 24 giờ; hết hạn thì
   xin lại mã mới trong AdtimaBox.
5. Bấm **Vẽ Wireframe**.

Plugin gọi `GET {API}/figma/job/{code}`, rồi vẽ:

- một frame `375x812` cho mỗi màn hình, xếp ngang cách nhau 60px;
- nhãn tên màn hình + ghi chú phía trên mỗi frame;
- toàn bộ nhóm nằm trong một **section** tên `AdtimaBox — {brand} — {product}`, đặt
  bên phải phần nội dung đang có nên không đè lên bài đang làm;
- kết thúc sẽ tự zoom vào section vừa vẽ và báo số màn hình đã vẽ.

## Ghi chú

- Tên miền backend phải có trong `networkAccess.allowedDomains` của `manifest.json`.
  Nếu bạn trỏ sang một host khác (staging, IP nội bộ…), thêm host đó vào danh sách rồi
  import lại plugin, nếu không Figma sẽ chặn request.
- Sau khi sửa `code.js` / `ui.html`, chạy lại plugin là đủ (không cần import lại).
  Chỉ khi sửa `manifest.json` mới phải import lại.
- Kiểu block chưa hỗ trợ sẽ được vẽ thành ô nét đứt có ghi tên kiểu, không làm hỏng
  cả bản vẽ. Màn hình không có block nào vẫn ra một frame điện thoại rỗng.
