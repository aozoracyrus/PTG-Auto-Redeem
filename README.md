# PTG Auto Redeem VN

Bot tự động nhập giftcode **Play Together (VNG)** cho nhiều ID người dùng Việt Nam.

Bot chạy hoàn toàn trên **GitHub Actions**, không cần máy chủ riêng, không cần cron.  
Bot lấy mã từ **YouTube**, nhập mã qua **API trực tiếp**, và gửi thông báo kết quả vào **Discord webhook**.

Phiên bản này chỉ hỗ trợ **VN**.

---

## 1. Bot làm gì?

Mỗi vòng lặp, bot sẽ:

1. Quét các video mới nhất trên kênh YouTube chính thức.
2. Tìm tiêu đề có chứa cụm từ:

   ```text
   CODE CHUNG
   ```

3. Lấy mã giftcode nằm ngay sau cụm từ đó.
4. Đợi một khoảng thời gian ngắn để server VNG kịp đồng bộ mã.
5. Gọi API redeem của VNG để nhập mã cho từng ID trong `id_user.txt`.
6. Gửi kết quả vào Discord:
   - Thành công: embed màu xanh.
   - Thất bại: embed màu đỏ.
   - Phát hiện mã mới: embed màu vàng.
   - Bot đang kẹt/không nhập được: embed màu cam, chỉ báo 1 lần mỗi run.
7. Lưu lại trạng thái những mã đã nhập để không nhập trùng.
8. Tự động chạy tiếp run mới sau khi run hiện tại kết thúc.

---

## 2. Điểm quan trọng cần hiểu trước

### 2.1. Bot không cần đăng nhập VNG

API redeem hiện tại không yêu cầu Cookie đăng nhập.

Dòng chữ trên web kiểu:

```text
Đăng nhập để rút ngắn thời gian nhập code và kiểm tra lịch sử
```

chỉ là gợi ý. Bot không phụ thuộc vào việc đăng nhập.

Bot chỉ cần quan tâm đến đăng nhập nếu API trả về mã lỗi:

```text
2101
```

nghĩa là tài khoản/ID chưa liên kết.

---

### 2.2. Lịch sử nhập của bot không giống giới hạn nhập của server

Bot lưu lịch sử vào file:

```text
code_da_nhap.txt
```

File này chỉ để bot biết:

```text
Mã X đã được thử cho ID Y chưa?
```

Còn việc mã đó còn lượt hay hết lượt là do **server VNG quyết định**.

Ví dụ:

- Bot nhập thành công mã `ABC` cho ID `123`.
- Server ghi nhận ID `123` đã dùng 1 lượt với mã `ABC`.
- Bạn xoá dòng `ABC|123` trong `code_da_nhap.txt`.
- Bot chạy lại và thử mã `ABC` cho ID `123`.

Kết quả vẫn có thể là:

```text
hết lượt nhập / usage limit
```

vì server vẫn nhớ lượt đã dùng.

=> Xoá file state chỉ làm bot gửi lại yêu cầu, không làm hồi sinh lượt nhập trên server.

---

### 2.3. Bot không tự giải captcha

Bot không có chức năng OCR hay auto-solve captcha.

Các biện pháp chống captcha của bot là:

- Random delay giữa mỗi lần nhập.
- Chỉ dùng 1 luồng browser fallback nếu cần.
- API-first để giảm tương tác web.
- Restart browser fingerprint khi browser fallback gặp captcha.

---

## 3. Cách bot hoạt động

### 3.1. Nguồn lấy mã: YouTube

Bot lấy mã từ kênh YouTube:

```text
https://www.youtube.com/@PlayTogetherVNGofficial/videos
```

Channel ID được dùng nội bộ:

```text
UCnLyxhAWS7yakzX8aWO6PKQ
```

Bot không dùng RSS feed của YouTube vì feed này hiện không trả về dữ liệu cho kênh.

Bot cũng không parse HTML trang YouTube theo cách cũ, vì trang có thể trả về shell rỗng và dữ liệu video được tải thêm bằng JavaScript.

Thay vào đó, bot dùng 2 tầng API:

#### Tầng 1: YouTube Data API v3

Đây là tầng bền nhất nếu bạn có API key.

Endpoint:

```text
https://www.googleapis.com/youtube/v3/playlistItems
```

Bot đọc tiêu đề video từ đường dẫn JSON cố định:

```text
items[].snippet.title
```

Nếu bạn cấu hình secret:

```text
YT_API_KEY
```

bot sẽ ưu tiên dùng tầng này.

#### Tầng 2: InnerTube

Đây là tầng mặc định, không cần bạn tạo API key.

Bot gọi:

```text
https://www.youtube.com/youtubei/v1/browse
```

InnerTube dùng key public của YouTube, không phải credential bí mật.

Bot vẫn cho phép ghi đè bằng secret:

```text
INNERTUBE_KEY
```

nếu bạn muốn repository sạch hơn về mặt cảnh báo secret scan.

Nhưng nếu bạn không set secret này, bot vẫn chạy bình thường nhờ key public mặc định.

---

### 3.2. Cách bot đọc mã từ tiêu đề YouTube

Bot giả định rằng NPH luôn ghi mã ngay sau cụm:

```text
CODE CHUNG
```

Ví dụ tiêu đề thật:

```text
PLAY TOGETHER VNG | CODE CHUNG PT26BATPET TRONG SỰ KIỆN HALLOWEEN
```

Bot sẽ lấy:

```text
PT26BATPET
```

Ví dụ:

```text
PLAY TOGETHER VNG | CODE CHUNG SWEETHALLOWEEN VÀ CÁ TRÁNG MIỆNG MỚI
```

Bot sẽ lấy:

```text
SWEETHALLOWEEN
```

Quy tắc:

1. Tìm cụm `CODE CHUNG`.
2. Lấy toàn bộ phần text phía sau.
3. Tách thành các token chỉ gồm chữ hoa ASCII và số: `A-Z0-9`.
4. Lấy token đầu tiên có độ dài từ `CODE_MIN_LEN` trở lên.

Mặc định:

```text
CODE_MIN_LEN = 6
```

Điều này giúp loại các từ tiếng Việt bị vỡ thành token ngắn, ví dụ:

```text
MỚI -> M
CỦA -> C
VÀ -> V
TRONG -> 5 ký tự
```

Đồng thời vẫn nhận được các mã kiểu:

```text
PT26BATPET
PT26HALLOWEEN
PTGIANTVEGGIE
SWEETHALLOWEEN
```

Bot chỉ xem 3 video mới nhất, nhưng gom nhóm theo mã để tránh việc một video tạo nhiều biến thể tiêu đề làm mất video khác.

---

### 3.3. Redeem qua API VNG

Bot gọi trực tiếp:

```text
POST https://vgrapi-sea.vnggames.com/coordinator/api/v1/code/redeem
```

Headers tối thiểu:

```http
Accept: application/json, text/plain, */*
Accept-Language: vi-VN,vi;q=0.9,en;q=0.6
Content-Type: application/json
Origin: https://giftcode.vnggames.com
Referer: https://giftcode.vnggames.com/
User-Agent: Mozilla/5.0 ... Mobile Safari/537.36
X-Client-Region: VN
X-Request-Id: <uuid>
```

Không cần Cookie.

Payload hiện tại:

```json
{
  "serverId": "2",
  "gameCode": "661",
  "roleId": "<ID_NHAN_VAT>",
  "roleName": "<ID_NHAN_VAT>",
  "code": "<MA_GIFTCODE>"
}
```

Giải thích:

| Trường | Ý nghĩa |
|---|---|
| `serverId` | Server của nhân vật. Hiện dùng `"2"` dạng string. |
| `gameCode` | Mã game nội bộ, hiện là `"661"`, không phải slug `ptg` trên URL. |
| `roleId` | ID nhân vật, ví dụ `4MFY-FMHL-LMGY`. |
| `roleName` | Tên role. Khi nhập ID tay, bot dùng chính ID làm `roleName`. |
| `code` | Giftcode cần nhập. |

---

### 3.4. Bot phán thắng/thua bằng errorCode

HTTP status không còn là căn cứ duy nhất.

Ví dụ:

- Thành công có thể là HTTP `200`.
- Thất bại nghiệp vụ cũng có thể là HTTP `200` hoặc `400`.

Do đó bot phán bằng `errorCode` trong JSON.

Bảng mã hiện tại:

| errorCode | Ý nghĩa | Bot xử lý |
|---:|---|---|
| `1` | Success | Thành công, gửi webhook xanh, chốt state |
| `2117` | Active code: usage limit | Thất bại hết lượt, gửi webhook đỏ, chốt state |
| `2106` | Code not found | Mã không tồn tại/sai mã |
| `2102` | Kiểm tra lại mã | Mã không tồn tại/sai mã |
| `2105` | Không tìm thấy nhân vật/offline | Lỗi theo ID, gửi webhook đỏ, chốt state |
| `2101` | Chưa liên kết tài khoản | Retry, không chốt failure |
| `1000`, `1001`, `2103` | Lỗi hệ thống tạm thời | Stuck/retry, không chốt failure |
| `1002` | Data invalid | Payload sai format, retry/khoá tạm, không chốt failure |

Với mã từ YouTube, nếu API trả `2106`/`2102`, bot hiểu rằng server có thể chưa đồng bộ mã kịp. Vì vậy bot không chốt failure ngay mà giữ trong queue và thử lại có giới hạn.

---

### 3.5. Queue và cooldown

Khi bot phát hiện mã mới từ YouTube, bot chưa vội nhập ngay.

Bot đưa mã vào:

```text
yt_queue.json
```

rồi đợi:

```text
YT_COOLDOWN = 60 giây
```

để server VNG kịp đồng bộ mã.

Sau đó bot mới thử redeem.

Nếu mã vẫn chưa được server chấp nhận, bot sẽ thử lại tối đa:

```text
YT_MAX_PROBE = 5 lần
```

Sau 5 lần vẫn chưa được, bot mới chốt failure và ghi chú là mã YouTube không đồng bộ kịp.

Cơ chế này tránh việc bot báo thất bại oan chỉ vì mã vừa được đăng lên YouTube nhưng chưa kịp lên server game.

---

### 3.6. Browser fallback

Mặc định bot dùng API:

```text
USE_API=1
```

Nên bot không mở browser.

Nếu bạn chuyển sang:

```text
USE_API=0
```

bot sẽ dùng Camoufox/Playwright để mở trang:

```text
https://giftcode.vnggames.com/vn/redeem/ptg
```

sau đó:

1. Điền mã.
2. Điền ID.
3. Chọn server best-effort.
4. Bấm nút nhập code.
5. Đọc kết quả qua tỉ số:
   - `1/1` = thành công.
   - `0/1` = thất bại.

Browser fallback chỉ là phương án dự phòng.

---

## 4. Cấu trúc repository

```text
.
├─ .github/workflows/redeem.yml
├─ requirements.txt
├─ .gitignore
├─ README.md
├─ id_user.txt
├─ code_da_nhap.txt
├─ yt_queue.json
├─ shots/.gitignore
└─ src/
   ├─ __init__.py
   ├─ config.py
   ├─ utils.py
   ├─ users.py
   ├─ state.py
   ├─ webhook.py
   ├─ parsers.py
   ├─ scraper.py
   ├─ api_redeemer.py
   ├─ redeemer.py
   ├─ browser_session.py
   ├─ youtube_watcher.py
   ├─ yt_queue.py
   └─ main.py
```

### File quan trọng

| File | Vai trò |
|---|---|
| `id_user.txt` | Danh sách ID người dùng cần nhập code |
| `code_da_nhap.txt` | Lịch sử mã đã nhập theo từng ID |
| `yt_queue.json` | Hàng đợi mã YouTube đang chờ đồng bộ |
| `src/config.py` | Cấu hình chính: API, payload, errorCode, YouTube, text lỗi |
| `src/main.py` | Vòng lặp chính |
| `src/youtube_watcher.py` | Lấy tiêu đề video từ YouTube |
| `src/parsers.py` | Trích mã từ tiêu đề YouTube |
| `src/api_redeemer.py` | Gọi API redeem VNG |
| `src/webhook.py` | Gửi Discord embed |
| `src/state.py` | Lưu và push state lên repo |
| `src/yt_queue.py` | Quản lý queue mã YouTube |

---

## 5. Cài đặt và chạy

### 5.1. Push repository

Đẩy toàn bộ cấu trúc lên nhánh `main`.

Commit sẵn 3 file state:

```text
code_da_nhap.txt
```

nội dung rỗng.

```text
yt_queue.json
```

nội dung:

```json
{}
```

```text
id_user.txt
```

chứa ID của bạn.

Ví dụ `id_user.txt`:

```text
# Mỗi dòng một ID. Có thể viết "VN - ID" hoặc ID trần.
VN - 4MFY-FMHL-LMGY
2JFA-Z4RL-LMYY
```

---

### 5.2. Cấu hình Secrets

Vào:

```text
Repository -> Settings -> Secrets and variables -> Actions
```

Tạo các secret sau.

| Secret | Bắt buộc? | Ý nghĩa |
|---|---:|---|
| `DISCORD_WEBHOOK` | Có | Webhook Discord để nhận thông báo |
| `PAT_TOKEN` | Khuyến nghị | Token để self-trigger run tiếp theo |
| `INNERTUBE_KEY` | Không | Key InnerTube public, chỉ để repository sạch cảnh báo |
| `YT_API_KEY` | Không | YouTube Data API v3 key, giúp nguồn YouTube bền hơn |

#### `PAT_TOKEN`

GitHub Actions có `GITHUB_TOKEN` mặc định, nhưng một số repo chặn token này tự trigger workflow đệ quy.

Vì vậy nên tạo Personal Access Token cổ điển hoặc fine-grained token có quyền:

```text
workflow
contents: read/write
actions: read/write
```

Rồi lưu vào secret:

```text
PAT_TOKEN
```

Workflow sẽ ưu tiên:

```text
secrets.PAT_TOKEN || github.token
```

---

### 5.3. Bật quyền ghi cho Actions

Vào:

```text
Settings -> Actions -> General
```

Chọn:

```text
Workflow permissions -> Read and write permissions
```

Nếu không bật, bot không push được:

```text
code_da_nhap.txt
yt_queue.json
```

---

### 5.4. Chạy bot

Vào:

```text
Actions -> PTG Auto Redeem VN -> Run workflow
```

Mỗi run sẽ sống tối đa khoảng 345 phút, sau đó tự trigger run kế tiếp.

Để dừng:

```text
Cancel run đang chạy
```

Run bị cancel sẽ không chạy tới bước self-trigger, nên chuỗi dừng.

---

## 6. Biến môi trường

Các biến nằm trong `.github/workflows/redeem.yml`.

| Biến | Mặc định | Ý nghĩa |
|---|---:|---|
| `REFRESH_INTERVAL` | `60` | Số giây giữa mỗi vòng quét |
| `MAX_RUNTIME` | `20700` | Thời lượng tối đa 1 run, tính bằng giây, khoảng 345 phút |
| `MIN_UPTIME` | `120` | Run phải sống tối thiểu bao nhiêu giây mới được nối tiếp |
| `DELAY_MIN` | `15000` | Delay tối thiểu giữa mỗi lần nhập, tính bằng ms |
| `DELAY_MAX` | `30000` | Delay tối đa giữa mỗi lần nhập, tính bằng ms |
| `YT_COOLDOWN` | `60` | Thời gian chờ server đồng bộ mã YouTube |
| `YT_MAX_PROBE` | `5` | Số lần thử lại tối đa cho mã YouTube chưa đồng bộ |
| `USE_API` | `1` | `1` là dùng API, `0` là dùng browser fallback |
| `YT_VERBOSE` | `0` | `1` là in tiêu đề video mỗi vòng |
| `DRY_RUN` | `0` | `1` là chỉ in payload, không gọi API, không webhook, không chốt |
| `TEST_CODE` | trống | Ép thử một mã cụ thể |

---

## 7. Kiểm tra an toàn trước khi chạy thật

### 7.1. Kiểm tra cú pháp Python

Trước khi push, chạy:

```bash
python -m py_compile src/*.py && echo "ALL SYNTAX OK"
```

Nếu thấy:

```text
ALL SYNTAX OK
```

thì file Python không lỗi cú pháp lúc import.

---

### 7.2. Xem bot có đọc được YouTube không

Set:

```yaml
YT_VERBOSE: "1"
```

Rồi chạy 1 vòng.

Log sẽ in ra các tiêu đề video đại diện, ví dụ:

```text
YT: 3 VIDEO MOI NHAT, tieu de dai dien:
   [ 1] PLAY TOGETHER VNG | CODE CHUNG SWEETHALLOWEEN ...
   [ 2] PLAY TOGETHER VNG | CODE CHUNG PT26BATPET ...
   [ 3] PLAY TOGETHER VNG | CODE CHUNG PT26HALLOWEEN ...
```

Nếu bạn thấy tiêu đề khớp với tab Videos trên YouTube, nghĩa là bot đã đọc đúng nguồn.

---

### 7.3. Xem payload bot sẽ gửi mà không đốt lượt

Set:

```yaml
DRY_RUN: "1"
TEST_CODE: "MA_CAN_TEST"
```

Bot sẽ in ra:

```text
DRY-RUN payload -> POST ... : {...}
```

Nhưng không gọi API thật, không gửi webhook, không chốt state.

Dùng mode này để đối chiếu payload với F12 Network tab khi cần.

---

### 7.4. Test redeem thật

Khi chắc chắn payload đúng và mã còn lượt:

```yaml
DRY_RUN: "0"
TEST_CODE: "MA_CON_LUOT"
```

Bot sẽ ép thử mã đó ngay.

Lưu ý:

- Mode này tiêu lượt thật.
- Chỉ dùng với mã bạn chấp nhận nhập thật.
- Sau khi test xong, xoá `TEST_CODE` để bot quay về chế độ chờ YouTube tự động.

---

## 8. Discord webhook

Bot gửi Discord dưới dạng embed.

### Thành công

Màu xanh:

```text
✅ Nhập thành công

Code "SWEETHALLOWEEN" đã nhập thành công cho ID "2JFA-Z4RL-LMYY"
```

### Thất bại

Màu đỏ:

```text
❌ Nhập thất bại

Code "SWEETHALLOWEEN" thất bại cho ID "4MFY-FMHL-LMGY" với lí do "hết lượt nhập / usage limit"
```

### Phát hiện mã mới

Màu vàng:

```text
🔔 Phát hiện code mới (YouTube)

Mã SWEETHALLOWEEN — đợi server sync ~60s trước khi thử nhập (không chốt failure sớm).
```

### Bot đang kẹt

Màu cam, chỉ gửi 1 lần mỗi run:

```text
⚠️ Bot đang kẹt

payload chưa xác nhận / HTTP 5xx / VNG khoá ...
(N code đang chờ trong queue, không chốt failure oan, sẽ tự thử lại ...)
```

Các trạng thái `retry`, `captcha`, `unknown` sẽ không gửi webhook cho từng ID để tránh spam.

---

## 9. Vận hành hằng ngày

### 9.1. Thêm ID

Sửa:

```text
id_user.txt
```

Mỗi ID một dòng.

Hỗ trợ:

```text
VN - 4MFY-FMHL-LMGY
```

hoặc:

```text
4MFY-FMHL-LMGY
```

ID phải theo dạng:

```text
XXXX-XXXX-XXXX
```

---

### 9.2. Reset lịch sử nhập

Xoá dòng tương ứng trong:

```text
code_da_nhap.txt
```

Hoặc xoá toàn bộ file nếu muốn bot thử lại tất cả.

Lưu ý quan trọng:

- Reset file này chỉ xoá lịch sử phía bot.
- Không reset được giới hạn lượt trên server VNG.
- Nếu mã đã hết lượt trên server, bot chạy lại vẫn sẽ nhận lỗi usage limit.

---

### 9.3. Dừng bot

Vào:

```text
Actions
```

Cancel run đang chạy.

Vì step self-trigger chỉ chạy khi run trước exit code `0`, cancel sẽ làm chuỗi dừng.

---

### 9.4. Khởi động lại bot

Vào:

```text
Actions -> Run workflow
```

---

## 10. Khi nào cần sửa bot?

### 10.1. NPH đổi cách ghi mã trên YouTube

Hiện bot giả định:

```text
CODE CHUNG <MA_LIEN_TUC>
```

Nếu sau này NPH đổi thành dạng khác, ví dụ:

```text
CODE CHUNG: ABC-123
```

hoặc:

```text
Mã chung là ABC123
```

bot có thể không trích đúng.

Khi đó kiểm tra log:

```text
YT: co "CODE CHUNG" nhung khong trich duoc code
```

hoặc:

```text
YT parse: nhay vụn dau ...
```

Rồi sửa:

```text
src/parsers.py
```

---

### 10.2. VNG đổi payload API

Nếu bot liên tục gặp:

```text
num=1002
msg='Data invalid'
```

nghĩa là payload bot gửi không khớp format server mong muốn.

Khi đó cần mở F12, xem request `redeem` thật, lấy tab Payload, rồi sửa:

```text
API_PAYLOAD_TEMPLATE
```

trong:

```text
src/config.py
```

---

### 10.3. VNG đổi errorCode

Nếu API trả mã mới chưa có trong bảng, bot có thể báo:

```text
ma loi chua map num=...
```

Khi đó mở rộng các set trong:

```text
src/config.py
```

ví dụ:

```python
NUM_USAGE
NUM_CODE_BAD
NUM_ID_ERROR
NUM_NEED_LOGIN
NUM_TRANSIENT
NUM_SUCCESS
```

---

### 10.4. YouTube đổi API nội bộ

Nếu InnerTube không trả tiêu đề, log sẽ có dạng:

```text
YT InnerTube DIAG: http=... videoId=...
string chua 'CODE CHUNG' = 0
```

Khi đó:

- Nếu có `YT_API_KEY`, bot sẽ ưu tiên Data API v3.
- Nếu không có key, cần cập nhật InnerTube params/context hoặc tạo Data API key.

Data API v3 là lựa chọn bền hơn vì được Google tài liệu hoá.

---

## 11. Xử lý lỗi thường gặp

| Triệu chứng | Nguyên nhân khả dĩ | Cách xử lý |
|---|---|---|
| Bot không gửi webhook | Chưa set `DISCORD_WEBHOOK` | Kiểm tra secret |
| Run đầu xong không tự chạy tiếp | `GITHUB_TOKEN` bị chặn self-trigger hoặc thiếu `PAT_TOKEN` | Tạo `PAT_TOKEN` scope `workflow` |
| Bot không push được state | Chưa bật Read and write permissions | Settings -> Actions -> Workflow permissions |
| Log `yt_queue file hong` | `yt_queue.json` không phải `{}` hợp lệ | Bot sẽ tự ghi lại `{}`; lần sau sạch |
| Log `!! PUSH FAIL` | Quyền ghi/token/scope có vấn đề | Kiểm tra `PAT_TOKEN`, quyền contents/actions |
| Bot báo 0 title YouTube | Thiếu key, YouTube đổi API, hoặc kênh chưa có video mới | Bật `YT_VERBOSE=1`, kiểm tra log InnerTube/DataAPI |
| Bot gặp `num=1002` lặp | Payload sai | Lấy raw payload từ F12 và sửa `API_PAYLOAD_TEMPLATE` |
| Bot gặp `num=2117` | Mã hết lượt | Bình thường, không phải lỗi bot |
| Bot gặp `num=2106` với mã YouTube mới | Server chưa đồng bộ kịp | Bot sẽ retry theo queue/cooldown |
| Bot gặp `num=2101` | ID chưa liên kết tài khoản | Cần kiểm tra phía tài khoản/game |
| Mã mới không được nhập | Chưa qua cooldown 60s | Đợi vòng sau |
| Webhook đỏ lặp lại sau khi xoá state | Server vẫn tính lượt cũ | Xoá state không hồi sinh lượt nhập |

---

## 12. Ghi chú bảo mật

- Không commit Cookie đăng nhập VNG.
- Không commit API key YouTube Data API thật.
- `INNERTUBE_KEY` mặc định là key public của YouTube, không phải credential cá nhân.
- `PAT_TOKEN` có quyền rộng, chỉ nên lưu trong GitHub Secrets.
- Nếu vô tình push key thật vào repo public, cần revoke/rotate key ngay và dọn git history.

---

## 13. Ghi chú pháp lý và rủi ro

Bot này tự động hoá việc nhập giftcode. Việc tự động hoá có thể vi phạm điều khoản sử dụng của game hoặc nền tảng.

Giftcode có giới hạn lượt, thời gian và số lượng.

Các cơ chế delay, cooldown, API-first, single-browser fallback nhằm giảm tải và giảm rủi ro captcha, không nhằm vượt rào hệ thống.

Bạn tự chịu trách nhiệm khi vận hành bot.

---

## 14. Tóm tắt nhanh

```text
YouTube video title
   ↓
Tìm "CODE CHUNG"
   ↓
Lấy token mã phía sau
   ↓
Đợi 60s cho server đồng bộ
   ↓
Gọi API redeem VNG
   ↓
Đọc errorCode
   ↓
Gửi Discord embed
   ↓
Lưu state CODE|ID
   ↓
Tự chạy run tiếp theo
```

Bot hiện tại:

- Chỉ VN.
- API-first.
- Không cần Cookie.
- Không parse RSS/HTML YouTube theo cách cũ.
- Có queue chống báo failure sớm.
- Có Discord embed.
- Có self-chain 24/7 qua GitHub Actions.
