# PTG Auto Redeem (Play Together · VNG) — GitHub Actions 100%, YouTube early-warning, parse theo PREFIX + NEO

Bot quét giftcode **Play Together** trên `giftcode.vnggames.com`, **đồng thời soi kênh YouTube
chính thức** để biết code sớm hơn vài phút, nhập cho dàn ID đa vùng (TH/VN), gửi kết quả qua
**Discord webhook**, và **tự nối tiếp run** để chạy 24/7 — không server riêng, không cron.

- **Repo PUBLIC** → miễn phí, không tính quota. **Repo PRIVATE** → ~710 h/tháng (< 2 000 h).

---

## 0. Bốn nguyên tắc sống còn

| # | Nguyên tắc | Vì sao |
|---|---|---|
| 1 | **Delay 15–30s GIỮA MỖI LẦN NHẬP** (không phải giữa reload) | Dàn ID đông + nhập nhanh = captcha. 15–30s ngẫu nhiên gần như triệt tiêu. |
| 2 | **Code từ YouTube KHÔNG BAO GIỜ ghi failure “không tồn tại” vào state** | Server chưa sync → nhập sớm ăn “không tồn tại” → nếu chốt state thì MẤT code thật. |
| 3 | **Cooldown `YT_COOLDOWN` (60s) trước khi probe code YT** | “Từ từ 30s–1p cho code đến server”. |
| 4 | **Parse giftcode theo ĐẶC TRƯNG (prefix / neo cấu trúc), KHÔNG theo độ dài, KHÔNG cần số, KHÔNG dựa ngoặc** | Code có thể toàn chữ (`PTGIANTVEGGIE`) và ngắn (`PT26`); title thật không có `""`/`()`. |

---

## 1. Giftcode ≠ ID người dùng (đừng lẫn)

| | **Giftcode** (mã thưởng) | **ID người dùng** |
|---|---|---|
| Format | **KHÔNG cố định**, CÓ THỂ không có số & ngắn (`PTGIANTVEGGIE`, `PT26BATPET`, `PT26`, `PT`) | **LUÔN** `4-4-4` (`A6PK-4KPL-WENL`) |
| Đến từ | Web-modal (`Valid until …`) **+** title YouTube (`CODE CHUNG <code>`) | File `id_user.txt` |
| Nhập vào ô | `PH_CODE` (*Enter redemption code* / *Nhập thông tin code*) | `PH_ID` (*Chọn nhân vật / Nhập ID nhân vật*) |
| Nhận diện bằng | 2 hàm trong `parsers.py` (mục 2) | `ID_RE` (khuôn cứng, chỉ validate dòng file) |

Hai vùng dữ liệu tách đôi → không bao giờ nhét giftcode vào ô ID hay ngược lại. Thứ tự dòng trong
`id_user.txt` = thứ tự bot xử lý (block VN trước / TH sau nếu muốn VN ưu tiên khi code chạm
usage-limit); region mỗi dòng quyết định trang nhập (`/vn` hay `/th`), độc lập với thứ tự.

---

## 2. Parse giftcode: PREFIX cho YouTube, NEO “Valid until” cho web — không độ dài, không số

### Tại sao keyword là `CODE CHUNG`
Quy ước title kênh PT VNG rất ổn định: **video CÓ giftcode cộng đồng luôn ghi cụm `CODE CHUNG`,
và mã nằm NGAY SAU cụm đó.** Video không code thì không bao giờ có cụm này → `CODE CHUNG` vừa là
**bộ lọc nhiễu** (loại ~90% video), vừa là **neo định vị**. `""`/`()` quanh code **KHÔNG** phải một
phần title (chỉ là cách nhấn mạnh khi chat) → bot **không** dựa vào ngoặc.

### Tại sao KHÔNG dùng “độ dài ≥ 6” hay “phải có số”
Cả hai đều là proxy YẾU và đều **giết code thật**: `PT26` (4 ký tự) rớt vì độ dài;
`PTGIANTVEGGIE` (toàn chữ) rớt vì không số. Thay bằng **đặc trưng cứng**:

| Nguồn | Neo | Bộ lọc | Code ngắn/không-số? |
|---|---|---|---|
| YouTube title | cụm `CODE CHUNG` | token in-hoa **mở đầu prefix `PT`** đứng ngay sau keyword (skip mọi rác `( ) " : space`) | ✅ `PT26`, `PT` vẫn lấy; `UPDATE`/`NGAY`/`VNG` bị chặn vì không mở đầu PT |
| Web modal | dòng `Valid until <ngày>` | token in-hoa **liền trước** mỗi `Valid until` (`[A-Z0-9]+`, min 1, KHÔNG re.I, KHÔNG prefix) | ✅ lấy được cả code 1 ký tự |

Vì sao web sạch mà **không cần blacklist & không cần prefix**? Regex token **không bật `re.I`** →
chỉ khớp chữ IN-HOA, nên mọi label Title-case/thường (`Selected`, `Quick select`, `Clear selection`,
`Coming soon`, `Enter code`, `Check`) tự rớt; `PROMOTIONS` (in-hoa) đứng trước `Coming soon` chứ
**không** trước `Valid until` → `findall` theo neo không bắt nó. Code PT luôn in-hoa nên qua.

Vì sao YouTube cần prefix còn web thì không? Title YouTube là **câu tự do** (lẫn từ sự kiện in-hoa
không dấu như `NGAY`, `RAU`, `CU`, `VNG`…) → cần tường chắn thương hiệu `PT`. Web-modal có **cấu
trúc chặt** (code heading luôn kề `Valid until`) → bản thân neo đã là tường chắn, không cần prefix.

### 10% đen: thêm prefix, KHÔNG bao giờ sửa độ dài
Nếu NPH ra brand code mới (VD tiền tố `TE`), chỉ cần `CODE_PREFIXES = ["PT", "TE"]` trong
`config.py` — regex build tự cập nhật, code ngắn‑dài gì cũng lấy, từ sự kiện vẫn bị chặn. Muốn
cực đoan “lấy mọi token in-hoa bất kể prefix” thì đặt `CODE_PREFIXES = []` (fallback `[A-Z0-9]+`
min 1); đổi lại YT sẽ thỉnh thoảng lấy nhầm từ tiếng Việt bị‑cắt‑dấu, nhưng flow YT (cooldown +
không ghi failure sớm + max‑probe + suppress webhook khi `not_exist`) gặm số noise đó mà **không
mất code thật, không spam webhook**. Mặc định prefix ON vì sạch.

### Lưới an toàn 2 nguồn
Hai bộ lọc khác độ chặt nên code khó mất:

| Loại code | YouTube (prefix PT) | Web (neo, min 1) | Kết cục |
|---|---|---|---|
| Ngắn, có PT (`PT26`) | ✅ | ✅ | lấy chắc |
| Dài, có PT (`PTGIANTVEGGIE`) | ✅ | ✅ | lấy chắc |
| Ngắn/không‑PT (`X9`, `OCT26`) | ❌ rớt | ✅ cứu | **web cứu** |
| Không tồn tại trên hệ thống | fail not_exist → probe → timeout | không hiện | bỏ đúng |

⇒ Mất code thật giờ đòi code *vừa* không‑PT *vừa* không‑hiện‑trên‑web — tức không tồn tại, có lấy cũng fail.

### Edge cần biết
- **Web neo dùng “Valid until”** vì scraper đọc trang **TH** (modal tiếng Anh, đúng hình bạn gửi).
  Nếu sau này chuyển scraper sang trang VN và modal dịch khác wording → sửa đúng
  `_WEB_BEFORE_VU` trong `parsers.py`.
- **Positional YT** giả định code ngay sau `CODE CHUNG`. Nếu NPH chèn chữ giữa (hiếm theo quy ước),
  YT rớt → web cứu.
- **`TOKEN_MIN_LEN` đã bị XOÁ** khỏi codebase — không còn constant độ dài để edit; bộ lọc giờ là
  đặc trưng cấu trúc, bền với mọi độ dài.

---

## 3. Vòng đời một code YouTube (queue `yt_queue.json`)

```
YT thấy title có "CODE CHUNG" + trích được mã X (positional + prefix)
        │  (X chưa trong queue & chưa fully-done)
        ▼
   queue[X] = {first_seen: now, probes: 0}   +   webhook 🔔 alert "chờ sync" (1 lần)
        │
   mỗi vòng, nếu now-first_seen >= YT_COOLDOWN(60s):
        ├─ X ĐÃ có trên web  ──► redeem source=web ──► chốt state MỌI outcome ──► xoá queue
        └─ X CHƯA có trên web ──► probe source=yt:
                ├─ success / usage limit ──► chốt state ──► xoá queue
                ├─ captcha               ──► skip, giữ queue, probes KHÔNG đổi
                └─ "không tồn tại"/other ──► KHÔNG chốt, KHÔNG webhook, probes += 1
                        ├─ probes <  YT_MAX_PROBE ──► giữ queue, retry vòng sau
                        └─ probes >= YT_MAX_PROBE ──► force-commit failure, xoá queue
```

`is_code_fully_done(X)` = mọi cặp `X|ID` đã ở state → video cũ vẫn trong top‑N RSS nhưng bot
**không re‑queue** (chống alert/probe trùng).

---

## 4. Refresh = reload trình duyệt thật (Camoufox)

Giữ **1** Camoufox + 1 context + 1 scan‑page xuyên suốt; mỗi `REFRESH_INTERVAL` (30/60s) gọi
`scan_page.reload()` (= F5) → bấm *View available redemption codes* → parse bằng neo `Valid until`
→ **đóng bottom‑sheet (Escape)** → trả codes. **Không** mở context mới mỗi vòng (fingerprint nhảy =
tự rước captcha). Gặp captcha mới `restart()` = mở browser fingerprint mới (= “xoá trình duyệt vào
lại”), retry 1 lần; vẫn captcha → **skip cặp đó, KHÔNG ghi state** → vòng sau thử lại.

---

## 5. Cấu trúc thư mục

```
.
├─ .github/workflows/redeem.yml
├─ requirements.txt   .gitignore
├─ id_user.txt        # region - ID(4-4-4)        ← BẠN SỬA (block VN trước / TH sau nếu muốn)
├─ code_da_nhap.txt   # STATE "CODE|ID"            (commit rỗng)
├─ yt_queue.json      # QUEUE {code:{first_seen,probes}}  (commit '{}')
├─ yt_channel_id.txt  # cache UC...                 (commit rỗng, bot tự điền)
├─ shots/.gitignore
└─ src/  __init__.py  config.py  utils.py  users.py  state.py  webhook.py  trigger.py
        browser_session.py  parsers.py  scraper.py  youtube_watcher.py  yt_queue.py
        redeemer.py  main.py
```

---

## 6. Cài đặt & bật chạy

1. Push cấu trúc lên `main`. Commit **4 file state/rỗng**: `code_da_nhap.txt` (rỗng),
   `yt_queue.json` (`{}`), `yt_channel_id.txt` (rỗng), `id_user.txt`.
2. **Settings → Secrets → Actions**:
   - `DISCORD_WEBHOOK` = URL webhook.
   - `PAT_TOKEN` *(khuyến nghị)* = PAT scope **workflow** (+ `repo` nếu private) hoặc fine‑grained
     **Actions: Read&write** + **Contents: Read&write**. Không set thì fallback `GITHUB_TOKEN` —
     nhưng `GITHUB_TOKEN` bị chặn đệ‑quy ở nhiều repo ⇒ self‑trigger fail ⇒ chuỗi đứt sau run đầu.
3. **Settings → Actions → General → Workflow permissions = Read and write**.
4. **Actions → PTG Auto Redeem (Camoufox + YouTube watcher) → Run workflow** (kích hoạt lần đầu).
5. Mỗi run sống 345′ rồi tự gọi API spawn run kế → 24/7, không cron.

**Dừng chuỗi:** *Actions → run đang chạy → Cancel* (cancel không chạy tới `finally` ⇒ không
self‑trigger). Hoặc xoá/đổi sai `PAT_TOKEN`, hoặc đặt `MIN_UPTIME` thật lớn.

### Lấy Channel ID (nếu auto‑resolve fail)
Bot tự resolve từ `https://www.youtube.com/@PlayTogetherVNGofficial` và cache vào
`yt_channel_id.txt`. Nếu HTML đổi cấu trúc (log: *chưa có channel id*), lấy tay:
```bash
curl -s "https://www.youtube.com/@PlayTogetherVNGofficial" \
  | grep -oP '"channelId":"\K[^"]+' | head -n 1
# hoặc mở /about, nhìn "Channel ID" (UC...), dán vào yt_channel_id.txt, commit.
```

---

## 7. Bảng biến môi trường (chỉnh trong `redeem.yml`)

| Var | Mặc định | Ý nghĩa |
|---|---|---|
| `REFRESH_INTERVAL` | 60 | giây giữa 2 lần **reload** trang (30 hoặc 60) |
| `MAX_RUNTIME` | 20700 | giây 1 job sống (345′ < trần 360′, chừa 15′ buffer) |
| `MIN_UPTIME` | 120 | guard: run phải sống ≥ cỡ này mới được nối tiếp (chống fail‑loop) |
| `DELAY_MIN`/`DELAY_MAX` | 15000/30000 | ms delay ngẫu nhiên **giữa mỗi lần nhập** (chống captcha) |
| `YT_COOLDOWN` | 60 | giây chờ server sync trước khi probe code YT |
| `YT_MAX_PROBE` | 5 | số lần probe code‑YT‑chưa‑sync trước khi bỏ cuộc |

Constant parse (không phải env, sửa trong `config.py`): `CODE_PREFIXES` (mặc định `["PT"]`),
`KEYWORD_PATTERN`/`YT_KEYWORD_RE` (`CODE CHUNG`), `YT_TOP_ENTRIES` (3).

---

## 8. Đăng nhập (tuỳ chọn — bớt captcha + có lịch sử)

Trang VN có box *“Đăng nhập để rút ngắn thời gian nhập code và kiểm tra lịch sử nhập code bất cứ
lúc nào”*. **Login KHÔNG bắt buộc** để redeem (form vẫn hiện, bot nhập được vô tư), nhưng phiên đã
auth được server tin ⇒ **ít captcha hơn** (cộng hưởng delay 15–30s) + có lịch sử đối chiếu. Bật:
```bash
python - <<'PY'
from camoufox.sync_api import Camoufox
with Camoufox(headless=False) as b:
    ctx = b.new_context(); p = ctx.new_page()
    p.goto("https://giftcode.vnggames.com/vn/redeem/ptg")
    input("Đăng nhập xong thì Enter..."); ctx.storage_state(path="auth.json")
PY
```
Commit `auth.json` **vào repo PRIVATE** (`.gitignore` đã chặn; muốn commit thì bỏ dòng đó), rồi đặt
`STORAGE_STATE = "auth.json"` trong `config.py`. **Login không đụng tới 2 hàm parse** — parse chỉ
đọc text trên màn hình (tầng *parse*), login chỉ ảnh hưởng tần suất captcha/lịch sử (tầng *giao
dịch*). Hai tầng tách biệt, bật/tắt login thoải mái không phải chỉnh regex.

---

## 9. Webhook message (đúng nguyên văn spec + alert YT)

| Loại | TH | VN |
|---|---|---|
| Success | `Code "<X>" enter success for "<ID>"` | `Code "<X>" đã nhập thành công cho "<ID>"` |
| Failure | `Code "<X>" enter failure with reason "<lí do>"` | `Code "<X>" đã thất bại với lí do "<lí do>"` |
| YT alert | `🔔 YouTube phát hiện "CODE CHUNG" -> mã \`X\`. Đợi server sync ~60s…` | (chung 1 câu) |

Success & failure **cùng 1 webhook**. Lí do failure = nguyên văn chuỗi VNG (`usage limit` /
`does not exist` / exception / DOM‑miss) hoặc `YT code không sync sau N lần thử`. **Probe YT fail
“không tồn tại” KHÔNG gửi webhook** (chống noise khi đang chờ sync).

---

## 10. Chỗ phải chỉnh sau lần chạy đầu

| Triệu chứng | Sửa ở đâu |
|---|---|
| Web‑list thiếu/sai code | `parsers._WEB_BEFORE_VU` (neo `Valid until` đổi wording / chuyển trang VN) |
| YT không ra code dù có video | `config.YT_KEYWORD_RE`/`KEYWORD_PATTERN` (đổi/thêm từ khoá) hoặc `config.CODE_PREFIXES` (thêm tiền tố 10% đen) |
| Code bị rớt vì không mở đầu PT | thêm tiền tố vào `config.CODE_PREFIXES` (KHÔNG sửa độ dài — không còn constant đó) |
| `fillfail-*` screenshot | `config.PH_CODE` / `PH_ID` |
| Không bấm được nút | `config.BTN_REDEEM` / `BTN_VIEW_CODES` |
| Thành công nhưng báo `unknown` | `config.OK` / `FAIL` |
| Phải chọn Server mới bật nút | thêm `page.get_by_text("Server 2").click()` trước đoạn fill trong `redeemer._attempt` |
| Resolve channel id fail | dán UC… tay vào `yt_channel_id.txt` (§6) |
| Captcha **mọi lần** (không do spam) | bật login (§8); hoặc OCR hook ở nhánh `return {"status":"captcha"}` trong `redeemer` |

Nguyên tắc: **constant hay đổi ở `config.py`, logic parse ở `parsers.py` (comment từng mảnh regex
tiếng Việt), phần còn lại không đụng.**

---

## 11. Troubleshooting nhanh

- **Chuỗi đứt sau run đầu** → log step *Run loop*: `self-trigger HTTP 403` ⇒ chưa set `PAT_TOKEN`
  hoặc thiếu scope workflow/Actions‑write.
- **`web fetch được 0 giftcode` hoài** → trang đòi login (§8) hoặc neo `Valid until` đổi wording.
- **`YT watcher: CHƯA có channel id`** → resolve fail, dán UC… tay (§6). Bot vẫn chạy web‑only.
- **`yt-probe … 'not_exist' (chưa sync, giữ retry)`** → BÌNH THƯỜNG, bot đang chờ server; sẽ tự
  chốt success khi web sync.
- **`YT timeout: X sau 5 probes -> bỏ cuộc`** → mã trong title YT không hề tồn tại trên hệ thống
  (YouTuber ghi sai / code kênh khác). Đã chốt failure để khỏi probe mãi.
- **Code không số / code ngắn bị rớt?** → KHÔNG còn xảy ra: parse mới không dùng “có số” và không
  dùng độ dài. Nếu vẫn rớt, kiểm tra `CODE_PREFIXES` (code không mở đầu PT → thêm tiền tố) hoặc
  neo web (`_WEB_BEFORE_VU`).
- **Test local**: `pip install -r requirements.txt && python -m camoufox fetch` rồi
  `REFRESH_INTERVAL=30 MAX_RUNTIME=180 DELAY_MIN=2000 DELAY_MAX=4000 python src/main.py`
  (set `DISCORD_WEBHOOK`/`GITHUB_TOKEN` qua env; không token thì state chỉ ghi local, không push).

---

## 12. Lưu ý pháp lý / rủi ro

Bot mô phỏng thao tác người dùng trên trang VNG; tự động hoá có thể vi phạm ToS nhà phát hành, và
giftcode có giới hạn sử dụng. Bạn tự chịu trách nhiệm vận hành. Delay 15–30s + 1 browser duy nhất
+ cooldown YT được thiết kế để **giảm** tải và tránh captcha, không nhằm vượt rào giới hạn.
