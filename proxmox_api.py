import time
import requests
import requests.packages.urllib3
from typing import List, Dict

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


def get_vm_ipv6(node: str, vmid: int) -> str | None:
    """透過 QEMU Guest Agent 取得 VM 的第一個『全域 IPv6』。"""
    url = f"{BASE_URL}/nodes/{node}/qemu/{vmid}/agent/network-get-interfaces"
    r   = requests.get(url, headers=HEADERS, verify=VERIFY_SSL)
    if r.status_code != 200:
        return None

    payload = r.json().get("data")            # 可能是 list 或 dict
    # 若是 dict，介面清單會在 payload["result"]
    if isinstance(payload, dict):
        interfaces = payload.get("result", [])
    else:
        interfaces = payload or []

    for iface in interfaces:
        if not isinstance(iface, dict):
            continue
        for ipd in iface.get("ip-addresses", []):
            ip = ipd.get("ip-address")
            if (
                ip                                          # 有值
                and ":" in ip                               # IPv6
                and not ip.startswith("fe80")               # 非 link-local
                and ip != "::1"                             # 非 loopback
            ):
                return ip
    return None





def create_user_vm(node: str,
                   template_vmid: int, 
                   new_vmid: int,
                   vm_name: str,
                   username: str,
                   password: str,
                   use_dhcp: bool = True,
                   ip_cidr: str | None = None,
                   gw_ip: str  | None = None) -> dict:

    try:
        # ① Clone
        r = requests.post(f"{BASE_URL}/nodes/{node}/qemu/{template_vmid}/clone",
                          headers=HEADERS, verify=VERIFY_SSL, data={
                              "newid": new_vmid,
                              "name": vm_name,
                              "full": 1
                          })
        r.raise_for_status()
        wait_for_task(node, r.json()["data"])

        # ② Cloud-Init config
        ipconfig = "ip6=dhcp" if use_dhcp else f"ip6={ip_cidr},gw6={gw_ip}"
        r = requests.post(f"{BASE_URL}/nodes/{node}/qemu/{new_vmid}/config",
                          headers=HEADERS, verify=VERIFY_SSL, data={
                              "ciuser": username,
                              "cipassword": password,
                              "ipconfig0": ipconfig
                          })
        r.raise_for_status()

        # ③ Start VM
        r = requests.post(f"{BASE_URL}/nodes/{node}/qemu/{new_vmid}/status/start",
                          headers=HEADERS, verify=VERIFY_SSL)
        r.raise_for_status()
        wait_for_task(node, r.json()["data"])

        # ④ Get IPv6
        ip_addr = None
        for _ in range(15):          # 最長等 15×2=30 秒
            ip_addr = get_vm_ipv6(node, new_vmid)
            if ip_addr:
                break
            time.sleep(2)

        ssh_cmd = f"ssh {username}@[{ip_addr}]" if ip_addr else "IPv6 N/A"

        return {
            "ok": True,
            "vmid": new_vmid,
            "ip6": ip_addr,
            "ssh": ssh_cmd,
            "username": username,
            "password": password
        }

    except Exception as err:
        try:
            requests.delete(f"{BASE_URL}/nodes/{node}/qemu/{new_vmid}",
                            headers=HEADERS, verify=VERIFY_SSL).raise_for_status()
        except Exception:
            pass
        return {"ok": False, "error": str(err), "vmid": new_vmid}

# ─────── 示範呼叫 ───────
if __name__ == "__main__":
    result = create_user_vm(
        node          = "pve",
        template_vmid = 9000,
        new_vmid      = 101,
        vm_name       = "student101",
        username      = "student",
        password      = "password",
        use_dhcp      = True          # 讓 cloud-init 用 DHCPv6
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


def build_ssh6_cmd(node: str, vmid: int, username: str) -> dict:
    """
    回傳指定 VM 的 IPv6 與 SSH 指令（若抓不到 IPv6 會回傳 None）
    """
    ip6 = get_vm_ipv6(node, vmid)
    ssh = f"ssh {username}@[{ip6}]" if ip6 else None
    return {"ip6": ip6, "ssh": ssh}

def list_vms(node: str) -> list[dict]:
    """回傳節點下所有 VM 的基本資訊（不含 IP）。"""
    url = f"{BASE_URL}/nodes/{node}/qemu"
    r = requests.get(url, headers=HEADERS, verify=VERIFY_SSL)
    r.raise_for_status()
    return r.json().get("data", [])


def get_vm_info(node: str, vmid: int) -> dict:
    """回傳單一 VM 的名稱、電源狀態與 IPv6。"""
    status_url = f"{BASE_URL}/nodes/{node}/qemu/{vmid}/status/current"
    resp = requests.get(status_url, headers=HEADERS, verify=VERIFY_SSL)
    if resp.status_code != 200:
        return {"ok": False, "vmid": vmid, "error": resp.text}

    data = resp.json().get("data", {})
    name = data.get("vmid")
    power = data.get("status")
    ip6 = get_vm_ipv6(node, vmid)

    return {
        "ok": True,
        "vmid": vmid,
        "name": name,
        "status": power,
        "ip6": ip6,
        "ssh": f"ssh s{name}@[{ip6}]" if ip6 else None,
    }

def list_vms_by_owner(node: str, owner: str) -> List[Dict]:
    """只回傳屬於登入者 (owner) 的 VM。約定名稱前綴 'vm-<user_id>'"""
    all_vms = list_vms(node)
    result = []
    for vm in all_vms:
        vmid = vm.get("vmid")
        name = vm.get("name", "")
        if name == f"vm-{owner}" or name.startswith(f"vm-{owner}-"):
            result.append(get_vm_info(node, vmid))
    return result

def list_nodes() -> List[Dict]:
    url = f"{BASE_URL}/nodes"
    r = requests.get(url, headers=HEADERS, verify=VERIFY_SSL)
    r.raise_for_status()
    return r.json().get("data", [])

