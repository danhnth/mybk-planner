# mybk-planner: Lập kế hoạch học tập, xem GPA & công cụ CLI cho cổng myBK của HCMUT

[![PyPI version](https://img.shields.io/pypi/v/mybk-planner)](https://pypi.org/project/mybk-planner/)
[![Python](https://img.shields.io/pypi/pyversions/mybk-planner)](https://pypi.org/project/mybk-planner/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/danhnth/mybk-planner/actions/workflows/ci.yml/badge.svg)](https://github.com/danhnth/mybk-planner/actions)
[![Downloads](https://img.shields.io/pypi/dm/mybk-planner)](https://pypi.org/project/mybk-planner/)
[![DeepWiki](https://deepwiki.com/badge/github/danhnth/mybk-planner.svg)](https://deepwiki.com/danhnth/mybk-planner)

**mybk-planner** là công cụ dòng lệnh chỉ đọc dành cho sinh viên Đại học Bách Khoa TP.HCM, giúp lập kế hoạch học tập ngay trên cổng myBK: theo dõi GPA, xem bảng điểm, tiến độ chương trình đào tạo (CTĐT), thời khóa biểu, lịch thi, cùng gợi ý môn học cho học kỳ tới kèm dự tính học phí. Tất cả ngay trên terminal.

Công cụ chỉ đọc: tìm lớp và gợi ý kế hoạch, còn việc đăng ký vẫn diễn ra trên cổng chính thức.

[English → README.md](README.md)

## Mục lục

- [Công cụ này làm được gì?](#công-cụ-này-làm-được-gì)
- [Vì sao chọn mybk-planner?](#vì-sao-chọn-mybk-planner)
- [Cài đặt như thế nào?](#cài-đặt-như-thế-nào)
- [Cấu hình như thế nào?](#cấu-hình-như-thế-nào)
- [Bắt đầu nhanh](#bắt-đầu-nhanh)
- [Danh sách lệnh](#danh-sách-lệnh)
- [Trình lập kế hoạch (`plan`)](#trình-lập-kế-hoạch-plan)
- [REPL tương tác](#repl-tương-tác)
- [Xuất JSON để viết script](#xuất-json-để-viết-script)
- [Ghi chú parser & quirk của API](#ghi-chú-parser--quirk-của-api)
- [Bảo mật & phạm vi](#bảo-mật--phạm-vi)
- [Kiểm thử & phát triển](#kiểm-thử--phát-triển)
- [Câu hỏi thường gặp](#câu-hỏi-thường-gặp)
- [Giấy phép](#giấy-phép)

## Công cụ này làm được gì?

- **GPA & bảng điểm**: GPA tích lũy theo thang 10 và thang 4, lịch sử GPA từng học kỳ, phân bố điểm chữ, danh sách môn điểm D có thể cải thiện, và xử lý đúng trường hợp học lại đã đạt: môn từng rớt F nhưng sau đó đạt (D+) không còn được tính là "chưa đạt".
- **Tiến độ CTĐT**: tiến độ tín chỉ theo từng khối kiến thức so với yêu cầu chương trình, tính đúng các khối có nhiều ràng buộc (khối BB + tổ hợp tự chọn + đồ án được cộng dồn, không gộp nhầm).
- **Thời khóa biểu & lịch thi**: xem thời khóa biểu và lịch thi cho bất kỳ học kỳ nào.
- **Trình lập kế hoạch**: lệnh `plan` kết hợp CTĐT + bảng điểm (+ danh sách lớp mở nếu có đợt) để gợi ý môn học kỳ tới. Công cụ ưu tiên môn học lại, lấp từng khối đến đúng phần còn thiếu của riêng khối đó, và không vượt ngân sách tín chỉ mỗi học kỳ.
- **Dự tính học phí**: `plan` in ra học phí ước tính theo thông báo học phí 2026-2027 chính thức: học phí trọn gói theo chương trình của bạn, tín chỉ vượt định mức tính theo đơn giá khi đăng ký quá 18 TC/HK, và các mức giảm học phí (Bảng 1.2) khi đăng ký ít tín chỉ.
- **Phần chỉ-đọc của đăng ký môn**: xem đợt đăng ký hiện tại, lớp mở, phiếu đăng ký của bạn, và đợt hoãn thi. Các endpoint ghi **cố tình không** được bao bọc.

## Vì sao chọn mybk-planner?

Các công cụ cộng đồng HCMUT hiện có (`mybk-mobile`, `BKSchedule`, `BKSCrawler`, các script xem điểm) phần lớn đã lỗi thời, bị archive, hoặc chỉ là plugin trình duyệt. mybk-planner:

- **Đã kiểm chứng trực tiếp trên API `/app` hiện tại của myBK (2026)**: gồm cả quirk `?null` chống cache, BOM UTF-8, và envelope `{code,msg,data}`.
- **Chỉ đọc và an toàn**: không bao giờ có wrapper `tao-phieu-dang-ky` / `huy-phieu-dang-ky`. Quy trình đăng ký của bạn không bị ảnh hưởng.
- **Vừa CLI vừa thư viện**: bảng đẹp trên terminal, JSON thô với `--json`, và các hàm thuần túy (`analysis`, `fees`) để tự viết script.
- **Tôn trọng quyền riêng tư**: thông tin đăng nhập nằm trong file `.env` được git-ignore, không bao giờ bị commit; công cụ chỉ dùng cho tài khoản của chính bạn.

## Cài đặt như thế nào?

Cần **Python 3.10 trở lên**. Cài từ PyPI:

```bash
pip install mybk-planner
```

Hoặc cài từ mã nguồn:

```bash
git clone https://github.com/danhnth/mybk-planner.git
cd mybk-planner
pip install -e ".[dev]"      # kèm pytest + ruff cho phát triển
```

Cả hai cách đều cung cấp lệnh `mybk-planner` (hoặc chạy `python -m mybk_planner.cli`).

## Cấu hình như thế nào?

Copy file mẫu và điền thông tin đăng nhập của bạn:

```bash
cp .env.example .env
# sửa .env với thông tin đăng nhập myBK của bạn
```

| Biến | Bắt buộc | Mô tả |
|---|---|---|
| `MYBK_USERNAME` | có | BKNetId: phần trước ký tự `@` của email `@hcmut.edu.vn` |
| `MYBK_PASSWORD` | có | mật khẩu CAS (đặt trong dấu nháy nếu chứa `#` hoặc khoảng trắng) |
| `MYBK_MSSV` | không | ghi đè mã số sinh viên; tự động lấy từ hồ sơ nếu bỏ trống |

Thứ tự ưu tiên đọc thông tin: **tham số CLI → biến môi trường → file `.env`**. Các tên cũ `MYBK_TEST_USERNAME`/`MYBK_TEST_PASSWORD`/`MYBK_TEST_MSSV` vẫn hoạt động như phương án dự phòng.

## Bắt đầu nhanh

```bash
mybk-planner info            # hồ sơ sinh viên
mybk-planner gpa             # GPA tích lũy (thang 10 + thang 4)
mybk-planner ctdt            # tiến độ chương trình đào tạo theo khối
mybk-planner plan            # kế hoạch gợi ý học kỳ tới + dự tính học phí
mybk-planner                 # vào REPL tương tác
```

Mọi lệnh đều in bảng đẹp mặc định; thêm `--json` để lấy JSON thô cho script:

```bash
mybk-planner plan --max-tc 18 --semester 20253 --json
```

## Danh sách lệnh

| Lệnh | Chức năng |
|---|---|
| `auth` | đăng nhập CAS + kiểm tra JWT |
| `info` | hồ sơ sinh viên (MSSV, lớp, khoa) |
| `grades` | toàn bộ bảng điểm + tóm tắt đạt/rớt/trung bình |
| `gpa` | GPA tích lũy (thang 4 + thang 10) + số tín chỉ |
| `ctdt` | tiến độ CTĐT theo khối kiến thức |
| `schedule --semester-year 20252` | thời khóa biểu một học kỳ (mã `YYYYk`) |
| `exams --namhoc 2025 --hocky 2` | lịch thi (các dòng GK/CK) |
| `reg-dots` | các đợt đăng ký hiện tại |
| `reg-open-classes --hockytkb 20253` | lớp mở / có thể rút trong một học kỳ |
| `reg-tickets` | phiếu đăng ký đang xử lý + đã xong của bạn |
| `reg-defer --hocky 20253 --dot HOANTHI_CK.20253.1` | đợt hoãn thi + các dòng thi |
| `reg-profile` | hồ sơ người đăng ký của bạn |
| `plan [--max-tc 18.0] [--semester 20253]` | kế hoạch gợi ý + phân tích + học phí |
| `dashboard [--max-tc 18.0] [--semester 20253]` | info + GPA + plan trong một màn hình, một lần đăng nhập |

## Trình lập kế hoạch (`plan`)

Lệnh `plan` đọc CTĐT và bảng điểm của bạn, sau đó:

1. Ưu tiên môn học lại trước (môn đã học nhưng chưa đạt).
2. Lấp từng khối chưa đạt đến đúng phần còn thiếu của riêng khối đó, khối thiếu nhiều xử lý trước, để một khối không "nuốt" hết ngân sách trong khi Tốt nghiệp vẫn trống.
3. Phần ngân sách dư đổ vào môn của các khối đã đạt theo độ ưu tiên.
4. In bảng phân tích đầy đủ: diễn biến GPA, % hoàn thành, các khối còn thiếu, sức khỏe điểm số, thời gian tốt nghiệp dự kiến, và dự tính học phí.

Những điểm công cụ xử lý đúng:

- Căn cứ xác định "đạt" là bảng điểm, không phải `diemdat` của CTĐT. Học lại đạt (ví dụ F rồi D+) được loại khỏi danh sách "chưa đạt".
- Phần còn thiếu của khối là tổng các dòng yêu cầu riêng biệt. Feed lặp lại yêu cầu của mỗi nhóm trên mọi dòng môn học, và một khối có thể mang nhiều nhóm cộng dồn (ví dụ Chuyên ngành = khối BB + tổ hợp tự chọn + đồ án). Cách đọc "dòng đầu tiên" sẽ tính thiếu chương trình.
- Thời gian còn lại dùng chênh lệch tín chỉ giữa các học kỳ: số học kỳ cần thêm là `ceil(còn lại / max_tc)` theo ngân sách của bạn.
- Học phí (theo thông báo 2026-2027): phí trọn gói theo chương trình, tín chỉ trên định mức 18 TC/HK tính theo đơn giá, và các mức giảm ≤12/≤9/≤6 TC (15/30/45%) hiển thị khi kế hoạch của bạn đủ điều kiện.

## REPL tương tác

Chạy không kèm lệnh con để vào chế độ menu (một lần đăng nhập CAS, sau đó từ `1` đến `8` cùng `find`, `help`):

```
1 info · 2 grades · 3 gpa · 4 ctdt · 5 plan · 6 schedule · 7 exams · 8 dashboard
```

## Xuất JSON để viết script

Thêm `--json` vào bất kỳ lệnh nào để lấy một JSON duy nhất trên stdout (xác nhận đăng nhập ghi ra stderr), tiện cho việc pipe vào `jq` hoặc phân tích riêng:

```bash
mybk-planner plan --json | jq '.plan.completion'
```

## Ghi chú parser & quirk của API

Những điều API myBK không nói ra, ghi lại cho người đóng góp:

- **Envelope**: `{"code": "200"|"400", "data": …, "msg": …}`. `code` là *chuỗi*; `400` vẫn kèm dữ liệu nghiệp vụ.
- **Hậu tố `?null`** được thêm vào tham số đầu tiên của GET (quirk chống cache của `/app/js/main.js`).
- **BOM UTF-8** (`\ufeff`) được bỏ khỏi response.
- **Mã hóa `id_hoc_ky`**: `(YYYY % 100) * 10 + HK`. HK2 năm 25-26 ⇒ `252`.
- **CAS**: myBK dùng CAS 3.5.1 (`sso.hcmut.edu.vn/cas` cho `/app`). Gặp 403 khi đăng nhập thường là do bị giới hạn tốc độ, hãy chờ, đừng spam.

## Bảo mật & phạm vi

- **Chỉ dùng cho tài khoản của chính bạn.** Lệnh `schedule`/`exams` nhận tham số `mssv`. Hãy truyền MSSV của bạn.
- **Chỉ đọc.** Các endpoint ghi của đăng ký và hoãn thi (`tao-phieu-dang-ky`, `huy-phieu-dang-ky`, `cap-nhat-…`) đã được phát hiện trong bundle API nhưng **cố tình không** được bao bọc.
- **Thông tin đăng nhập không bao giờ bị commit.** `.env`, token và cookie đều được git-ignore.
- Không liên kết chính thức với HCMUT; đây là công cụ cộng đồng không chính thức.

## Kiểm thử & phát triển

Phần logic thuần túy (analysis, fees, env) có bộ kiểm thử pytest offline: không cần mạng, không cần tài khoản:

```bash
pip install -e ".[dev]"
python -m pytest tests -q
ruff check mybk_planner tests
```

CI chạy pytest + ruff + build wheel trên Python 3.10/3.11/3.12.

## Câu hỏi thường gặp

### Đây có phải công cụ chính thức của HCMUT không?

Không. Đây là client chỉ-đọc cộng đồng, không chính thức, cho cổng myBK.

### Tài khoản của tôi có an toàn không?

Công cụ chỉ đọc dữ liệu bằng chính thông tin đăng nhập của bạn, không sửa đổi gì và chỉ dùng cho tài khoản của chính bạn. Hãy chú ý giới hạn tốc độ của myBK.

### Tôi có thể dùng để xem dữ liệu của người khác không?

Không. Chỉ truyền MSSV của chính bạn. Các endpoint này không dùng để xem dữ liệu của tài khoản khác.

### Vì sao tổng tín chỉ của tôi khác với cộng dồn thô trong CTĐT?

Vì phần còn thiếu của một khối là tổng các dòng yêu cầu *riêng biệt*, và feed lặp lại giá trị yêu cầu trên mọi dòng môn học. Cộng dồn thô mọi môn tự chọn sẽ đếm thừa.

### Tôi vẫn đăng ký môn trên myBK chứ?

Có. Công cụ này chỉ tìm lớp và gợi ý kế hoạch; bạn luôn đăng ký qua cổng myBK chính thức.

## Giấy phép

[MIT](LICENSE) © 2026 Nguyễn Thành Danh
