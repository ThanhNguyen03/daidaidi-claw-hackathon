---
name: adtimabox-objection-bank-fmcg
description: >
  FMCG client objections, split Branch A (B2C consumer, FA-*) and Branch B (B2B internal staff, FB-*),
  plus shared. Seeds the client-simulator's questions and weak-point flags. Each entry = trigger,
  client phrasing, what it's really testing, severity, strong response direction, likely persona.
---

# Objection Bank — FMCG

Severity: `deal-killer` · `major` · `minor`.

## PROOF-CLAIM RULE (FMCG — khác Pharma!)
Các case sau LÀ của Adtima → **ĐƯỢC claim thẳng kèm số**:

**AdtimaBox (CRM / Loyalty / Mini App):**
- **Red Bull** AI Video Tet 2026: #1 YMI Tet 2026, 175K+ AI video, 47K+ user, 107K+ social conversation.
- **Coca-Cola**: loyalty point-based trên Zalo Mini App, unique code on-pack, leaderboard, retarget theo nhóm.
- **Rockstar**: UTC "Quét ngay – Cơ hội túng liền tay", buy → scan → instant reward.
- **TH Beverage**: O2O sampling (lucky box online → redeem offline).
- **Nestlé – Milo** (UTC QR on-pack): 27% pack growth per trip, 70% scans buổi sáng, 50% user duy trì thói quen tập thể dục.
- **VinFast** (Zalo Lead Form): Car — 57K+ clicks, ~1,250 leads; E-Motor — 23K+ clicks, ~450 leads.
- **Surf (Unilever)** Game "Tâm Đầu Ý Hợp" trên Zalo: 3M users reached, 19K arrivals, 26K play-turns.

**Media / Content / Music (non-CShub):**
- **Surf (Unilever)** Zalo Sticker "Tết Lên Hương": 383K+ turns download (1.5x vs others), 856K+ turns use (2x vs others) trong 1 tháng.
- **Surf (Unilever)** Music Marketing Zing MP3 (branded song): 56M impressions/ngày, 7M reach/ngày, 200K listens (124% KPI).
- **Lazada** Audio Ads + Audio Plus Zing MP3: 3.4M impressions, 103K clicks, CTR 1.6x benchmark.
- **Nutifood** Content ZNews + MOH: 90 articles/videos, 718K views.
- **UOB** Z-Pro content + ZNews: 16 multi-format articles, 198K views.

**Case-study-advisor:** CS-01, CS-02, CS-07, CS-08, CS-09, CS-10, CS-11.

→ Ở FMCG, simulator KHÔNG flag proof-claim như Pharma — đây là proof thật, AE nên dùng tự tin.
(Vẫn cấm bịa case không có thật hoặc gán số sai cho sai brand.)

---

## NHÁNH A — B2C CONSUMER

```
OBJECTION: OBJ-FA01
Bucket: ROI vs media
Trigger: Đề xuất Brand Hub/loyalty trong khi brand quen dồn tiền vào ATL
Client says: "Cùng ngân sách này tôi mua TVC/TikTok/Meta để phủ awareness. Tại sao lại làm Mini App?"
Really testing: Brand Hub bổ trợ hay cạnh tranh ngân sách media
Severity: deal-killer
Strong response direction: định vị Brand Hub là tầng "Reach → Relationship" — biến traffic ẩn danh thành
  first-party data sở hữu, hạ CAC dài hạn, tăng CLV. Media vẫn cần để acquire; Hub giữ & tái dùng.
  Proof claim được: Red Bull Tet 2026 (#1 YMI, 47K user, 107K social conversation).
Likely persona: FA-P01 / FA-P05
```

```
OBJECTION: OBJ-FA02
Bucket: MT data block
Trigger: Mục tiêu thu data consumer ở kênh Modern Trade
Client says: "MT không trả data consumer cho tôi. Brand Hub bắt được data mua hàng kiểu gì?"
Really testing: cơ chế thu data khi không sở hữu kênh bán
Severity: major
Strong response direction: bridge offline→online — Scan Bill (OCR), UTC on-pack, voucher redeem tại store.
  Proof claim: CS-02 (condiment MT scan bill), TH Beverage O2O, Rockstar UTC.
Likely persona: FA-P03
```

```
OBJECTION: OBJ-FA03
Bucket: fraud / gaming
Trigger: Cơ chế Scan Bill / UTC tích điểm
Client says: "Làm sao chống bill giả, scan trùng, hoặc user gian lận code để cày điểm?"
Really testing: tính toàn vẹn của earn scheme
Severity: major
Strong response direction: AI OCR phát hiện signal trên bill; unique code dùng-một-lần + prefix-format;
  khóa account khi sai nhiều lần (khớp flow UTC/Scan Bill trong solution-designer).
Likely persona: FA-P03 / FA-P02
```

```
OBJECTION: OBJ-FA04
Bucket: reward economics
Trigger: Earn & Burn scheme với quà/voucher
Client says: "Reward ai trả? Cost mỗi lượt redeem bao nhiêu, có ăn vào margin sản phẩm không?"
Really testing: chi phí thực của loyalty scheme
Severity: deal-killer
Strong response direction: reward budget do brand set; thiết kế burn theo tier để kiểm soát cost/redeem;
  ưu tiên reward gắn sản phẩm (sampling, combo) để vừa thưởng vừa đẩy sales.
  >> Cần input: chuẩn margin/ngân sách reward của brand để model cụ thể.
Likely persona: FA-P05 / FA-P03
```

```
OBJECTION: OBJ-FA05
Bucket: campaign vs always-on
Trigger: Đề xuất CShub (phí định kỳ) cho brand quen tư duy campaign
Client says: "Bọn tôi nghĩ theo campaign từng đợt, không quen trả phí platform định kỳ. Sao phải subscription?"
Really testing: giá trị của always-on vs burst campaign
Severity: major
Strong response direction: campaign instant cho burst; CShub cho giá trị tích lũy — data & member không mất
  sau campaign, campaign sau không phải build lại từ đầu (chính là pain "campaign xong data biến mất").
Likely persona: FA-P01
```

```
OBJECTION: OBJ-FA06
Bucket: cannibalize existing loyalty
Trigger: Brand đã có app loyalty/CRM riêng
Client says: "Bọn tôi đã có app loyalty riêng rồi. Đẩy thêm loyalty trên Zalo có chạy song song hai chương trình không?"
Really testing: tránh hai loyalty xung đột
Severity: deal-killer
Strong response direction: KHÔNG chạy hai loyalty song song mù — định rõ master record; Zalo Brand Hub
  acquire tệp không-cài-app (đa số user VN) + sync/feed về CRM brand (add-on integration). 
  >> Khớp integration skill: platform có loyalty → decide replace or sync, never two without clear logic.
Likely persona: FA-P04
```

```
OBJECTION: OBJ-FA07
Bucket: engagement sustainability
Trigger: Gamification/minigame thu hút theo đợt
Client says: "Engagement cao lúc có quà, hết campaign là chết. Giữ user quay lại kiểu gì?"
Really testing: cơ chế retention sau burst
Severity: major
Strong response direction: leaderboard + daily login + referral + ZNS cá nhân hóa theo hành vi; earn/burn
  liên tục thay vì one-shot. Proof: Coca-Cola loyalty leaderboard duy trì tương tác dài hạn.
Likely persona: FA-P02
```

```
OBJECTION: OBJ-FA08
Bucket: attribution
Trigger: Tuyên bố Brand Hub thúc đẩy sales
Client says: "Làm sao chứng minh Mini App tạo ra đơn hàng, chứ không phải promo nào cũng bán được?"
Really testing: đo lường nhân quả, không phải vanity metric
Severity: major
Strong response direction: track UTC/scan bill gắn purchase thật; so sánh segment tham gia vs không;
  Auto EDA với Zalo DMP. >> Thành thật: attribution tuyệt đối khó, nói rõ phương pháp đo, đừng over-claim.
Likely persona: FA-P02 / FA-P04
```

```
OBJECTION: OBJ-FA09
Bucket: data ownership / PDPL
Trigger: Thu first-party data consumer
Client says: "Data consumer thu trên Zalo là của brand hay Adtima? Tuân thủ PDPL/Nghị định 13 thế nào?"
Really testing: ownership + tuân thủ (nhẹ hơn Pharma nhưng vẫn có)
Severity: major
Strong response direction: brand = data owner; consent trong onboarding; ISO 27001, data tại VN; export add-on.
Likely persona: FA-P04
```

```
OBJECTION: OBJ-FA10
Bucket: cost / competitor
Trigger: So giá với đối thủ FMCG
Client says: "CNV/Pango/Mmenu báo rẻ hơn / nhanh hơn. AdtimaBox khác gì?"
Really testing: differentiator thật
Severity: deal-killer
Strong response direction: anchor — native Zalo + Auto EDA với Zalo DMP (đối thủ không có) + ISO 27001/data VN.
  >> CẦN INPUT: intel CNV/Pango/Mmenu/Digibird (mạnh/rẻ ở đâu) — chưa có thì KHÔNG bịa điểm yếu đối thủ.
Likely persona: FA-P05
```

```
OBJECTION: OBJ-FA11
Bucket: generic packaged deck
Trigger: Pitch bằng gói packaged "Ông Lớn" thay vì custom cho brand
Client says: "Slide này tôi thấy chung chung — đâu là insight riêng cho brand TÔI, không phải Red Bull hay Coca?"
Really testing: AE có hiểu brand cụ thể hay chỉ bê gói chung
Severity: deal-killer
Strong response direction: packaged deck chỉ để giáo dục về Brand Hub; trước pitch thật phải layer insight
  riêng của brand (pain, category, kênh). Khớp tư duy packaged vs custom của solution-designer.
Likely persona: FA-P01 / FA-P02
```

---

## NHÁNH B — B2B INTERNAL STAFF (Perfetti FLEX type)

```
OBJECTION: OBJ-FB01
Bucket: rep adoption
Trigger: Hub học tập + gamification cho sale rep
Client says: "Sale chạy ngoài thị trường cả ngày, lấy đâu thời gian vào app? Adoption thật bao nhiêu %?"
Really testing: giải pháp có chạy với hành vi field force không
Severity: deal-killer
Strong response direction: no-install (Zalo Mini App), học micro/chơi ngắn, leaderboard + thưởng tạo động lực,
  onboarding qua QR tại văn phòng/POSM; đề xuất pilot 1 vùng đo adoption trước scale.
  Proof: Perfetti FLEX (learning + engagement hub cho sales staff).
Likely persona: FB-P01 / FB-P04
```

```
OBJECTION: OBJ-FB02
Bucket: ownership / whose budget
Trigger: Hub vừa đào tạo vừa engagement
Client says: "Đây là việc của Marketing, Sales hay HR? Ngân sách của ai?"
Really testing: tránh xung đột nội bộ về sở hữu dự án
Severity: major
Strong response direction: làm rõ sponsor & owner ngay từ đầu (thường Commercial/Sales là sponsor, HR co-own
  phần learning); định rõ RACI để tránh kẹt phê duyệt nội bộ.
Likely persona: FB-P03 / FB-P01
```

```
OBJECTION: OBJ-FB03
Bucket: staff incentive / policy
Trigger: Tích điểm đổi quà cho nhân viên
Client says: "Thưởng quà cho nhân viên qua app có vướng chính sách thưởng/thuế nội bộ không?"
Really testing: rủi ro chính sách nhân sự
Severity: major
Strong response direction: cấu trúc reward gắn ghi nhận/đào tạo; quy đổi quà cần HR/finance brand duyệt.
  >> Do NOT promise: không tự khẳng định không vướng thuế/policy — để HR/finance brand quyết.
Likely persona: FB-P03
```

```
OBJECTION: OBJ-FB04
Bucket: learning effectiveness
Trigger: Learning hub (play-to-learn)
Client says: "Làm sao biết nhân viên thực sự nắm kiến thức chứ không phải chơi game lấy điểm?"
Really testing: learning có tạo năng lực bán hàng thật không
Severity: major
Strong response direction: quiz/assessment gắn khóa học, phân nhóm theo trình độ (senior vs junior),
  đo completion + điểm assessment, không chỉ điểm chơi. Proof: Perfetti Learning Hub có quiz tích hợp.
Likely persona: FB-P02
```

```
OBJECTION: OBJ-FB05
Bucket: integration (LMS/HR)
Trigger: Brand đã có LMS / hệ thống HR
Client says: "Bọn tôi đã có LMS. Hub này tích hợp hay lại thêm một hệ thống rời?"
Really testing: tránh thêm silo
Severity: major
Strong response direction: định rõ ranh giới — Hub là lớp engagement no-install trên Zalo; tích hợp/feed
  dữ liệu hoàn thành về LMS là add-on, >> cần tech confirm theo từng hệ thống.
Likely persona: FB-P02
```

```
OBJECTION: OBJ-FB06
Bucket: content maintenance
Trigger: Learning hub cần nội dung cập nhật liên tục
Client says: "Sản phẩm đổi liên tục, ai cập nhật nội dung khóa học? Bọn tôi không có nguồn lực làm content."
Really testing: gánh vận hành nội dung sau bàn giao
Severity: major
Strong response direction: làm rõ ai sở hữu content ops (brand tự cập nhật qua dashboard, hoặc Adtima
  hỗ trợ gói content — có cost). Đừng để mơ hồ → khách sợ gánh nặng.
Likely persona: FB-P02
```

---

## SHARED (cả 2 nhánh)
- **Cost stacking**: CShub + campaign instant (UTC 80 / Scan Bill 80 / Lucky Draw 60) + VAT 8% + agency fee → tham chiếu cost-tripwires.
- **Hidden cost**: storage +100K (50M/năm), OCR scan bill 1.200đ/scan × volume mass FMCG (con số lớn — Finance sẽ soi).
- **Why Zalo / why Adtima**: anchor Auto EDA + Zalo DMP, native Zalo, ISO 27001/data VN, 100+ brand/210+ campaign.

---

## COMPETITIVE OBJECTIONS — CNV vs PANGO vs ADTIMABOX

> Activate khi client đề cập đối thủ cụ thể. Intel tổng hợp từ website thực tế (tháng 6/2026).
> ⚠️ Chỉ dùng các fact đã verify — KHÔNG bịa điểm yếu đối thủ.

```
OBJECTION: OBJ-COMP01
Bucket: Competitor — CNV pricing
Trigger: Client nhận báo giá CNV trước khi gặp Adtima
Client says: "CNV Mini App chỉ 10–30 triệu/năm, đủ tính năng. AdtimaBox đắt gấp 5–10 lần. Giải thích gì?"
Really testing: Value justification — brand có sẵn sàng trả premium cho enterprise solution không
Severity: deal-killer
Strong response direction:
  1. Segment khác nhau: CNV phục vụ 3,000+ SMEs với SaaS template. AdtimaBox cho MNC cần customization,
     governance, tích hợp media ecosystem.
  2. CNV không có Auto EDA với Zalo DMP — analytics từ 75M users chỉ AdtimaBox có.
  3. CNV không có media/content solution — brand cần Ads+CRM+Content cùng ecosystem phải dùng AdtimaBox.
  4. Enterprise compliance: ISO 27001, data VN — CNV chưa công bố tương đương.
  5. Reframe ROI: So sánh total cost (CNV tool + Zalo Ads riêng + analytics riêng) vs AdtimaBox integrated.
  Proof: Coca-Cola, Red Bull, Nestlé chọn AdtimaBox.
Likely persona: FA-P05 / FA-P01
```

```
OBJECTION: OBJ-COMP02
Bucket: Competitor — CNV deploy speed
Trigger: Timeline launch gấp, CNV chào nhanh hơn
Client says: "CNV triển khai trong 2 tuần. AdtimaBox mất bao lâu? Tôi cần launch trong tháng."
Really testing: Speed vs customization tradeoff
Severity: major
Strong response direction:
  1. Xác nhận timeline thực tế theo package (>> CẦN INPUT: lead time thực tế per package từ team).
  2. Timeline gấp → đề xuất bắt đầu với package nhỏ hơn (Base 1/2) rồi scale up.
  3. Hỏi lại: "Template CNV có match đúng use case của anh/chị không, hay vẫn cần custom?"
  4. Tradeoff rõ ràng: nhanh hơn = ít customization = phải adapt business process theo tool.
     AdtimaBox ngược lại: tool adapt theo business của brand.
Likely persona: FA-P01 / FA-P05
```

```
OBJECTION: OBJ-COMP03
Bucket: Competitor — PangoCDP AI/Data
Trigger: Client đã biết PangoCDP, dùng Nutifood/Unilever làm tham chiếu
Client says: "PangoCDP có AI, có Nutifood và Unilever, 65 segments, 55 auto flows. AdtimaBox chỉ là loyalty platform?"
Really testing: Data sophistication và full-platform capability của AdtimaBox
Severity: major
Strong response direction:
  1. AdtimaBox không chỉ là loyalty — là full Customer Engagement Platform trên Zalo.
  2. Key differentiator: Auto EDA với Zalo DMP — insight từ 75M Zalo users, Pango không có.
  3. Positioning khác: Pango = multi-channel CDP (breadth). AdtimaBox = Zalo-native depth + media.
     Nếu brand muốn maximize Zalo ecosystem → AdtimaBox. Nếu muốn unify tất cả kênh → Pango.
  4. Adtima cũng có Nutifood (ZNews Content, 718K views) và Unilever (Surf Sticker, Surf Music).
     Nutifood có thể dùng cả hai cùng lúc cho mục tiêu khác nhau.
  5. Hỏi lại: Brand muốn data từ tất cả kênh hay muốn go deep trên Zalo ecosystem?
  Proof: Red Bull Tet 2026 #1 YMI — targeting dựa trên Zalo DMP.
Likely persona: FA-P03 / FA-P05
```

```
OBJECTION: OBJ-COMP04
Bucket: Competitor — đang dùng competitor
Trigger: Brand đang dùng CNV hoặc PangoCDP
Client says: "Tôi đang dùng CNV/PangoCDP rồi. Switch sang AdtimaBox thêm cost và rủi ro migration."
Really testing: Switching cost vs incremental value
Severity: major
Strong response direction:
  1. Không cần switch toàn bộ — AdtimaBox có thể bổ sung phần thiếu:
     - Đang dùng CNV? → Thêm Zalo Ads + Content + Auto EDA mà CNV không có.
     - Đang dùng PangoCDP? → Thêm native Zalo depth + Zalo media ecosystem.
  2. Identify gap cụ thể trong current solution → pitch vào chỗ thiếu đó trước.
  3. Nếu muốn migrate hoàn toàn: phân tích switching cost vs long-term ROI cụ thể theo brand.
  >> CẦN INPUT: Có case migration từ CNV sang AdtimaBox không?
Likely persona: FA-P01 / FA-P03
```

---

## COMPETITIVE INTEL QUICK REFERENCE (cập nhật tháng 6/2026)

| Competitor | Pricing (2026) | Client base | Điểm mạnh | Gap vs AdtimaBox |
|-----------|----------------|-------------|-----------|-----------------|
| **CNV** | 10.8–30M/năm (Mini App); 20.4–28.8M/năm (Combo CDP) | 3,000+ SME | Rẻ, triển khai nhanh, SaaS | Không có Zalo DMP, không media, chưa ISO 27001 |
| **PangoCDP** | Contact (chưa public) | 170+ enterprise | AI CDP, Nutifood/Unilever, O2O data | Multi-channel không native Zalo, không media |
| **AdtimaBox** | 20–297M/package | 100+ MNC brands | Native Zalo + Auto EDA + Full-funnel | Giá cao hơn, lead time dài hơn |

---

## CÒN THIẾU (cần bạn cung cấp)
- [ ] **Objection thật** từ pitch FMCG đã chạy (cả 2 nhánh) + win/loss notes.
- [ ] **Lead time thực tế** per package (để handle OBJ-COMP02).
- [ ] **Migration case** từ CNV → AdtimaBox nếu có.
- [ ] **Pitch win/loss vs CNV và Pango**: thắng/thua vì lý do gì.
- [ ] **Chuẩn margin/ngân sách reward** của brand (cho OBJ-FA04).
- [ ] Nhánh B bán cho Sales/HR/Trade → chốt để gán sponsor đúng.
