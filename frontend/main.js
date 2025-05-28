/*---------- 0. 基本設定 ----------*/
const API_BASE = 'http://157.230.41.208:5002';   // 後端根網址
const form     = document.getElementById('registerForm');
const pwd      = document.getElementById('password');
const confirm  = document.getElementById('confirm');
const errBox   = document.getElementById('pwdErr');

/*---------- 1. 事件監聽 ----------*/
form.addEventListener('submit', async (e) => {
  e.preventDefault();                            // 永遠攔表單，改用 JS fetch

  /* 1-1 前端欄位驗證 */
  if (pwd.value !== confirm.value) {
    errBox.style.display = 'block';
    return;
  }

  /* 1-2 組 JSON payload（欄位名稱一定要和後端一致！） */
  const payload = {
    username : document.getElementById('userid').value.trim(),
    name     : document.getElementById('name').value.trim(),
    email    : document.getElementById('email').value.trim(),
    password : pwd.value
  };

  try {
    /* 1-3 發送 POST /register */
    const res = await fetch(`${API_BASE}/register`, {
      method : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body   : JSON.stringify(payload)
    });

    if (!res.ok) {
      // 後端應回 {"msg":"帳號已存在"}，沒有就 fallback HTTP code
      const err = await res.json().catch(() => ({}));
      throw new Error(err.msg || `HTTP ${res.status}`);
    }

    alert('註冊成功！請前往登入頁');
    form.reset();                               // 清空表單
    window.location.href = 'login.html';        // 如有登入頁
  } catch (err) {
    alert(`註冊失敗：${err.message}`);
    console.error(err);
  }
});

/* 即時隱藏密碼不一致提示 */
confirm.addEventListener('input', () => { errBox.style.display = 'none'; });
