import asyncio
import socket
import subprocess
import sys
import time
import psutil
import pytest
from websockets.client import connect

# Address details for running stress test server
HOST = "127.0.0.1"
PORT = 8999
WS_URL = f"ws://{HOST}:{PORT}/ws/interview"

def wait_for_server(host: str, port: int, timeout: float = 15.0) -> bool:
    """Waits dynamically for the server port to open."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.2)
    return False

async def send_client_traffic(client_id: int, num_frames: int):
    """Simulates a single candidate sending SDP offers."""
    import httpx
    
    uri = f"http://{HOST}:{PORT}/interview/candidate_stress_{client_id}/offer"
    dummy_payload = {
        "sdp": "v=0\r\no=- 4611731400430051336 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=extmap-allow-mixed\r\na=msid-semantic: WMS\r\n",
        "type": "offer"
    }
    
    latencies = []
    try:
        async with httpx.AsyncClient() as client:
            for _ in range(num_frames):
                start = time.perf_counter()
                response = await client.post(uri, json=dummy_payload, timeout=4.0)
                response.raise_for_status()
                latencies.append(time.perf_counter() - start)
                await asyncio.sleep(0.05)
    except Exception as e:
        return False, latencies, f"Client {client_id} Error: {type(e).__name__}: {e}"
    
    return True, latencies, None

def json_dumps(d):
    import json
    return json.dumps(d)

@pytest.mark.asyncio
async def test_high_load_resilience():
    """Stress tests the WebSocket server under concurrent candidate connections."""
    cmd = [
        sys.executable, "-m", "uvicorn", "src.main:app",
        "--host", HOST,
        "--port", str(PORT),
        "--log-level", "info"
    ]
    
    # Write logs to a file to prevent pipe buffer deadlock
    with open("server.log", "w") as log_file:
        proc = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)
        
        # Wait dynamically for the port to open
        server_ready = wait_for_server(HOST, PORT)
        assert server_ready, "Server failed to start within timeout"
        
        # Retrieve process resources
        process = psutil.Process(proc.pid)
        cpu_before = process.cpu_percent(interval=0.1)
        mem_before = process.memory_info().rss / (1024 * 1024)
        
        num_concurrent_users = 10
        frames_per_user = 5
        
        print(f"\n--- Stress Test Started ---")
        print(f"Concurrent users: {num_concurrent_users}")
        print(f"Frames per user: {frames_per_user}")
        
        start_time = time.perf_counter()
        tasks = [send_client_traffic(i, frames_per_user) for i in range(num_concurrent_users)]
        results = await asyncio.gather(*tasks)
        
        duration = time.perf_counter() - start_time
        
        cpu_after = process.cpu_percent(interval=0.1)
        mem_after = process.memory_info().rss / (1024 * 1024)
        
        # Terminate process cleanly
        proc.terminate()
        proc.wait()
        
    success_count = sum(1 for r in results if r[0])
    errors = [r[2] for r in results if r[2] is not None]
    
    if success_count < num_concurrent_users:
        print("--- Server Logs on Failure ---")
        try:
            with open("server.log", "r") as f:
                print(f.read())
        except Exception as log_err:
            print(f"Could not read server logs: {log_err}")
            
    print("--- Errors encountered during stress test ---")
    for err in errors[:5]:
        print(err)
        
    all_latencies = []
    for r in results:
        all_latencies.extend(r[1])
        
    avg_latency = (sum(all_latencies) / len(all_latencies)) * 1000 if all_latencies else 0
    
    print(f"--- Stress Test Results ---")
    print(f"Successful connections: {success_count}/{num_concurrent_users}")
    print(f"Total frames processed: {len(all_latencies)}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Average frame latency: {avg_latency:.2f} ms")
    print(f"Memory Change: {mem_after - mem_before:+.2f} MB")
    print(f"---------------------------")
    
    assert success_count == num_concurrent_users, f"Some WebSocket connections failed: {errors[:3]}"
