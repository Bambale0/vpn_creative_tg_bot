"""
Системное управление VPN сервером через админку
"""

from fastapi import APIRouter, Depends, HTTPException
import subprocess
import psutil
import json
from datetime import datetime
from typing import List, Dict
from config.dependencies import get_admin, DB, log

router = APIRouter(prefix="/admin/api/system", tags=["admin"])


@router.get("/status")
async def get_system_status(admin=Depends(get_admin)):
    try:
        # System info
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # WireGuard info
        wg_status = subprocess.check_output(['wg', 'show', 'all']).decode()
        
        # Active connections
        netstat = subprocess.check_output(['netstat', '-tunlp']).decode()
        
        return {
            "system": {
                "cpu": cpu,
                "memory": {
                    "total": memory.total,
                    "used": memory.used,
                    "percent": memory.percent
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "percent": disk.percent
                }
            },
            "wireguard": wg_status,
            "connections": netstat
        }
    except Exception as e:
        log().error(f"Error getting system status: {e}")
        raise HTTPException(500, "Failed to get system status")


@router.post("/restart/vpn")
async def restart_vpn(admin=Depends(get_admin)):
    try:
        subprocess.run(['systemctl', 'restart', 'wg-quick@wg0'], check=True)
        await DB.execute("""
            INSERT INTO admin_actions (admin_id, action_type, details)
            VALUES (?, 'restart_vpn', 'VPN service restarted')
        """, (admin,))
        return {"success": True}
    except Exception as e:
        log().error(f"Error restarting VPN: {e}")
        raise HTTPException(500, "Failed to restart VPN")


@router.post("/restart/bot")
async def restart_bot(admin=Depends(get_admin)):
    try:
        subprocess.run(['systemctl', 'restart', 'vpnbot'], check=True)
        await DB.execute("""
            INSERT INTO admin_actions (admin_id, action_type, details)
            VALUES (?, 'restart_bot', 'Bot service restarted')
        """, (admin,))
        return {"success": True}
    except Exception as e:
        log().error(f"Error restarting bot: {e}")
        raise HTTPException(500, "Failed to restart bot")


@router.get("/logs/{service}")
async def get_logs(service: str, lines: int=100, admin=Depends(get_admin)):
    log_files = {
        'vpn': '/var/log/vpn/vpn.log',
        'bot': '/root/vpnbot/logs/bot.log',
        'webapp': '/root/vpnbot/logs/webapp.log',
        'system': '/var/log/syslog'
    }
    
    if service not in log_files:
        raise HTTPException(400, "Invalid service specified")
        
    try:
        output = subprocess.check_output(
            ['tail', '-n', str(lines), log_files[service]]
        ).decode()
        return {"logs": output.splitlines()}
    except Exception as e:
        log().error(f"Error getting logs for {service}: {e}")
        raise HTTPException(500, "Failed to get logs")


@router.get("/audit")
async def get_audit_log(
    start_date: str=None,
    end_date: str=None,
    admin=Depends(get_admin)
):
    query = """
        SELECT aa.*, u.username 
        FROM admin_actions aa
        LEFT JOIN users u ON aa.admin_id = u.user_id
        WHERE 1=1
    """
    params = []
    
    if start_date:
        query += " AND aa.timestamp >= ?"
        params.append(start_date)
    if end_date:
        query += " AND aa.timestamp <= ?"
        params.append(end_date)
        
    query += " ORDER BY aa.timestamp DESC LIMIT 1000"
    
    try:
        actions = await DB.fetch(query, params)
        return {"actions": actions}
    except Exception as e:
        log().error(f"Error getting audit log: {e}")
        raise HTTPException(500, "Failed to get audit log")
