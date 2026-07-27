# BRD - AdtimaBox Presale Agent

Tài liệu cho dev. Phạm vi: cách xây hệ thống.

Mọi địa chỉ file trong doc này thuộc **source code cũ** (`agents_instructions/` và `backend/`). Không lẫn với bộ skill dùng trong Claude project - đó là bộ khác, nội dung đã trôi khỏi nhau.

---

## 1. Vấn đề cần giải

Mọi deal đều kéo tech vào 3-4 lần. Nguyên nhân: sales nắm Layer 1, không có Layer 2.

| Layer | Nội dung | Sales |
|---|---|---|
| 1 - kinh doanh, marketing | CJM, chiến lược, mục tiêu | Nắm tốt |
| 2 - yêu cầu kỹ thuật | Loyalty cần data gì · CRM có API không · redemption verify thế nào | Không biết cách hỏi khách |

Không phải không biết câu trả lời, mà không biết **cách hỏi**. Hệ thống phải sinh ra câu hỏi, không chỉ sinh ra câu trả lời.

| Vòng lặp | Tốn | Cắt bằng |
|---|---|---|
| 01 - Hỏi dev/BA giải thích nghiệp vụ | 1-2 ngày | Bảng nghiệp vụ trong knowledge |
| 02 - Dev confirm + estimate feasibility | 2-5 ngày | Phán quyết khả thi |
| 03 - Báo giá chờ Tech Lead + BA | Không xác định | Bảng tra tính năng → gói → giá |

---

## 2. Nguyên nhân trong source code cũ

| Địa chỉ | Vấn đề |
|---|---|
| `backend/agents/sales_orchestrator_agent/agent.py:613` | Brief thiếu thông tin vẫn `return True`, comment `# still dispatch — questions are optional, not blocking` |
| `backend/validation/validator.py:20` | `MANDATORY_FIELDS = ["industry", "goal"]` - chỉ 2 trường |
| `backend/main.py:742` | `use_full_graph = False`, comment `# full LangGraph has issues with duplicate routes` |
| `backend/agents/graph.py:308` | Đường chạy thật là `SimpleAgentRunner` với group tuần tự G1 → G2 |
| `backend/tools/ingest.py` | RAG tách corpus theo từng thư mục agent, tài liệu lớn bị lặp |
| `backend/config/agents.yaml` | Một số agent không đăng ký đủ, rơi vào `StubAgent` |
| `agents_instructions/sales_orchestrator_agent/SKILL.md:36` | `Ask at most 3 questions per turn` |
| `agents_instructions/sales_orchestrator_agent/reference/sales-agent-master.md:19` | `Ask maximum 3 questions per turn` |
| `agents_instructions/requirement_elicitation_agent/reference/requirement-elicitor.md:31` | `Never ask more than 3 questions at a time` |
| `agents_instructions/requirement_elicitation_agent/reference/requirement-elicitor.md:298` | `Do not ask more than 3 questions at once` |

Điểm chung: **thứ bắt buộc lại được đặt ở nơi có thể bỏ qua.** Cổng là nhánh `if`. Giới hạn câu hỏi là câu trong prompt.

**Một chỗ tri thức đã đúng nhưng cần kiểm code có làm đúng không:** `agents_instructions/sales_orchestrator_agent/reference/data-masking.md` đã ghi rõ *"This skill must run BEFORE the Orchestrator — no downstream agent should ever see real client data"* và mapping table chỉ đi tới Export Tool, không vào pipeline. Thiết kế đúng. **Cần dev xác nhận code có thực thi đúng vậy không, hay masking đang là một agent mà router có thể không gọi.**

---

## 3. Nguyên tắc kiến trúc

**Cái gì không được phép skip thì không được là agent.**

| Thành phần | Vị trí | Nếu để làm agent |
|---|---|---|
| Che PII | Đầu vào, trước mọi thứ | Bỏ qua 1 lần là PII đã vào mô hình |
| Cổng kiểm tra | Sau khi trích thông tin | Đúng lỗi bản cũ |
| Soát đầu ra | Cuối cùng | Agent tự soát mình thì luôn thấy ổn |

**Một thay đổi so với `data-masking.md` hiện tại:** tài liệu đó đặt masking **sau** khi scoping validate brief. Bản này đặt masking **trước tất cả**, kể cả trước agent khai thác yêu cầu. Lý do: nếu masking chạy sau scoping thì chính agent scoping đã đọc PII thô rồi.

---

## 4. Kiến trúc

```
Sales gửi tin
   ↓
[A] CHE PII                  ← thành phần hệ thống, mọi lượt
   ↓
[B] PHÂN LOẠI Ý ĐỊNH
   ├─ tra cứu ────────────→ trả thẳng, KHÔNG qua cổng
   ├─ coaching ──────────→ client_simulator_agent → trả thẳng, KHÔNG qua cổng
   └─ brief
        ↓
   [C] TRÍCH THÔNG TIN + SUY LUẬN
        ↓
   [D] CỔNG KIỂM TRA        ← CODE THUẦN, không gọi mô hình, không bypass
        ├─ thiếu → requirement_elicitation_agent hỏi lại → về [C]
        ↓
   ★ CHỐT 1 - sales xác nhận cách hiểu brief
        ↓
   [E] ROUTER               ← mô hình chọn agent, không hardcode thứ tự
        ├─ market_strategy_agent
        ├─ compliance_policy_agent
        └─ product_solution_agent → phán quyết khả thi + gói + giá
        ↓
   ★ CHỐT 2 - sales duyệt hướng giải pháp
        ↓
   [F] proposal_renderer_agent
        ↓
   [G] SOÁT ĐẦU RA          ← thành phần hệ thống
        ↓
   Trả về + bảng tự đánh giá
```

`market_strategy_agent` và `compliance_policy_agent` không phụ thuộc nhau. Làm tuần tự trước cho dễ debug; chạy song song là tối ưu sau, không phải yêu cầu.

---

## 5. Lớp truy xuất tri thức

Bản cũ để mỗi agent tự nạp tri thức của mình, nên cùng một tài liệu bị nạp nhiều lần trong một request. Bản mới gom về một chỗ.

### Yêu cầu

| # | Yêu cầu | Cụ thể |
|---|---|---|
| 1 | Chỉ có **một hàm** đọc tri thức trong toàn hệ thống | Agent không tự mở file, không tự query. Gọi hàm này |
| 2 | Trong phạm vi **một request**, mỗi tài liệu chỉ được nạp **một lần** | Giữ danh sách tài liệu đã nạp cho request đó. Agent thứ hai xin lại cùng tài liệu thì trả về từ danh sách, không nạp lại |
| 3 | Nhận diện tài liệu trùng bằng **giá trị băm nội dung**, không bằng tên file | Cùng nội dung ở hai đường dẫn khác nhau vẫn tính là một |
| 4 | Có **hạn mức dung lượng** cho phần tri thức đưa vào mỗi lần gọi mô hình | Vượt hạn mức thì bỏ tài liệu có điểm liên quan thấp nhất, và **ghi log đã bỏ cái gì** |
| 5 | Tri thức là file tĩnh nên **cache trong bộ nhớ**, không đọc lại mỗi lượt | |
| 6 | Truy xuất thất bại thì **dừng bước đó** | Không cho mô hình tự trả lời từ kiến thức chung. Trả lỗi rõ: không có tri thức cho phần này |

### Về việc có cần vector DB không

Corpus hiện tại khoảng 250KB. Ở kích thước này, nạp file theo bảng tra là đủ và dễ debug hơn nhiều. Đề xuất bỏ vector DB, dùng bảng tra tĩnh: mỗi agent khai trước cần những file nào.

Nếu giữ vector DB thì yêu cầu 2, 3, 4 vẫn áp dụng nguyên.

---

## 6. Tối ưu ngữ cảnh và đầu ra sub-agent

Đây là yêu cầu kỹ thuật riêng vì bản cũ tràn ngữ cảnh và mô hình quên ràng buộc ở đầu hội thoại.

### Đầu ra mỗi sub-agent phải là JSON gọn

| # | Yêu cầu | Cụ thể |
|---|---|---|
| 1 | Chỉ chứa **field mà bước sau thật sự cần** | Khai trước danh sách field cho từng cặp bước. Field không ai dùng thì không sinh ra |
| 2 | **Không lặp lại đầu vào** trong đầu ra | Agent chiến lược không được trả lại toàn bộ brief. Bước sau đã có brief rồi |
| 3 | **Không kèm văn xuôi diễn giải** trong JSON trung gian | Chỉ dữ liệu. Văn xuôi chỉ xuất hiện ở bước cuối, khi ghép proposal |
| 4 | Field dài chỉ ở nơi nó **là sản phẩm chính** | Ví dụ screen spec thuộc agent giải pháp. Các agent khác không nhắc lại |
| 5 | Có **hạn mức dung lượng cho đầu ra từng agent** | Vượt thì agent phải rút gọn, không phải để hệ thống cắt |
| 6 | Danh sách và bảng dùng **mã ngắn thay vì câu** | Ví dụ trạng thái khả thi dùng mã, không dùng cả câu mô tả |

### Truyền gì giữa các bước

| # | Yêu cầu |
|---|---|
| 7 | **Không truyền toàn bộ lịch sử hội thoại** cho từng agent. Truyền bản ghi yêu cầu có cấu trúc |
| 8 | Mỗi agent chỉ nhận **những field nó đã khai là cần**, không nhận cả object |
| 9 | Lịch sử hội thoại thô chỉ dùng ở bước trích thông tin và bước hỏi lại |
| 10 | Tri thức và bản ghi yêu cầu đưa vào prompt theo **thứ tự ổn định**, để cache prompt có hiệu lực |

### Đo và giám sát

| # | Yêu cầu |
|---|---|
| 11 | Log dung lượng prompt và dung lượng đầu ra của **từng lần gọi mô hình** |
| 12 | Có ngưỡng cảnh báo. Vượt thì báo, đừng để phát hiện lúc mô hình bắt đầu quên ràng buộc |

---

## 7. Cấu trúc thư mục

Giữ nguyên tên thư mục hiện có. Nội dung viết tiếng Việt.

```
agents_instructions/
├── sales_orchestrator_agent/
│   ├── SKILL.md
│   └── reference/
│       ├── orchestrator.md
│       ├── sales-agent-master.md
│       ├── data-masking.md
│       └── feedback-adjustments.md
├── requirement_elicitation_agent/
│   ├── SKILL.md
│   └── reference/requirement-elicitor.md
├── market_strategy_agent/
│   ├── SKILL.md
│   └── reference/  (strategy-consultant · case-studies)
├── product_solution_agent/
│   ├── SKILL.md
│   └── reference/  (product-advisor · solution-designer · domain-knowledge
│                    · miniapp-specialist · integration-advisor
│                    · platform-haravan · platform-kiotviet)
├── compliance_policy_agent/
│   ├── SKILL.md
│   └── reference/  (compliance-checking · vn-data-privacy
│                    · vn-advertising-law-pharma · zalo-oa-policy
│                    · zalo-ads-policy · zalo-miniapp-policy)
├── client_simulator_agent/
│   ├── SKILL.md
│   └── reference/  (objection-bank-fmcg · objection-bank-pharma
│                    · competitive-defense-pharma · buyer-personas-fmcg)
├── proposal_renderer_agent/          ← THÊM MỚI
│   ├── SKILL.md
│   └── reference/  (concept · render)
└── design/
    └── prompt.md                      ← ngoài phạm vi bản này
```

### Thay đổi so với hiện tại

| # | Việc |
|---|---|
| 1 | Thêm `proposal_renderer_agent`, nội dung lấy từ `A10_proposal_renderer_agent`. Chỉ có `SKILL.md` + `reference/`, không có `prompt.md` |
| 2 | Bỏ `proposal-assembler.md` khỏi `sales_orchestrator_agent/reference/` - chuyển sang agent mới |
| 3 | Xoá 4 dòng giới hạn 3 câu hỏi ở các địa chỉ liệt kê tại §2 |
| 4 | `data-masking.md` giữ nguyên chỗ, giữ vai trò tài liệu đặc tả. Nhưng code phải gọi nó như thành phần hệ thống, không phải như agent trong danh sách router chọn |
| 5 | `domain-knowledge.md` chỉ tồn tại 1 bản, mọi agent cần thì gọi qua lớp truy xuất §5 |
| 6 | Đưa điều kiện tiên quyết từ thân skill lên phần mô tả skill, xem §9 |
| 7 | `design/` để nguyên, không sửa |

---

## 8. Cổng kiểm tra

Cổng là **code**. Mô hình trích thông tin, code phán đủ hay chưa. Để mô hình tự đánh giá là mở lại đúng cái cửa vừa đóng.

### Ba trạng thái, không phải boolean

| Trạng thái | Khi nào | Hệ thống làm gì |
|---|---|---|
| `CHAN_HOI_LAI` | Thiếu trường bắt buộc, sales chưa yêu cầu bỏ qua | Chỉ gọi agent hỏi lại. Không gọi agent chuyên môn |
| `CHAY_CO_PHONG_DOAN` | Sales yêu cầu bỏ qua, hoặc chỉ thiếu trường nhóm nên-có | Chạy, dán nhãn, liệt kê mục đang đoán |
| `CHAY_DAY_DU` | Đủ trường bắt buộc | Chạy bình thường |

### Ràng buộc

| # | Ràng buộc |
|---|---|
| 1 | Không có tham số, cờ cấu hình, hay biến môi trường nào bỏ qua cổng |
| 2 | Quyền duy nhất là sales nói rõ "cứ làm đi". Khi đó trường thiếu chuyển thành phỏng đoán có nhãn, **không bị xoá** |
| 3 | Ý định tra cứu và coaching không qua cổng |
| 4 | Cổng chặn theo **mức đắt khi sửa muộn**, không theo mức đầy đủ. Khả thi kỹ thuật, pháp lý, ngân sách, timeline thì chặn. Insight, cách diễn đạt, số liệu minh hoạ thì không |
| 5 | Ngưỡng đầu ra là 8/10. Hai điểm còn lại in ra rõ để sales xử lý |

Danh sách trường bắt buộc / có điều kiện / nên có nằm trong knowledge, không trong BRD.

---

## 9. Điều hướng

| Layer | Ai quyết | Nội dung |
|---|---|---|
| Cổng | Code | Có được gọi agent chuyên môn hay chưa |
| Router | Mô hình | Trong số agent được phép, gọi cái nào, thứ tự nào |

Bỏ cơ chế group tuần tự G1 → G2. Brief thật không đi theo một đường - sales hỏi ngược và bổ sung thông tin giữa dòng.

**Yêu cầu với mô tả skill:** mỗi agent chuyên môn khai điều kiện tiên quyết ngay trong phần mô tả, dạng đọc được lúc chọn agent. Ví dụ *"Cần có bản ghi yêu cầu đã qua cổng. Chưa có thì không chạy."* Đặt trong thân skill thì lúc chọn agent không ai đọc thấy - đúng lỗi bản cũ.

---

## 10. Cách hỏi lại

| # | Quy tắc |
|---|---|
| 1 | Suy luận trước những gì suy được, điền sẵn, đánh dấu là suy luận, xin xác nhận thay vì hỏi |
| 2 | Chỉ hỏi cái không đoán được |
| 3 | Gộp 1 lượt, có nhóm tiêu đề: *tôi tự suy ra* · *cần bạn cho biết* · *cần hỏi lại khách* |
| 4 | **Không giới hạn số câu hỏi.** Ngưỡng dừng là đã đủ để ra phán quyết khả thi |
| 5 | Không hỏi câu phụ thuộc câu trước |
| 6 | Mỗi câu kèm lý do hỏi |
| 7 | Tách rõ câu sales tự trả lời được và câu phải hỏi khách, để họ gửi 1 email chứ không phải 3 |

Quy tắc 4 thay thế 4 dòng phải xoá ở §2. Lý do: sales không biết mình cần biết gì, nên giới hạn số câu là bỏ đúng những câu họ sẽ không nghĩ ra.

---

## 11. Hai điểm dừng chờ sales xác nhận

Nếu chạy hết một lượt rồi mới đưa sales xem, họ phát hiện sai từ câu đầu và phải làm lại toàn bộ. Nên dừng 2 lần giữa đường.

### Chốt 1 - sau khi trích thông tin

Hệ thống trình ra: cái gì sales đã nói · cái gì hệ thống tự suy ra · cái gì đang phỏng đoán. Sales bấm xác nhận, hoặc sửa từng dòng.

### Chốt 2 - sau khi có hướng giải pháp

Hệ thống trình ra hướng giải pháp và phán quyết khả thi, **chưa render proposal đầy đủ**. Sales duyệt hoặc đổi hướng.

### Yêu cầu kỹ thuật cho 2 chốt

| # | Yêu cầu | Cụ thể |
|---|---|---|
| 1 | Lưu lại kết quả từng bước, không chỉ kết quả cuối | Để chạy lại được một bước mà không chạy lại cả pipeline |
| 2 | Sửa ở Chốt 1 thì chạy lại **từ bước trích thông tin** | Các bước chưa chạy thì chưa có gì để mất |
| 3 | Đổi hướng ở Chốt 2 thì chạy lại **từ bước giải pháp** | Giữ nguyên kết quả bước khai thác yêu cầu, chiến lược, pháp lý |
| 4 | Chạy lại một bước thì **các bước phụ thuộc nó cũng chạy lại**, các bước độc lập thì không | Ví dụ đổi hướng giải pháp thì phải render lại proposal, nhưng không cần chạy lại kiểm pháp lý |
| 5 | Có thể chạy lại **một agent đơn lẻ** khi nó lỗi hoặc timeout | Không bắt sales gửi lại brief từ đầu |
| 6 | Phiên phục hồi được sau khi mất kết nối | Thông tin đã thu không mất |

---

## 12. Hợp đồng dữ liệu

Mỗi bước nhận và trả dữ liệu có cấu trúc. Bước sau không tự đọc hiểu văn bản của bước trước.

| Bước | Nhận | Trả |
|---|---|---|
| requirement_elicitation | Tin nhắn thô | Bản ghi yêu cầu · bản đồ ràng buộc · trạng thái cổng · danh sách phỏng đoán |
| market_strategy | Bản ghi yêu cầu | Báo cáo chiến lược |
| compliance_policy | Bản ghi yêu cầu | Verdict · danh sách điều kiện |
| product_solution | Bản ghi yêu cầu + chiến lược + điều kiện pháp lý | Journey · screen spec · phán quyết khả thi · gói · giá · hạng mục custom |
| client_simulator | Câu hỏi hoặc phản đối của khách | Hướng trả lời |
| proposal_renderer | Tất cả phía trên + mức độ hoàn thiện cần | Bộ đầu ra · bảng tự đánh giá |

| # | Yêu cầu |
|---|---|
| 1 | Trường bắt buộc phải **không rỗng**, không chỉ tồn tại |
| 2 | Mỗi thông tin trong bản ghi yêu cầu mang nguồn: *sales nói* · *suy luận* · *phỏng đoán* |
| 3 | Cấu trúc đúng không có nghĩa nội dung tốt. Cấu trúc chặn lỗi kỹ thuật, bảng tiêu chí chất lượng chặn lỗi nội dung. Cần cả hai |

---

## 13. Kỳ vọng hệ thống

Số dưới đây là đề xuất, cần chốt lại với dev.

### Thời gian phản hồi

| Bước | Mục tiêu |
|---|---|
| Che PII + phân loại ý định | < 1s |
| Trả lời câu tra cứu | < 5s tới token đầu |
| Ra bộ câu hỏi lại | < 10s tới token đầu |
| Chạy 1 agent chuyên môn | < 45s |
| Toàn bộ tới proposal | < 4 phút |

Bắt buộc có **streaming**. Không streaming thì 4 phút màn hình trắng là không dùng được.

### Tải

| Chỉ tiêu | Đề xuất |
|---|---|
| Sales dùng đồng thời | 20 |
| Phiên mở cùng lúc | 50 |
| Brief xử lý mỗi ngày | 100 |

### Chi phí

| Chỉ tiêu | Yêu cầu |
|---|---|
| Chi phí mỗi brief đầy đủ | Đo và báo cáo, đặt ngưỡng cảnh báo |
| Cache prompt | Bật. Xem §6 yêu cầu 10 |

### Sẵn sàng và chịu lỗi

| Tình huống | Yêu cầu |
|---|---|
| Nhà cung cấp mô hình lỗi | Thử lại có giãn cách. Sau 3 lần báo lỗi rõ, không trả nội dung rỗng |
| Một agent timeout | Trả phần đã có, phiên không sập, cho chạy lại riêng bước đó |
| Truy xuất tri thức lỗi | Dừng bước, nói rõ không có tri thức. Không cho mô hình tự trả lời |
| Agent trả sai cấu trúc | Thử lại 1 lần, sau đó báo rõ bước lỗi. Không đưa dữ liệu sai sang bước sau |
| Mất kết nối giữa phiên | Phiên phục hồi được, thông tin đã thu không mất |

### Nhất quán

| Yêu cầu |
|---|
| Cùng 1 brief chạy lại: **phán quyết khả thi và gói phải giống nhau.** Phần diễn đạt được phép khác |
| Cổng là code nên phải cho kết quả giống nhau tuyệt đối |

### Bảo mật và dữ liệu

| Yêu cầu |
|---|
| Bảng bí danh PII chỉ tồn tại trong phiên, **không ghi vào file đầu ra**, không ghi vào log |
| Log không chứa PII thô |
| Đặt thời hạn lưu phiên và nói rõ thời hạn đó |
| Ghi rõ tri thức và dữ liệu phiên lưu ở đâu |
| Đăng nhập giới hạn theo domain là mong muốn, chưa thuộc phạm vi bản này |

---

## 14. Ghi log

Bản cũ khó chẩn đoán vì không biết bước nào đã chạy. Mỗi request phải log được:

| Mục | Vì sao cần |
|---|---|
| Đã che bao nhiêu mục PII, loại gì. Không log giá trị | Kiểm masking có chạy thật |
| Ý định được phân loại là gì | Debug việc bị chặn oan |
| Trạng thái cổng + danh sách trường thiếu | Bản cũ không có, nên không ai biết cổng đang mở |
| Agent nào được gọi, thứ tự nào, mất bao lâu | Debug điều hướng |
| Tài liệu nào được nạp, tổng dung lượng, đã bỏ bớt cái gì | Kiểm §5 và §6 có hiệu lực |
| Dung lượng prompt và đầu ra từng lần gọi mô hình | Phát hiện phình ngữ cảnh trước khi mô hình quên ràng buộc |
| Số lỗi soát đầu ra bắt được, loại gì | Đo chất lượng theo thời gian |
| Điểm tự đánh giá + mục còn thiếu | Đo chất lượng theo thời gian |
| Version của mỗi file tri thức đã dùng | Truy nguyên khi proposal sai |

Mỗi phiên có 1 mã tra cứu. Sales báo lỗi thì đọc log ra được ngay bước nào sai.

---

## 15. Định nghĩa hoàn thành

Hành vi hệ thống. Kịch bản kiểm chất lượng nội dung nằm trong file tiêu chí thuộc knowledge.

| # | Kiểm gì | Đạt khi |
|---|---|---|
| 1 | Brief thiếu trường bắt buộc | Cổng trả `CHAN_HOI_LAI`. Không agent chuyên môn nào được gọi. Kiểm bằng log |
| 2 | Câu tra cứu | Không qua cổng, trả thẳng, dưới 5s tới token đầu |
| 3 | Sales nói "cứ làm đi" | Chạy, đầu ra có nhãn phỏng đoán và liệt kê đủ mục đang đoán |
| 4 | Brief có PII | Đã che trước khi vào mô hình. Kiểm bằng log |
| 5 | Bảng bí danh | Không xuất hiện trong file đầu ra và trong log |
| 6 | Sales sửa 1 thông tin ở Chốt 1 | Chạy lại từ bước trích thông tin, phần khác giữ nguyên |
| 7 | Sales đổi hướng ở Chốt 2 | Chạy lại từ bước giải pháp, thông tin đã thu không mất |
| 8 | Một tài liệu tri thức được 2 agent cùng cần | Chỉ nạp 1 lần trong request đó. Kiểm bằng log |
| 9 | Đầu ra JSON của mỗi sub-agent | Không chứa field bước sau không dùng, không lặp lại brief |
| 10 | Tính năng không trace được về bảng giá | Vào nhóm cần tech xác nhận, không bao giờ vào nhóm có sẵn |
| 11 | Đầu ra gửi khách | 0 gạch dài, 0 ngoặc diễn giải thừa, 0 từ trong danh sách cấm |
| 12 | Một agent timeout | Trả phần đã có, phiên không sập, chạy lại được riêng bước đó |
| 13 | Một agent trả sai cấu trúc | Không lan sang bước sau, báo rõ bước lỗi |
| 14 | Truy xuất tri thức lỗi | Dừng bước, báo không có tri thức. Không có nội dung tự sinh |
| 15 | Chạy lại cùng brief | Phán quyết khả thi và gói không đổi |
| 16 | Mỗi thông tin trong bản ghi yêu cầu | Truy được nguồn: sales nói · suy luận · phỏng đoán |
| 17 | Không có đường nào tắt được cổng | Rà code: không tham số, không cờ, không biến môi trường |

---

## 16. Cần chốt

| # | Câu hỏi | Chặn cái gì |
|---|---|---|
| 1 | Code hiện tại gọi masking như thành phần bắt buộc hay như agent router chọn? | Nếu là agent thì phải sửa trước, xem §2 |
| 2 | Bảng giá có đủ chi tiết để sales tự tra tính năng → gói → giá không? | Agent gói-giá làm được đến đâu |
| 3 | Custom tính tiền theo cơ chế nào? | Không có thì mọi custom vẫn chờ Tech Lead |
| 4 | Có tài liệu cho biết tính năng nào đã chạy được, cái nào còn trong lộ trình? | Phán quyết khả thi có nhóm "trong lộ trình" hay không |
| 5 | Ai điền cột "chỗ sales hay hứa sai" trong bảng nghiệp vụ? | Không suy ra từ tài liệu được |
| 6 | Bảng nghiệp vụ đặt tên theo từ sales dùng hay theo cách chia của tài liệu nội bộ? | Sales tra theo từ họ nói với khách |
| 7 | Có cần phần khuyến mại may rủi không? | Nếu cần thì legal viết |
| 8 | Giữ hay bỏ vector DB? | Xem §5 |
| 9 | Chốt các số ở §13 | Dev cần số để thiết kế |
| 10 | `design/` có vào phạm vi đợt này không? | Hiện là prompt 516 byte, không có tri thức nghiệp vụ |

---

## 17. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Bị ép cắt thì cắt cổng "cho nó ra được cái gì đó" | Đây chính xác là quyết định đã tạo ra bản cũ. Nếu phải cắt, cắt số agent chuyên môn, không cắt cổng |
| Cổng lại nằm ở chỗ skip được | Checklist trước khi merge: cổng có phải code · che PII có phải thành phần hệ thống · soát đầu ra có nằm ngoài agent |
| Cổng quá cứng, sales bỏ dùng | Phân loại ý định + quyền nói "cứ làm đi" + ngưỡng 8/10 |
| Agent tự xưng đạt chuẩn | Bắt in bảng kiểm kèm dẫn chứng trích từ hội thoại, không cho ghi PASS trống |
| Làm phần chiến lược cho hay rồi bỏ phần khả thi | Sales tự viết được phần chiến lược. Họ không tự đánh giá được feasibility - đó là lý do phải kéo tech vào |
| Tri thức không có mà mô hình tự trả lời | Truy xuất lỗi thì dừng, không cho tự sinh |
| Ngữ cảnh phình lại như bản cũ | §5 và §6 cộng với log dung lượng ở §14 |

Câu tự kiểm: **sau khi dùng, sales có còn phải nhắn tech team không?**
