from aiortc import RTCPeerConnection

active_sessions = {}
peer_connections: set[RTCPeerConnection] = set()
