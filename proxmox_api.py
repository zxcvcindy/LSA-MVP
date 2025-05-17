import requests

PVE_HOST = "10.32.1.100"
USER = "root@pam!LSAlab"
TOKEN = "c9bc7679-c908-48f1-957c-17addd105dae"

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


def create_vm(node, vmid, name, cores, memory, storage, iso):
    url = f"{BASE_URL}/nodes/{node}/qemu"
    payload = {
        "vmid": vmid,
        "name": name,
        "cores": cores,
        "memory": memory,
        "scsihw": "virtio-scsi-pci",
        "scsi0": f"{storage}:8",  # 預設 8GB
        "net0": "virtio,bridge=vmbr0",
        "ide2": f"{iso},media=cdrom",
        "ostype": "l26"
    }
    response = requests.post(url, headers=HEADERS, data=payload, verify=False)

    if response.status_code == 200:
        # 有時 Proxmox 成功會傳純文字 UPID 開頭
        return {"data": response.text.strip()}
    else:
        # 顯示錯誤內容協助除錯
        return {
            "error": f"Create VM failed. Status {response.status_code}",
            "details": response.text
        }
    
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


