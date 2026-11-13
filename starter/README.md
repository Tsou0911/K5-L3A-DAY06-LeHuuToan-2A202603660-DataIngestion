# Starter · PostgreSQL + pgvector via Docker

Starter dùng **PostgreSQL + pgvector trong Docker** để lưu vector. Embedding chạy local bằng model đa ngữ; lần tải model đầu cần Internet và có thể mất thời gian.

## Cài đặt trên Windows PowerShell

Mở Docker Desktop, chờ trạng thái Engine chạy, sau đó mở PowerShell tại thư mục `starter/`:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d --wait
python scripts/check_setup.py
```

Python 3.11–3.14 được chấp nhận. Nếu PowerShell chặn kích hoạt môi trường, chỉ áp dụng trong cửa sổ hiện tại rồi thử lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

`Setup OK` xác nhận Python kết nối được PostgreSQL trong Docker và extension pgvector đã bật. Docker giữ dữ liệu trong named volume `pg_data` khi container dừng. Không commit `.env` hoặc `.venv/`.

## Embedding model

Mặc định là `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, model đa ngữ phù hợp truy vấn tiếng Việt. Lần chạy đầu tải model từ Hugging Face; model chạy trên máy, không cần API key. Ghi tên model, phiên bản thư viện và số chiều thực tế vào báo cáo. Dùng cùng model cho A/B/C.

## Pipeline

Chuẩn bị PDF mặc định trong `data/` thành các trang và cấu hình chunk A/B/C bằng lệnh:

```powershell
python scripts/prepare_corpus.py
```

Kết quả JSONL được ghi vào `results/prepared/`: `pages.jsonl` giữ văn bản đã chuẩn hóa cùng số trang PDF vật lý; ba file `chunks_*.jsonl` giữ `document_id`, nguồn và trang cho mỗi chunk. Có thể đổi PDF, ID nguồn, thư mục đầu ra, kích thước và overlap bằng các tham số `--pdf`, `--document-id`, `--source`, `--output`, `--size` và `--overlap`. Kích thước tính bằng ký tự, không phải token.

`A_fixed` dùng cửa sổ cố định có overlap; `B_paragraph` đóng gói theo đoạn văn; `C_paragraph_metadata` dùng cùng chunk như B để áp dụng filter khi truy vấn. Script không tự đoán metadata section từ bố cục PDF; cần gắn nhãn section đã kiểm chứng trước khi dùng các filter `section` trong benchmark. Các module `src/` cũng có embedding local, lưu bền vững, filter metadata và tính metric retrieval. Xem [GUIDE.md](../GUIDE.md), [BENCHMARK.md](../BENCHMARK.md) và [SUBMISSION.md](../SUBMISSION.md).

Sau khi chuẩn bị chunk, tạo embedding và lưu cả ba cấu hình vào PostgreSQL:

```powershell
python -m src.run
```

Lần đầu chạy sẽ tải embedding model. Thông tin model, số chiều và số chunk được ghi vào `results/ingestion_summary.json`. Lệnh này chưa chấm benchmark; cần gắn metadata section đã kiểm chứng trước khi đánh giá các câu hỏi có filter.

Chạy truy xuất trên tập dev để xem top-3 và chọn cấu hình:

```powershell
python scripts/evaluate_benchmark.py --split dev
```

Trace và chỉ số Hit@1/Evidence Hit@3 được ghi vào `results/benchmark_dev_traces.jsonl` và `results/benchmark_dev_summary.json`. Chỉ sau khi chốt cấu hình theo dev mới chạy test, đồng thời chỉ định cấu hình đã chọn, ví dụ `python scripts/evaluate_benchmark.py --split test --strategy B_paragraph`; script không cho so sánh các cấu hình trên tập test.

pgvector dùng cosine distance. Các chiến lược được phân biệt bằng trường `strategy`; truy vấn C có thể truyền filter metadata. Khi nạp lại, chunk cũ của cùng tài liệu và chiến lược được thay thế.
