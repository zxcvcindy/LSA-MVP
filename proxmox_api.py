import time
import requests
import requests.packages.urllib3

requests.packages.urllib3.disable_warnings()

PVE_HOST = "10.32.1.100"
USER = "root@pam!LSAlab"
TOKEN = "c9bc7679-c908-48f1-957c-17addd105dae"
NODE         = "pve"    # Proxmox 節點名稱
TEMPLATE_ID  = 100      # 範本 VM ID
VERIFY_SSL   = False    # 自簽憑證用 False；正式環境請改 True

BASE_URL = f"https://{PVE_HOST}:8006/api2/json"

HEADERS = {
    "Authorization": f"PVEAPIToken={USER}={TOKEN}"
}

def get_nodes():
    url = f"{BASE_URL}/nodes"
    response = requests.get(url, headers=HEADERS, verify=False)
    return response.json()

def start_vm(node, vmid):
    url = f"{BASE_URL}/nodes/{node}/qemu/{vmid}/status/start"
    response = requests.post(url, headers=HEADERS, verify=False)
    return response.json()

def stop_vm(node, vmid):
    url = f"{BASE_URL}/nodes/{node}/qemu/{vmid}/status/stop"
    response = requests.post(url, headers=HEADERS, verify=False)
    return response.json()

def delete_vm(node, vmid):
    url = f"{BASE_URL}/nodes/{node}/qemu/{vmid}"
    response = requests.delete(url, headers=HEADERS, verify=False)

    if response.status_code == 200:
        return {"data": response.text.strip()}
    else:
        return {
            "error": f"Delete VM failed. Status {response.status_code}",
            "details": response.text
        }

def wait_for_task(node: str, upid: str, timeout: int = 600) -> None:
    """輪詢 Proxmox 任務直到完成；失敗時丟出例外。"""
    start = time.time()
    while True:
        r = requests.get(f"{BASE_URL}/nodes/{node}/tasks/{upid}/status",
                        headers=HEADERS, verify=VERIFY_SSL)
        r.raise_for_status()
        st = r.json()["data"]
        if st["status"] == "stopped":
            if st.get("exitstatus") == "OK":
                return
            raise RuntimeError(f"Task {upid} failed: {st.get('exitstatus')}")
        if time.time() - start > timeout:
            raise TimeoutError(f"Task {upid} timed-out after {timeout}s")
        time.sleep(1)


def get_vm_ip(node: str, vmid: int) -> str | None:
    """透過 QEMU Guest Agent 取得 VM 的第一個 IPv4。"""
    url = f"{BASE_URL}/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces"
    r = requests.get(url, headers=HEADERS, verify=VERIFY_SSL)
    if r.status_code != 200:
        return None
    for iface in r.json().get("data", []):
        for ipd in iface.get("ip-addresses", []):
            ip = ipd.get("ip-address")
            if ip and ":" not in ip and ip != "127.0.0.1":
                return ip
    return None

# ───── 主要工作 ─────
def create_user_vm(node: str,
                   template_vmid: int,
                   new_vmid: int,
                   vm_name: str,
                   username: str,
                   password: str,
                   use_dhcp: bool = True,
                   ip_cidr: str | None = None,
                   gw_ip: str | None = None) -> dict:
    """
    從範本 Clone 一台 VM → 套 Cloud-Init → 開機 → 取 IP。
    回傳 dict，內含 ssh 指令與錯誤訊息。
    """

    try:
        # ① Clone
        print(f"[1/4] Clone {template_vmid} → {new_vmid}")
        r = requests.post(f"{BASE_URL}/nodes/{node}/qemu/{template_vmid}/clone",
                          headers=HEADERS, verify=VERIFY_SSL, data={
                              "newid": new_vmid,
                              "name": vm_name,
                              "full": 1
                          })
        r.raise_for_status()
        wait_for_task(node, r.json()["data"])

        # ② Cloud-Init 設定
        print("[2/4] Apply Cloud-Init config")
        ipconfig = "ip=dhcp" if use_dhcp else f"ip={ip_cidr},gw={gw_ip}"
        r = requests.post(f"{BASE_URL}/nodes/{node}/qemu/{new_vmid}/config",
                          headers=HEADERS, verify=VERIFY_SSL, data={
                              "ciuser": username,
                              "cipassword": password,
                              "ipconfig0": ipconfig
                          })
        r.raise_for_status()

        # ③ 開機
        print("[3/4] Start VM")
        r = requests.post(f"{BASE_URL}/nodes/{node}/qemu/{new_vmid}/status/start",
                          headers=HEADERS, verify=VERIFY_SSL)
        r.raise_for_status()
        wait_for_task(node, r.json()["data"])

        # ④ 取 IP
        print("[4/4] Query IP (guest-agent)")
        ip_addr = get_vm_ip(node, new_vmid)
        ssh_cmd = f"ssh {username}@{ip_addr}" if ip_addr else "IP N/A"

        return {
            "ok": True,
            "vmid": new_vmid,
            "ip": ip_addr,
            "ssh": ssh_cmd,
            "username": username,
            "password": password
        }

    # ─── 任何失敗都進這裡 ───
    except Exception as err:
        print(f"Error: {err}")
        try:
            requests.delete(f"{BASE_URL}/nodes/{node}/qemu/{new_vmid}",
                            headers=HEADERS, verify=VERIFY_SSL).raise_for_status()
            print("Rollback OK")
        except Exception as rb_err:
            print(f"Rollback failed: {rb_err}")
        return {"ok": False, "error": str(err), "vmid": new_vmid}


# ─────── 示範呼叫 ───────
if __name__ == "__main__":
    result = create_user_vm(
        node=NODE,
        template_vmid=TEMPLATE_ID,
        new_vmid=101,
        vm_name="student101",
        username="student",
        password="password",
        use_dhcp=True
    )
    print(result)

    
def restart_vm(node, vmid):
    # Step 1: Shutdown
    shutdown_url = f"{BASE_URL}/nodes/{node}/qemu/{vmid}/status/shutdown"
    shutdown_resp = requests.post(shutdown_url, headers=HEADERS, verify=False)

    if shutdown_resp.status_code != 200:
        return {
            "error": "Failed to shutdown VM",
            "details": shutdown_resp.text
        }

    # Step 2: Start again
    start_url = f"{BASE_URL}/nodes/{node}/qemu/{vmid}/status/start"
    start_resp = requests.post(start_url, headers=HEADERS, verify=False)

    if start_resp.status_code == 200:
        return {"data": start_resp.text.strip()}
    else:
        return {
            "error": "Failed to start VM after shutdown",
            "details": start_resp.text
        }


def get_vm_status(node, vmid):
    url = f"{BASE_URL}/nodes/{node}/qemu/{vmid}/status/current"
    response = requests.get(url, headers=HEADERS, verify=False)
    return response.json()


