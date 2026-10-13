# PTG Auto Redeem VN — Play Together (VNG), GitHub Actions 100%, API‑first + YouTube early‑warning

Bot nhập giftcode **Play Together** cho dàn ID tiếng Việt qua **API trực tiếp**, gửi kết quả
qua **Discord webhook**, tự nối tiếp run 24/7 (không cron, không server riêng). **Chỉ VN** (đã rút TH).

- Repo **PUBLIC** → miễn phí, không tính quota. **PRIVATE** → ~710 h/tháng (< 2 000 h).

## Cơ chế redeem (cách ae tìm ra qua F12)
- **Đường chính = API:** `POST https://vgrapi-sea.vnggames.com/coordinator/api/v1/code/redeem`.
  F12 tố Request Headers **KHÔNG có Cookie** → redeem **không cần đăng nhập** ở tầng API
  (khớp knowledge base: *"Đăng nhập để rút ngắn thời gian nhập code và kiểm tra lịch sử"* = optional;
  bot tự quản lịch sử qua `code_da_nhap.txt` nên càng không cần login). Headers tối thiểu:
  `X-Client-Region: VN`, `Origin/Referer`, `Accept-Language: vi-VN`, `User-Agent` mobile,
  `X-Request-Id`. `Baggage`/`Sentry-Trace` là telemetry → bỏ được.
- **Phán quan thắng/thua của API = MÃ SỐ JSON** (1000/1001/1002/2101/2102/2103/2105 từ blob i18n)
  → language‑proof tuyệt đối. Tỉ số `1/1`/`0/1` **chỉ** dùng cho browser‑fallback (`USE_API=0`).
- **Payload** tab F12 chưa chụp → template `{gameCode,code,roleId,serverId,region}` (ước byte khớp 107)
  + **tự chẩn đoán**: mã `1002` lặp ⇒ log `PAYLOAD SAI`, retry **không chốt** (không mất code).
- **Browser fallback** (`redeemer.py`): mở `/vn/redeem/ptg`, điền code+ID, chọn server best‑effort,
  bấm nút, poll tỉ số `1/1`/`0/1`. Captcha → restart fingerprint mới, retry 1 lần, vẫn captcha → skip không chốt.

## Parse giftcode (2 nguồn, không cần số / không dựa ngoặc)
- **Web‑modal VN:** neo = **dòng ngày `dd/mm/yyyy`** (không bị dịch), lấy token in‑hoa ASCII ≤2 dòng
  phía trước → heading code. Chạy được dù label tiếng Việt là "Có hiệu lực đến"/bất kỳ.
- **YouTube:** title chứa **`CODE CHUNG`** → lấy token mở đầu prefix **`PT`** ngay sau keyword.
  10% đen → thêm tiền tố vào `CODE_PREFIXES` (không bao giờ sửa độ dài). Resolve channel id từ
  `/@handle/videos` (đúng danh mục Video, không phải trang chủ), cache vào `yt_channel_id.txt`.

## Self‑chain (trigger đã gộp vào `.yml`, không còn `src/trigger.py`)
`redeem.yml` có step `Trigger next run` dùng `gh workflow run`, `if: success()`. Gate bằng exit code:
`main.py` exit `0` (loop êm, runtime ≥ `MIN_UPTIME`) ⇒ step trigger chạy ⇒ spawn run kế;
exit `2` (fail sớm/crash) ⇒ step Run loop đỏ ⇒ step trigger **bỏ qua** ⇒ chuỗi dừng (không spam).
`concurrency: cancel-in-progress:false` ⇒ run mới pending chờ run cũ finish ⇒ 1 browser duy nhất.

## Bật chạy
1. Push cấu trúc lên `main`. Commit 4 file state/rỗng: `code_da_nhap.txt`(rỗng), `yt_queue.json`(`{}`),
   `yt_channel_id.txt`(rỗng), `id_user.txt`.
2. **Secrets → Actions**: `DISCORD_WEBHOOK`; `PAT_TOKEN` (scope **workflow** + Contents/Actions read&write —
   `GITHUB_TOKEN` bị chặn đệ‑quy ở nhiều repo ⇒ self‑trigger fail ⇒ chuỗi đứt sau run đầu; step trigger
   tự fallback `secrets.PAT_TOKEN || github.token`).
3. **Settings → Actions → General → Workflow permissions = Read and write**.
4. **Actions → … → Run workflow**. Mỗi run sống 345′ rồi step trigger tự spawn run kế → 24/7.
   Dừng: Cancel run đang chạy (cancel không chạy tới step trigger ⇒ không self‑chain).

## 3 việc anh làm sau lần chạy đầu (nếu log báo)
- **`PAYLOAD SAI` (mã 1002 lặp)** → mở F12 tab **Payload**, copy raw JSON, dán đúng vào
  `API_PAYLOAD_TEMPLATE` trong `config.py`.
- **`nút 'View…' KHÔNG hiện`** → wording VN của nút khác regex; soi Elements 1 lần, thêm string
  vào `BTN_VIEW_CODES`.
- **`UNKNOWN`** (browser fallback) → mở screenshot `unknown-VN-*.png` / đọc `body[:500]` trong log,
  bổ sung chuỗi vào table text tương ứng.

## id_user.txt
Mỗi dòng 1 ID (`VN - ID` hoặc ID trần, 4‑4‑4). `#` = comment. Thêm dàn ID cứ thêm dòng.

## Webhook (VN)
- Success: `Code "<X>" đã nhập thành công cho "<ID>"`
- Failure: `Code "<X>" đã thất bại với lí do "<lí do>"`
- YT alert: `🔔 YouTube phát hiện "CODE CHUNG" -> mã \`X\`. Đợi server sync ~60s…`
- `retry`/`captcha`/`unknown` → **im lặng, thử lại** (không gửi, không chốt → không mất code, không spam).

## Env (trong redeem.yml)
`REFRESH_INTERVAL`(60) `MAX_RUNTIME`(20700=345′) `MIN_UPTIME`(120) `DELAY_MIN/MAX`(15000/30000)
`YT_COOLDOWN`(60) `YT_MAX_PROBE`(5) `USE_API`(1). Constant parse ở `config.py` (`CODE_PREFIXES`,
`KEYWORD_PATTERN`, `NUM_*`, table text…).

## Rủi ro / pháp lý
Tự động hoá có thể vi phạm ToS; giftcode có giới hạn. Delay + 1 browser + cooldown + API‑first nhằm
**giảm** tải và tránh captcha, không nhằm vượt rào. **Không auto‑solve captcha** (cookie login chỉ để
*giảm* captcha, không phải OCR). Bạn tự chịu trách nhiệm vận hành.
