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

console = Console(theme=Theme({
    "ok": "green",
    "issue": "red"
}))

@dataclass
class NetworkDevice:
    ip: str
    username: str
    password: str
    device_type: str

def detect_device_type(ip, username, password):
    params = {
        "device_type": "autodetect",
        "host": ip,
        "username": username,
        "password": password,
    }
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

def get_interface_details(device):
    conn = ConnectHandler(
        host=device.ip,
        username=device.username,
        password=device.password,
        device_type=device.device_type,
    )
    raw = conn.send_command("show interfaces")
    parsed = parse_output(platform=device.device_type,
                          command="show interfaces",
                          data=raw)
    return {entry["interface"]: entry for entry in parsed}

def display_interface_stats(device, details):
    counters = [
        ("input_rate", "Input Rate"),
        ("output_rate", "Output Rate"),
        ("input_pps", "Input PPS"),
        ("output_pps", "Output PPS"),
        ("input_packets", "Input Packets"),
        ("output_packets", "Output Packets"),
        ("input_errors", "Input Errors"),
        ("output_errors", "Output Errors"),
        ("crc", "CRC Errors"),
        ("frame", "Frame Errors"),
        ("overrun", "Overruns"),
    ]
    table = Table(title=f"{device.ip}", expand=True)
    table.add_column("Interface", no_wrap=True)
    table.add_column("Status", justify="center")
    for _, header in counters:
        table.add_column(header, justify="right")
    table.add_column("Issues")

    for name, stats in details.items():
        status = f"{stats['link_status']}/{stats['protocol_status']}"
        row = [name, status]
        issues = []
        for key, _ in counters:
            val = stats.get(key) or "0"
            row.append(val)
            if key in ("input_errors", "output_errors", "crc", "frame", "overrun") and val.isdigit() and int(val) > 0:
                issues.append(f"{key}={val}")
        if stats["link_status"] != "up" or stats["protocol_status"] != "up":
            issues.insert(0, status)
        row.append(", ".join(issues) or "all clear")
        style = "issue" if issues else "ok"
        table.add_row(*row, style=style)

    console.print(Panel(table, title=f"[bold]{device.ip} Interfaces[/bold]"))

def main():
    username = input("Username: ")
    password = getpass("Password: ")
    for dev in read_devices_csv(username, password):
        details = get_interface_details(dev)
        display_interface_stats(dev, details)

if __name__ == "__main__":
    main()