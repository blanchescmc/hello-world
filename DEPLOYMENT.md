# NFC 資格查驗

三個核准標籤各自有 3 次成功額度，初始為 0。第 1、2、3 次提交成功並符合資格，第 4 次起不符合，成功次數維持 3。其他序號一律不符合。

## 啟動與測試

需要 Python 3.10 以上，不必安裝第三方套件。

```sh
cd /workspace/hello-world
python3 -m unittest -v test_server.py
python3 server.py
```

預設監聽本機 8001 埠。`PORT`、`NFC_HOST` 可調整監聽位置。資料庫預設為 `/workspace/nfc-data/counts.sqlite3`，也可用 `NFC_DB_PATH` 指定；必須是伺服器可寫入的持久儲存位置。初始化只補入缺少的標籤，不會重設次數。測試使用獨立臨時資料庫，不扣實際額度。

## 手機與標籤設定

### 使用容器部署

儲存庫提供 `Dockerfile`，可部署到支援容器及持久磁碟的平台：

```sh
docker build -t nfc-check .
docker volume create nfc-data
docker run -d --name nfc-check --restart unless-stopped -p 8001:8001 -v nfc-data:/data nfc-check
```

容器以非 root 使用者 UID 10001 執行。若主機使用 bind mount 或平台持久磁碟，需預先確保 `/data` 可由 UID 10001 寫入。平台可用 `PORT` 指定服務埠。對外服務需由平台或反向代理提供 HTTPS；健康檢查可使用 `GET /`，不應使用計次 API。不要把 SQLite 放在容器短暫檔案系統。

將 Python 服務部署在 HTTPS 反向代理後方，靜態檔案與 API 必須使用相同網域。GitHub Pages 無法執行這個後端。所有手機必須連到同一個服務及同一份持久資料庫；SQLite 適用單一主機，勿將多個各自持有資料庫的服務當成共同計數器。

假設正式網域為 `https://你的網域`，將以下三個完整網址分別寫為 NFC 標籤的 NDEF URL 記錄：

- `https://你的網域/?tag=53%3AD8%3A75%3A07%3A51%3A00%3A01`
- `https://你的網域/?tag=53%3AD9%3A75%3A07%3A51%3A00%3A01`
- `https://你的網域/?tag=53%3ADA%3A75%3A07%3A51%3A00%3A01`

開啟網址只查詢，不扣次數。按「確認本次感應」才提交並顯示最終結果。第三次提交仍顯示符合資格；再次開啟頁面會顯示額度已用盡。手機不會自動把 NFC UID 傳給網頁，需逐個標籤寫入正確網址。

## 計數及限制

伺服器以 SQLite 交易保證併發時最多成功 3 次，並保存請求編號，讓同一請求重送不會重複計次。瀏覽器暫存未確認完成的請求編號；請勿在網路結果不明時清除資料後重送。成功紀錄持久保存，重新啟動不會歸零。備份應使用 SQLite 備份工具或停機後複製資料庫；遺失資料庫即失去計數紀錄。

目前是序號額度查驗，不是防偽系統：知道網址的人可複製網址或直接呼叫 API 消耗額度。若必須證明感應實體原始標籤，需要可驗證動態簽章的 NFC 標籤及伺服器驗簽，單靠 UID 網址無法達成。
