from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.theme import Theme
from netmiko import ConnectHandler
from netmiko import SSHDetect
from ntc_templates.parse import parse_output
import csv
from dataclasses import dataclass
from getpass import getpass

console = Console(record=True, theme=Theme({"ok": "green", "issue": "red"}))

@dataclass
class NetworkDevice:
    ip: str
    username: str
    password: str
    device_type: str

def detect_device_type(ip, username, password):
    params = {"device_type": "autodetect", "host": ip, "username": username, "password": password}
    try:
        guesser = SSHDetect(**params)
        dt = guesser.autodetect() or "cisco_ios"
    except:
        dt = "cisco_ios"
    if "xe" in dt:
        dt = "cisco_ios"
    return dt

def read_devices_csv(username, password):
    devices = []
    with open('devices.csv', 'r') as f:
        for row in csv.reader(f):
            if not row:
                continue
            ip = row[0].strip()
            dt = detect_device_type(ip, username, password)
            devices.append(NetworkDevice(ip, username, password, dt))
    return devices

def get_device_hostname(device):
    conn = ConnectHandler(host=device.ip, username=device.username, password=device.password, device_type=device.device_type)
    line = conn.send_command("show running-config | include ^hostname")
    conn.disconnect()
    parts = line.strip().split()
    return parts[1] if len(parts) == 2 else device.ip

def get_interface_details(device):
    conn = ConnectHandler(host=device.ip, username=device.username, password=device.password, device_type=device.device_type)
    raw = conn.send_command("show interfaces")
    conn.disconnect()
    parsed = parse_output(platform=device.device_type, command="show interfaces", data=raw)
    return {entry["interface"]: entry for entry in parsed}

def display_interface_stats(name, ip, details):
    counters = [
        ("input_rate", "In Rate"), ("output_rate", "Out Rate"),
        ("input_pps", "In PPS"), ("output_pps", "Out PPS"),
        ("input_packets", "In Pkts"), ("output_packets", "Out Pkts"),
        ("input_errors", "In Err"), ("output_errors", "Out Err"),
        ("crc", "CRC"), ("frame", "Frame"), ("overrun", "Overrun"),
    ]
    table = Table(title=f"{name} ({ip}) Interfaces", expand=True)
    table.add_column("Interface", no_wrap=True)
    table.add_column("Status", justify="center")
    for _, hdr in counters:
        table.add_column(hdr, justify="right")
    table.add_column("Issues")

    for iface, stats in details.items():
        status = f"{stats['link_status']}/{stats['protocol_status']}"
        row = [iface, status]
        issues = []
        for key, _ in counters:
            val = stats.get(key) or "0"
            row.append(val)
            if key in ("input_errors","output_errors","crc","frame","overrun") and val.isdigit() and int(val)>0:
                issues.append(f"{key}={val}")
        if stats["link_status"]!="up" or stats["protocol_status"]!="up":
            issues.insert(0, status)
        row.append(", ".join(issues) or "all clear")
        style = "issue" if issues else "ok"
        table.add_row(*row, style=style)

    console.print(Panel(table))

def main():
    user = input("Username: ")
    pwd = getpass("Password: ")
    for dev in read_devices_csv(user, pwd):
        name = get_device_hostname(dev)
        details = get_interface_details(dev)
        display_interface_stats(name, dev.ip, details)
    console.save_html("interfaces_report.html")
    with open("interfaces_report.txt", "w") as f:
        f.write(console.export_text())

if __name__ == "__main__":
    main()