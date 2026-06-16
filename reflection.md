# Day 14 — Reflection
## Evaluation Report & Failure Analysis

---

## 1. Benchmark Results Summary

Dưới đây là tóm tắt kết quả từ Exercise 3.2:

**Overall pass rate:** `5.0%` (Chỉ có 1 trên 20 QA pairs vượt qua hoàn toàn ngưỡng điểm >= 0.5 ở cả 3 metrics).

**Average scores:**

| Metric | Average | Min | Max | Std Dev |
|--------|---------|-----|-----|---------|
| Faithfulness | 0.27 | 0.00 | 0.75 | 0.17 |
| Relevance | 0.40 | 0.11 | 0.80 | 0.19 |
| Completeness | 0.68 | 0.12 | 1.00 | 0.31 |
| Overall Score | 0.45 | 0.17 | 0.69 | 0.12 |

**Score interpretation (theo bài giảng):**
- Bao nhiêu metrics ở Good (0.8–1.0)? `0`
- Bao nhiêu metrics ở Needs Work (0.6–0.8)? `1` (Completeness đạt trung bình 0.68)
- Bao nhiêu metrics ở Significant Issues (<0.6)? `2` (Faithfulness đạt 0.27 và Relevance đạt 0.40)

**Failure type distribution:**

| Failure Type | Count | Percentage |
|--------------|-------|------------|
| hallucination | 15 | 75.0% |
| irrelevant | 0 | 0.0% |
| incomplete | 1 | 5.0% |
| off_topic | 3 | 15.0% |
| refusal | 0 | 0.0% |

---

## 2. Top 3 Worst Failures — 5 Whys Analysis

### Failure 1

**Question:** `Define the concept of 'hallucination' in LLMs.`

**Agent Answer:** `Hallucination refers to a hardware error where the CPU overheats due to infinite loops during LLM inference.`

**Scores:** Faithfulness: `0.00` | Relevance: `0.25` | Completeness: `0.27` | Overall: `0.17`

**5 Whys Analysis:**
| Level | Question | Answer |
|-------|----------|--------|
| Symptom | Vấn đề là gì? | Agent trả lời sai lệch nghiêm trọng về khái niệm ảo giác (coi đó là lỗi phần cứng CPU quá nhiệt). |
| Why 1 | Tại sao xảy ra? | Do thông tin ảo giác (CPU quá nhiệt) được tạo ra không hề có trong ngữ cảnh (context) được cung cấp. |
| Why 2 | Tại sao Why 1 xảy ra? | Mô hình sử dụng tri thức sai lệch có sẵn trong trọng số thay vì dựa vào ngữ cảnh của RAG. |
| Why 3 | Tại sao Why 2 xảy ra? | Prompt không có chỉ thị bắt buộc mô hình chỉ được trả lời dựa trên context, và phải từ chối nếu thiếu thông tin. |
| Why 4 | Root cause là gì? | Hệ thống thiếu bộ lọc ảo giác (Hallucination Checker) và Prompt chưa đủ chặt chẽ để cấm mô hình suy diễn ngoài lề. |

**Root cause (from `find_root_cause()`):**
> `Context is missing or irrelevant — improve retrieval`

**Bạn có đồng ý với root cause suggestion không? Tại sao?**
> Đồng ý một phần. Mặc dù lý do trực tiếp là Prompt thiếu ràng buộc và Agent tự suy diễn (hallucination), nhưng việc cải thiện chất lượng ngữ cảnh (Retrieval) chi tiết hơn cũng sẽ giúp mô hình có thông tin tham chiếu chính xác để trả lời, giảm thiểu sự tự suy diễn.

**Proposed fix (cụ thể, actionable):**
> 1. Thêm chỉ thị phủ định vào Prompt: "Chỉ trả lời dựa trên ngữ cảnh được cung cấp. Nếu ngữ cảnh không chứa thông tin, hãy trả lời 'Tôi không biết', tuyệt đối không được tự bịa đặt."
> 2. Thiết lập cấu hình temperature của mô hình bằng `0.0` để tối đa hóa tính ổn định và chính xác của câu trả lời.

---

### Failure 2

**Question:** `Explain the 'lost in the middle' phenomenon in LLMs and how to mitigate it.`

**Agent Answer:** `The lost in the middle phenomenon is an optical illusion where users focus on the center of the web page screen.`

**Scores:** Faithfulness: `0.17` | Relevance: `0.43` | Completeness: `0.12` | Overall: `0.24`

**5 Whys Analysis:**
| Level | Question | Answer |
|-------|----------|--------|
| Symptom | Vấn đề là gì? | Agent hiểu sai hiện tượng kỹ thuật "lost in the middle" của LLM thành hiện tượng ảo ảnh thị giác. |
| Why 1 | Tại sao xảy ra? | Agent tự động dịch nghĩa đen của cụm từ "lost in the middle" và liên tưởng đến thiết kế giao diện web. |
| Why 2 | Tại sao Why 1 xảy ra? | Ngữ cảnh kỹ thuật được cung cấp quá ngắn và mơ hồ, không giải thích rõ đây là hiện tượng attention của mô hình ngôn ngữ. |
| Why 3 | Tại sao Why 2 xảy ra? | Retriever không truy xuất được tài liệu chi tiết và sâu sắc hơn về giới hạn ngữ cảnh của LLM. |
| Why 4 | Root cause là gì? | Cơ sở dữ liệu tri thức thiếu tài liệu chi tiết hoặc Retriever chọn sai chunk có độ liên quan kém. |

**Root cause:**
> `Context is missing or irrelevant — improve retrieval`

**Proposed fix:**
> 1. Cải tiến Retriever sử dụng Hybrid Search (dense + sparse) kết hợp với Reranker để đảm bảo các chunk kỹ thuật chính xác nhất được chọn.
> 2. Bổ sung các tài liệu chuyên sâu giải thích chi tiết về hiện tượngattention và context window của LLM vào Vector Database.

---

### Failure 3

**Question:** `Tell me about the fast optimizer that does not use gradients.`

**Agent Answer:** `I can tell you that gradient-free optimizers include RMSprop and Adam, which do not use gradients.`

**Scores:** Faithfulness: `0.13` | Relevance: `0.44` | Completeness: `0.27` | Overall: `0.28`

**5 Whys Analysis:**
| Level | Question | Answer |
|-------|----------|--------|
| Symptom | Vấn đề là gì? | Agent trả lời sai kiến thức cơ bản nghiêm trọng (khẳng định RMSprop và Adam không dùng gradient). |
| Why 1 | Tại sao xảy ra? | Agent bị nhầm lẫn và liên kết sai thông tin giữa gradient descent và gradient-free optimizers trong context. |
| Why 2 | Tại sao Why 1 xảy ra? | Ngữ cảnh viết chung cả hai loại thuật toán tối ưu trong cùng một đoạn văn ngắn, khiến LLM hiểu nhầm mối quan hệ. |
| Why 3 | Tại sao Why 2 xảy ra? | LLM không có khả năng tự kiểm chứng tính đúng đắn logic của câu trả lời trước khi phản hồi. |
| Why 4 | Root cause là gì? | Cấu trúc dữ liệu context đầu vào kém (noisy context) và thiếu validation gate để check factual correctness. |

**Root cause:**
> `Context is missing or irrelevant — improve retrieval`

**Proposed fix:**
> 1. Chuẩn hóa và làm sạch cấu trúc tài liệu nguồn: Tách biệt hoàn toàn các khái niệm gradient-based và gradient-free optimizers thành các phần riêng biệt.
> 2. Triển khai Fact-checking hoặc Validation Gate để lọc các tuyên bố kỹ thuật sai lệch trước khi xuất kết quả.

---

## 3. Failure Clustering

Theo bài giảng: "Fix 1 root cause giải quyết nhiều failures cùng lúc."

**Cluster Analysis:**

| Cluster | Root Cause | Failures in cluster | Priority |
|---------|-----------|--------------------:|----------|
| 1 | Hallucination do thiếu ràng buộc prompt & temperature cao | E04, A03, M01, M05, M06, A01, A02 | High |
| 2 | Thiếu thông tin do Context Window nhỏ / Chunking kém | H04, E03, M03, H05 | Medium |
| 3 | Nhầm lẫn khái niệm do context mơ hồ / noisy | H01, E02, M07, H03 | Medium |

**Nếu chỉ fix 1 cluster, bạn chọn cluster nào? Tại sao?**
> Tôi chọn **Cluster 1 (Hallucination do thiếu ràng buộc prompt)**. Hallucination là lỗi nghiêm trọng nhất làm mất hoàn toàn sự tin cậy của người dùng vào hệ thống. Việc khắc phục lỗi này bằng cách tinh chỉnh Prompt Instruction và giảm temperature là nhanh chóng nhất, dễ thực hiện và mang lại sự cải thiện điểm số lớn nhất cho benchmark.

---

## 4. Improvement Log (from `generate_improvement_log`)

Paste output của `generate_improvement_log()`:

```markdown
| Failure ID | Type | Root Cause | Suggested Fix | Status |
|------------|------|------------|---------------|--------|
| F001 | off_topic | Context is missing or irrelevant — improve retrieval | Implement hallucination checker to filter unsupported claims | Open |
| F002 | off_topic | Answer is missing key information — increase context window or improve generation | Verify retriever content alignment to ensure relevant background contexts are loaded | Open |
| F003 | hallucination | Context is missing or irrelevant — improve retrieval | Increase chunk size or retrieve more chunks (higher top-k) in RAG pipeline to reduce context fragmentation | Open |
| F004 | hallucination | Answer does not address the question — improve prompt clarity | Add structured formatting instructions to prompt (e.g. bullet points) to ensure all facets are answered | Open |
| F005 | hallucination | Answer does not address the question — improve prompt clarity | Implement hallucination checker to filter unsupported claims | Open |
| F006 | hallucination | Context is missing or irrelevant — improve retrieval | Verify retriever content alignment to ensure relevant background contexts are loaded | Open |
| F007 | off_topic | Answer is missing key information — increase context window or improve generation | Increase chunk size or retrieve more chunks (higher top-k) in RAG pipeline to reduce context fragmentation | Open |
| F008 | hallucination | Context is missing or irrelevant — improve retrieval | Add structured formatting instructions to prompt (e.g. bullet points) to ensure all facets are answered | Open |
| F009 | hallucination | Multiple issues detected — review full pipeline | Implement hallucination checker to filter unsupported claims | Open |
| F010 | hallucination | Context is missing or irrelevant — improve retrieval | Verify retriever content alignment to ensure relevant background contexts are loaded | Open |
| F011 | hallucination | Context is missing or irrelevant — improve retrieval | Increase chunk size or retrieve more chunks (higher top-k) in RAG pipeline to reduce context fragmentation | Open |
| F012 | hallucination | Answer is missing key information — increase context window or improve generation | Add structured formatting instructions to prompt (e.g. bullet points) to ensure all facets are answered | Open |
| F013 | hallucination | Context is missing or irrelevant — improve retrieval | Implement hallucination checker to filter unsupported claims | Open |
| F014 | hallucination | Context is missing or irrelevant — improve retrieval | Verify retriever content alignment to ensure relevant background contexts are loaded | Open |
| F015 | incomplete | Answer is missing key information — increase context window or improve generation | Increase chunk size or retrieve more chunks (higher top-k) in RAG pipeline to reduce context fragmentation | Open |
| F016 | hallucination | Context is missing or irrelevant — improve retrieval | Add structured formatting instructions to prompt (e.g. bullet points) to ensure all facets are answered | Open |
| F017 | hallucination | Answer does not address the question — improve prompt clarity | Implement hallucination checker to filter unsupported claims | Open |
| F018 | hallucination | Answer does not address the question — improve prompt clarity | Verify retriever content alignment to ensure relevant background contexts are loaded | Open |
| F019 | hallucination | Context is missing or irrelevant — improve retrieval | Increase chunk size or retrieve more chunks (higher top-k) in RAG pipeline to reduce context fragmentation | Open |
```

**Thêm 3 improvement suggestions từ `generate_improvement_suggestions()`:**
1. `Implement hallucination checker to filter unsupported claims`
2. `Verify retriever content alignment to ensure relevant background contexts are loaded`
3. `Increase chunk size or retrieve more chunks (higher top-k) in RAG pipeline to reduce context fragmentation`

---

## 5. Regression Testing Strategy

### CI/CD Integration

**Câu 1: Khi nào chạy `run_regression()` trong production system?**
> `run_regression()` nên được kích hoạt tự động ở hai thời điểm quan trọng:
> 1. Mỗi khi có một pull request/merge code mới vào nhánh `main` nhằm phát hiện lỗi regression từ mã nguồn.
> 2. Mỗi khi có thay đổi về System Prompt, cấu hình tham số LLM (như temperature), hoặc khi thay đổi mô hình LLM nền tảng.

**Câu 2: Threshold regression 0.05 có phù hợp domain của bạn không?**
> Đối với domain hỗ trợ kỹ thuật RAG & AI, ngưỡng 0.05 là tương đối phù hợp để cân bằng giữa tính ổn định và tốc độ phát triển. Tuy nhiên, nếu áp dụng cho hệ thống tài chính hay y tế, ngưỡng này nên được siết chặt hơn (ví dụ `0.02`) để giảm thiểu rủi ro phát sinh sai sót kỹ thuật.

**Câu 3: Khi phát hiện regression — block deployment hay chỉ alert?**
> **Block deployment** đối với metric **Faithfulness** (độ trung thực) vì ảo giác có thể phá hủy hoàn toàn uy tín của hệ thống.
> **Alert và review** đối với các metric như **Completeness** hoặc **Relevance** vì đôi khi chất lượng sụt giảm nhẹ do việc thay đổi cách hành văn hoặc định dạng mà không ảnh hưởng lớn đến giá trị sử dụng.

**Câu 4: Eval pipeline nên chạy ở đâu trong CI/CD flow?**

```
Code change → [Chạy Unit Tests] → [Chạy Offline Eval (RAGAS)] → [Run Regression check vs Baseline] → Deploy
              (bước 1)          (bước 2)                     (bước 3)
```
> *Điền 3 bước eval vào flow trên:*
> - Bước 1: **Chạy Unit Tests** (đảm bảo code chạy đúng logic cơ bản, không lỗi syntax).
> - Bước 2: **Chạy Offline Eval (RAGAS)** (đo lường các điểm số chất lượng trên Golden Dataset).
> - Bước 3: **Run Regression check vs Baseline** (so sánh điểm số mới với baseline cũ để quyết định deploy hay block).

---

## 6. Continuous Improvement Loop

Theo bài giảng: Evaluate → Analyze → Improve → Augment (add to benchmark) → lặp lại

**Sau lab hôm nay, 3 actions tiếp theo bạn sẽ làm để improve agent:**

| Priority | Action | Metric sẽ improve | Expected impact |
|----------|--------|-------------------|-----------------|
| 1 | Thêm negative constraints và few-shot examples vào Prompt | Faithfulness | Ngăn chặn ảo giác, tăng Faithfulness từ 0.27 lên > 0.85 |
| 2 | Tích hợp bộ Rerank (Cross-Encoder) vào pipeline | Context Precision | Đưa tài liệu chuẩn nhất lên đầu, cải thiện chất lượng trả lời |
| 3 | Tăng chunk size từ 250 lên 500 tokens và thêm overlap 10% | Context Recall / Completeness | Giảm phân mảnh thông tin, tăng độ bao phủ ý |

**Bạn sẽ thêm failure cases nào vào benchmark cho sprint tiếp theo?**
> 1. Thêm các câu hỏi so sánh đa tài liệu phức tạp (multi-document synthesis).
> 2. Thêm các prompt injection nguy hiểm sử dụng nhiều ngôn ngữ phối hợp để kiểm tra độ bảo mật.

---

## 7. Framework Reflection

**Framework bạn đã dùng trong lab:** `RAGAS-inspired heuristic` (Word-overlap)

**Nếu dùng trong production, bạn sẽ chọn framework nào? Tại sao?**
> Trong production, tôi sẽ chọn **RAGAS** hoặc **DeepEval**.

| Tiêu chí | Lý do chọn |
|----------|------------|
| Focus phù hợp vì... | RAGAS cung cấp bộ chỉ số đo lường chuyên sâu dành riêng cho RAG (được đánh giá bằng LLM-as-a-Judge) thay vì so khớp từ vựng đơn giản, giúp đánh giá chính xác về mặt ngữ nghĩa (semantic). |
| CI/CD integration vì... | DeepEval hỗ trợ tích hợp cực tốt với pytest-native assertions và CLI commands, giúp dễ dàng thiết lập các quality gates trực tiếp trong GitHub Actions. |
| Team workflow vì... | DeepEval cung cấp CONFIDENT AI Dashboard để trực quan hóa kết quả chạy benchmark, lưu lịch sử và giúp các thành viên trong nhóm dễ dàng cộng tác kiểm thử. |
