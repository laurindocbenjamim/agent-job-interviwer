from typing import Dict, Any

def evaluate_audio_decibels(average_volume: float) -> Dict[str, Any]:
    """
    Evaluates audio loudness to trigger voice warnings.
    """
    status = "normal"
    if average_volume > 2.0 and average_volume < 15.0:
        status = "too_soft"
    elif average_volume <= 2.0:
        status = "silent"
        
    return {
        "volume": average_volume,
        "status": status,
        "warning": "Speak Louder" if status == "too_soft" else None
    }
