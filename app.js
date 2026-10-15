const tag = (new URLSearchParams(location.search).get('tag') || '').trim().toUpperCase();
const result = document.getElementById('result');
const serial = document.getElementById('serial');
const count = document.getElementById('count');
const button = document.getElementById('confirm');
const message = document.getElementById('message');
let busy = false;
let requestId;
try {
  requestId = sessionStorage.getItem('pending-scan:' + tag);
} catch { /* The server still prevents duplicates for this page session. */ }
requestId ||= crypto.randomUUID();
async function request(record = false) {
  if (busy) return;
  busy = true;
  button.disabled = true;
  try {
    if (record) {
      try { sessionStorage.setItem('pending-scan:' + tag, requestId); } catch {}
    }
    const response = await fetch(record ? '/api/scan' : '/api/check?tag=' + encodeURIComponent(tag), record ? {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({tag, request_id: requestId})
    } : {cache: 'no-store'});
    if (!response.ok) throw new Error();
    const data = await response.json();
    if (record) {
      try { sessionStorage.removeItem('pending-scan:' + tag); } catch {}
    }
    result.textContent = data.eligible ? '資格符合' : '資格不符';
    result.className = data.eligible ? 'pass' : 'fail';
    count.textContent = data.count === null ? '' : `成功感應次數：${data.count} / 3`;
    button.hidden = record || !data.eligible;
    message.textContent = data.reason === 'unknown' ? '此序號不在核准名單中。' : record ? (data.recorded ? '本次感應成功，已保存紀錄。' : '已使用 3 次，本次資格不符。') : '請確認本次感應以取得最終結果。';
  } catch {
    result.textContent = '無法確認資格';
    result.className = 'fail';
    button.hidden = true;
    message.textContent = '無法取得伺服器結果。若您已送出感應，請重新整理查看次數，避免重複提交。';
  } finally {
    busy = false;
    button.disabled = false;
  }
}
if (tag) {
  serial.textContent = '序號：' + tag;
  request();
}
button.addEventListener('click', () => request(true));
