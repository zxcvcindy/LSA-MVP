<h1>PVE Pixie</h4>
<h2>動機與目的</h2>
<p>對於剛接觸 Linux 的使用者來說，在筆記型電腦上安裝虛擬機往往繁瑣又耗時：下載映像、配置硬體、安裝作業系統，還要額外佔用大量記憶體與儲存空間，不僅安裝時間拉長，每次啟動都會讓筆電過熱、效能下降。</p>
<p>為了解決這些痛點，我們打造了 <strong>PVE Pixie</strong> —— 一個基於 Proxmox VE 的雲端虛擬化平台。使用者只要透過瀏覽器，就能：</p>
<ul>
  <li><strong>快速建立</strong> 完全隔離、可自訂資源（CPU、記憶體、磁碟、網路）的虛擬機</li>
  <li><strong>即時管理</strong> 虛擬機的啟動、關機、重啟，以及 SSH 連線資訊</li>
  <li><strong>釋放本機資源</strong> 不再占用筆電大量效能與空間，也免去手動安裝與設定的麻煩</li>
</ul>
<p>透過 <strong>PVE Pixie</strong>，你可以隨時、隨地在雲端操作自己的 Linux 環境，專注於學習與開發，而不必再為虛擬機的安裝與維護煩惱。</p>
<h2>功能</h2>
<ul>
  <li>透過瀏覽器快速建立、啟動、關機及重啟虛擬機</li>
  <li>取得 SSH 連線指令與 IPv6 位址</li>
  <li>查看並管理所有使用者專屬虛擬機清單</li>
  <li>使用者註冊、登入與 JWT 驗證機制保障帳號安全</li>
  <li>RESTful API 介面，方便前端或第三方整合</li>
</ul>

<h2>硬體設備</h2>
<ul>
  <li>Proxmox VE 伺服器節點</li>
  <li>具有public IP的伺服器</li>
</ul>

<h2>第三方服務</h2>
<ul>
  <li><strong>Proxmox VE</strong>：底層虛擬化與 LXC/VM 管理</li>
  <li><strong>MySQL</strong>：使用者帳號與權限儲存</li>
  <li><strong>Flask-JWT-Extended</strong>：JWT 權杖驗證</li>
  <li><strong>Flask-CORS</strong>：跨域資源請求處理</li>
  <li><strong>nginx</strong>：反向代理與 HTTPS 支援</li>
</ul>

<h2>軟體需求及程式語言</h2>
<ul>
  <li><strong>後端</strong>：Python 3.10+, Flask</li>
  <li><strong>資料庫</strong>：MySQL</li>
  <li><strong>前端</strong>：HTML5, CSS3, JavaScript (Fetch API)</li>
  <li><strong>API 呼叫</strong>：requests 套件</li>
  <li><strong>程式語言</strong>：Python, JavaScript</li>
  <li><strong>其他工具</strong>：docker, Git</li>
</ul>
<h2>PVE 建立 cloud-init VM template</h2>
<h4>以 Ubuntu Server 為範例</h4>

<ol>
  <li>
    <strong>下載 Ubuntu Server 的 ISO 檔案</strong><br>
    <a href="[ISO 下載網址]">Download Ubuntu Server ISO</a><br>
    並放到 PVE 的 <code>/var/lib/vz/template/iso</code> 資料夾中，可以直接用以下指令：<br>
    <pre><code>wget -P /var/lib/vz/template/iso [ISO 下載網址]</code></pre>
  </li>

  <li>
    <strong>建立虛擬機器</strong><br>
    點選 <em>Create VM</em> 後，選擇剛剛下載的 ISO 檔案，依需求配置資源。建立完後先不要開機。
  </li>

  <li>
    <strong>設定 cloud-init 硬體</strong><br>
    1. 點選剛建立的虛擬機器，切換到 <em>Hardware</em> 分頁<br>
    2. 按 <em>Add &gt; CloudInit Drive</em>（保持預設設定即可）<br>
    3. 再按 <em>Add &gt; Serial Port</em>，序號填 <code>0</code>
  </li>

  <li>
    <strong>啟用 qemu-guest-agent 支援</strong><br>
    在 <em>Options</em> 分頁中找到 <em>QEMU Guest Agent</em>，將其狀態改為 <em>Enabled</em>。
  </li>

  <li>
    <strong>開啟虛擬機安裝 Ubuntu</strong><br>
    使用預設設定進行安裝（除非有特殊需求），安裝完成後系統會提示重新開機。
  </li>

  <li>
    <strong>安裝 qemu-guest-agent</strong><br>
    1. 重新開機後，以安裝過程中建立的使用者登入 Ubuntu<br>
    2. 執行：
    <pre><code>sudo apt update
sudo apt install -y qemu-guest-agent</code></pre>
    3. 安裝完成後重置 cloud-init 狀態：
    <pre><code>sudo cloud-init clean
sudo rm -rf /var/lib/cloud/</code></pre>
    這樣可以讓 cloud-init 在下一次啟動時重新執行，並正確載入 guest-agent。
  </li>

  <li>
    <strong>將這個虛擬機轉換為 Template</strong><br>
    關閉該 VM，然後在 Proxmox VE GUI 中對該 VM 按右鍵，選擇 <em>Convert to Template</em>。
  </li>
</ol>



<h2>工作分配</h2>
<ul>
  <li>111213023 謝逸驊 : 前後端連接、上台報告</li>
  <li>111213028 張嘉心 : PveAPI後端連接、上台報告</li>
  <li>111213033 朱邑旋 : PveAPI後端連接、上台報告</li>
  <li>特別感謝Josh的超強後援</li>
</ul>
<h2>參考資料</h2>
<ul>
  <li>Proxmox VE API Documentation:https://pve.proxmox.com/pve-docs/api-viewer/</li>
  <li>git:https://gitbook.tw/chapters/using-git/reset-commit#google_vignette</li>
</ul>
