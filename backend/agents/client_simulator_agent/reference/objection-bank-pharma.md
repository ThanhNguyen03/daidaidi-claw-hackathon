---
name: adtimabox-objection-bank-pharma
description: >
  Pharma client objections by bucket. Seeds the client-simulator's questions and weak-point flags.
  Each entry = trigger, client phrasing, what it's really testing, severity, strong response direction
  (with "Do NOT promise" guardrails for legal-sensitive items), and likely persona.
  Pharma set — FMCG objections tracked separately.
---

# Objection Bank — Pharma

Severity: `deal-killer` = không trả lời được thì mất deal · `major` · `minor`.
⚠️ = vùng pháp lý/kỹ thuật nhạy cảm — simulator phải ép, nhưng hướng trả lời KHÔNG được hứa bừa.

## PROOF-CLAIM RULE (simulator tự bắt lỗi)
- Adtima CHỈ được claim là proof của mình: các case CS-01…CS-11 trong `adtimabox-case-studies`.
- MerapLion, FPT Long Châu, và mọi case từ research = **tiền lệ ngành/Zalo**, KHÔNG phải Adtima.
- Nếu proposal trình bày tiền lệ ngành như kết quả Adtima → simulator flag OBJ-P11 (deal-killer credibility).

---

```
OBJECTION: OBJ-P01
Bucket: adoption
Trigger: Đề xuất nhà thuốc tự thao tác đặt hàng trên Mini App
Client says: "Chủ nhà thuốc của tôi lớn tuổi, ngại công nghệ. Làm sao ép họ tự đặt hàng trên app?"
Really testing: giải pháp có thật sự chạy được với end-user thật, hay chỉ đẹp trên slide
Severity: deal-killer
Strong response direction: nhấn no-install — quét QR tại quầy là vào Mini App ngay (rào cản "ngại cài đặt"
  được phá bỏ); MR onboard hộ lần đầu; incentive cho nhà thuốc; đề xuất PILOT để chứng minh trước khi scale.
  Tiền lệ thị trường (KHÔNG phải case Adtima): MerapLion +48% đơn online / +40% kết nối — chỉ dùng để chứng minh
  "Mini App không-cài-đặt giải được rào cản tuổi tác trong ngành Dược". Khi pitch phải nói rõ là tiền lệ ngành/Zalo,
  KHÔNG được trình bày như kết quả Adtima làm ra.
  Proof THẬT của Adtima (được phép claim): CS-04 (HCP CRM).
Likely persona: P-01
```

```
OBJECTION: OBJ-P02 ⚠️
Bucket: compliance / OA ban risk
Trigger: Chiến dịch nhắc dùng thuốc / khảo sát bác sĩ / nội dung y tế trên OA-Mini App
Client says: "Zalo kiểm duyệt nội dung y tế rất gắt. Làm sao đảm bảo OA của tôi không bị khóa hay gắn cờ?"
Really testing: ai chịu rủi ro nếu OA bị khóa giữa chiến dịch
Severity: deal-killer
Strong response direction: nội dung thuốc/TPCN cần Giấy xác nhận nội dung quảng cáo + công bố hợp quy —
  đây là trách nhiệm brand (khớp stakeholder role: brand = data/compliance owner). Adtima tư vấn chính sách Zalo,
  dùng template ZNS đã duyệt, tách nội dung thương mại vs thông tin. 
  >> Do NOT promise: KHÔNG hứa "OA chắc chắn không bị khóa". Chỉ cam kết quy trình giảm rủi ro + tư vấn.
Likely persona: P-02
```

```
OBJECTION: OBJ-P03 ⚠️
Bucket: data ownership / liability
Trigger: Data bệnh nhân + lịch sử toa thuốc nằm trên cloud Zalo
Client says: "Data của tôi mã hóa thế nào? Nếu rò rỉ từ máy chủ Zalo, AI chịu trách nhiệm pháp lý?"
Really testing: trách nhiệm pháp lý khi sự cố + tuân thủ Nghị định 13/2023
Severity: deal-killer (veto)
Strong response direction: AdtimaBox — ISO 27001, dữ liệu lưu tại VN, align Nghị định 13; brand = data owner.
  Phân định trách nhiệm pháp lý phải nằm trong HỢP ĐỒNG + pháp chế hai bên.
  >> Do NOT promise: KHÔNG tự nhận trách nhiệm thay Zalo, KHÔNG cam kết "không bao giờ rò rỉ".
  Flag: chuyển sang legal/contract để chốt liability split.
Likely persona: P-03 / P-04
```

```
OBJECTION: OBJ-P04 ⚠️
Bucket: integration feasibility
Trigger: Yêu cầu đồng bộ real-time với SAP ERP / Salesforce CRM
Client says: "Mini App của anh sync real-time với SAP/Salesforce của tôi được không? Volume lớn thì sao?"
Really testing: tính khả thi kỹ thuật thật, không phải lời hứa
Severity: major
Strong response direction: AdtimaBox có API + add-on integration (inbound/outbound 25–50M). Nhưng real-time
  ở volume lớn = RED FLAG theo integration skill — phải confirm tech lead về throughput.
  >> Do NOT promise: KHÔNG khẳng định "real-time được" tại bàn. Trả lời: "pattern khả thi, cần tech confirm về volume".
Likely persona: P-03
```

```
OBJECTION: OBJ-P05 ⚠️
Bucket: anti-bribery / medical ethics
Trigger: Đề xuất loyalty tích điểm đổi quà cho bác sĩ dự CME
Client says: "MNC không được tài trợ vật chất cho HCP. Tích điểm đổi quà cho bác sĩ — chứng minh không vi phạm anti-bribery thế nào?"
Really testing: giải pháp có đẩy khách vào rủi ro pháp lý hình sự không
Severity: deal-killer (veto)
Strong response direction: với HCP/ETC, KHÔNG đề xuất quà vật chất đổi điểm. Tái cấu trúc thành phi vật chất:
  chứng chỉ CME tự động, truy cập nội dung khoa học, theo dõi tham dự — không phải "gift". Quyết định cuối thuộc
  pháp chế của brand.
  >> Do NOT propose: loyalty quà tặng cho bác sĩ như với consumer. Đây là landmine — phải để legal brand sign-off.
Likely persona: P-04
```

```
OBJECTION: OBJ-P06
Bucket: cost vs free channel
Trigger: So sánh chi phí Mini App + ZNS với nhóm Viber/Zalo chat miễn phí
Client says: "Sao phải trả tiền Mini App + từng tin ZNS, trong khi nhóm Viber/Zalo chat miễn phí cũng nhận đơn?"
Really testing: giá trị cốt lõi vượt trên kênh free ở đâu
Severity: deal-killer
Strong response direction: chat free = không có owned data, không segment, không automation, không report,
  không scale nổi hàng nghìn nhà thuốc. AdtimaBox = data sở hữu + tự động hóa + dashboard + loyalty.
  Quy ra chi phí MR tiết kiệm được. Market evidence (KHÔNG phải case Adtima): MerapLion scale 58 tỉnh — dùng để
  chứng minh chat free không scale nổi, phải nói rõ là tiền lệ ngành chứ không claim là Adtima làm.
Likely persona: P-05
```

```
OBJECTION: OBJ-P07
Bucket: hidden cost
Trigger: Lo phí phát sinh sau triển khai
Client says: "Phí duy trì, phí đổi tính năng, ZNS vượt hạn mức — tổng thực sự là bao nhiêu?"
Really testing: pricing có minh bạch không
Severity: major
Strong response direction: bóc tách trước: CShub recurring + Maintenance 5M/tháng + ZNS theo tin + add-on rõ ràng.
  Map chi phí 12 tháng trên bàn, không để surprise. Tham chiếu product-advisor.
Likely persona: P-05
```

```
OBJECTION: OBJ-P08
Bucket: internal adoption / change mgmt
Trigger: Số hóa đặt hàng B2B đụng vai trò MR
Client says: "MR của tôi sẽ phản kháng vì sợ mất việc / bị kiểm soát. Sao thuyết phục họ dùng?"
Really testing: giải pháp có gây xung đột nội bộ không
Severity: major
Strong response direction: định vị Mini App là CÔNG CỤ tăng năng suất MR (MR vẫn onboard, vẫn được ghi nhận
  qua referral/assisted order), không thay thế MR. Kèm change management + KPI mới cho MR.
Likely persona: P-01
```

```
OBJECTION: OBJ-P09 ⚠️
Bucket: HCP data / consent
Trigger: Xây HCP database + thu thập dữ liệu bác sĩ/bệnh nhân
Client says: "Quy trình xin consent và xác minh danh tính bác sĩ (ETC) chuẩn tới đâu?"
Really testing: tuân thủ Nghị định 13 + xác thực HCP
Severity: major
Strong response direction: consent form trong onboarding (opt-in, T&C), align Nghị định 13. Xác minh danh tính
  HCP cho kênh ETC = cần thiết kế quy trình riêng, có thể cần verify thủ công.
  >> Flag: phần ETC identity verification cần tech + legal confirm, không có sẵn out-of-box.
Likely persona: P-02 / P-04
```

```
OBJECTION: OBJ-P10
Bucket: ROI / payback
Trigger: Đòi cam kết payback period rõ ràng
Client says: "Payback bao lâu? Dựa trên cơ sở nào?"
Really testing: con số ROI có thực tế hay vẽ
Severity: major
Strong response direction: model từ chi phí MR giảm + tần suất đặt hàng tăng + active rate. Tham chiếu CS-04 (HCP),
  CS-08 (nutrition/pharmacy full-funnel). 
  >> Do NOT promise: payback phụ thuộc adoption — nói thẳng giả định, đừng cam kết cứng con số.
Likely persona: P-05
```

```
OBJECTION: OBJ-P11 ⚠️
Bucket: credibility / proof-claim
Trigger: Proposal trình bày tiền lệ ngành (MerapLion, FPT Long Châu...) như kết quả Adtima làm ra
Client says: "Case MerapLion này là Adtima triển khai à? Cho tôi xem hợp đồng / số liệu các anh đo được."
Really testing: Adtima có đang phóng đại năng lực bằng case của bên khác không
Severity: deal-killer (credibility — đặc biệt nguy hiểm với P-04 Legal)
Strong response direction: phân định rõ ngay từ slide — case Adtima (CS-01…CS-11) vs tiền lệ ngành/Zalo.
  Tiền lệ ngành chỉ dùng để chứng minh "mô hình này chạy được ở VN", không phải "Adtima làm ra kết quả này".
  >> Do NOT claim: bất kỳ case nào ngoài CS-01…CS-11 là của Adtima. Nếu lỡ claim, P-04 phát hiện → mất niềm tin toàn bộ deck.
Likely persona: P-04 / P-03
```

```
OBJECTION: OBJ-P12 ⚠️
Bucket: compliance / Luật Dược 2024
Trigger: Mini App có chức năng bán/hiển thị thuốc, hoặc đặt hàng
Client says: "Theo Luật Dược 2024, OTC bán online được nhưng Rx phải tư vấn 1:1 + xác thực đơn điện tử,
              thuốc kiểm soát đặc biệt thì cấm. Mini App của anh phân biệt Rx/OTC và xác thực đơn thế nào?"
Really testing: giải pháp có đẩy khách vi phạm Luật Dược không
Severity: deal-killer
Strong response direction: phân luồng theo loại thuốc — OTC: đặt hàng/thanh toán; Rx: chỉ hiển thị thông tin
              tham khảo + tư vấn 1:1 (Video Call/Chat) + xác thực đơn điện tử qua hệ thống quốc gia; thuốc
              kiểm soát đặc biệt: chỉ dẫn đến cơ sở vật lý. TPCN: marketing/loyalty thoải mái hơn.
  >> Verify with legal: chi tiết Luật Dược 2024 (hiệu lực 7/2025) phải để pháp chế brand xác nhận, không tự diễn giải luật.
Likely persona: P-04 / P-02
```

```
OBJECTION: OBJ-P13
Bucket: data asset risk (MR turnover)
Trigger: MR đang chăm HCP qua Zalo cá nhân
Client says: "Data HCP đang nằm trong Zalo cá nhân của trình dược viên. MR nghỉ là mất hết hoặc bị đối thủ
              khai thác. Giải pháp của anh giữ tài sản data này lại cho công ty kiểu gì?"
Really testing: ai sở hữu mối quan hệ HCP — công ty hay cá nhân MR
Severity: major (selling point mạnh — Adtima CÓ quản lý MR nên xử được trực diện)
Strong response direction: AdtimaBox CÓ module quản lý MR (xác nhận từ team) → data HCP tập trung về platform
              (brand = owner), MR nghỉ thì chuyển giao quyền quản lý mượt mà, lịch sử tương tác không mất.
              Cộng thêm loyalty/CRM/Auto EDA mà giải pháp thuần "quản lý Zalo MR" không có.
  >> Cần confirm với product-advisor: module quản lý MR nằm ở package/add-on nào + scope cụ thể (để fact-check khớp).
Likely persona: P-01 / P-03
```

```
OBJECTION: OBJ-P14 ⚠️
Bucket: integration / HIS fragmentation
Trigger: Yêu cầu kết nối với HIS bệnh viện / EMR
Client says: "13.000 cơ sở y tế dùng HIS khác nhau. Mini App tích hợp với hệ thống bệnh viện của tôi kiểu gì?"
Really testing: tính khả thi tích hợp ở môi trường y tế phân mảnh
Severity: major
Strong response direction: giai đoạn đầu KHÔNG ép tích hợp sâu HIS — dùng mô hình "Lite-EMR/độc lập" để bác sĩ
              tự quản nhóm bệnh nhân; tích hợp HIS sâu là roadmap sau, cần tech confirm theo từng HIS.
  >> Do NOT promise: tích hợp HIS phổ quát. Khớp integration skill — custom platform = confirm feasibility với tech lead.
Likely persona: P-03
```

```
OBJECTION: OBJ-P15
Bucket: competitor (pharma-specific)
Trigger: Đề xuất HCP Mini App / CME / Webinar trên Zalo
Client says: "AddyCare, Z-Waka, CNV đã làm Mini App HCP và CME trên Zalo rồi. AdtimaBox khác gì mà tôi chọn anh?"
Really testing: differentiator thật vs các player chuyên Dược trên Zalo
Severity: deal-killer
Strong response direction: [CẦN INPUT — xem file competitive-defense-pharma]. Anchor tạm: native Zalo + Auto EDA
              với Zalo DMP + ISO 27001/data VN + enterprise-grade. KHÔNG bịa điểm yếu đối thủ khi chưa có intel.
Likely persona: P-05 / P-02
```

```
OBJECTION: OBJ-P16
Bucket: compliance / OA verification
Trigger: Lập Zalo OA dược được xác thực
Client says: "OA dược muốn xác thực phải có giấy phép kinh doanh dược + hoạt động y tế. Ai lo phần giấy tờ này?"
Really testing: phân định trách nhiệm pháp lý/giấy phép
Severity: minor → major (tùy MNC)
Strong response direction: giấy phép là của brand (brand = compliance owner); Adtima hỗ trợ quy trình xác thực OA.
Likely persona: P-04
```

---

## CÒN THIẾU (cần bạn cung cấp để bản tiếp theo sắc hơn)
- [ ] **Objection thật ngoài các câu seed** — từ pitch Dược đã chạy (nguyên văn càng tốt).
- [ ] **Win/loss notes**: deal Dược nào mất vì objection nào?
- [ ] **Bộ objection FMCG** — file này chỉ Pharma.
- [ ] **Intel đối thủ Dược** (AddyCare, Z-Waka, CNV, ViHAT/Vpage) để hoàn thiện OBJ-P15 → xem file competitive-defense-pharma.

> Đã xác nhận: MerapLion / FPT Long Châu KHÔNG phải case Adtima → giữ ở dạng "market evidence", đã khóa bằng PROOF-CLAIM RULE + OBJ-P11.
> Bổ sung từ research HCP: OBJ-P12 (Luật Dược 2024), OBJ-P13 (data MR), OBJ-P14 (HIS), OBJ-P15 (đối thủ Dược), OBJ-P16 (OA verification).
