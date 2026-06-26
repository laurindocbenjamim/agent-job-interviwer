import React, { useState, useEffect } from 'react';
import { UploadCloud, CheckCircle, AlertCircle, Trash2, Download } from 'lucide-react';
import { API_BASE_URL } from '../../config';
import './AdminPage.css';

export const AdminPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [statusType, setStatusType] = useState<'success' | 'error' | ''>('');
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/admin/voice/file`, { method: 'HEAD' })
      .then(res => {
        if (res.ok) {
          setAudioUrl(`${API_BASE_URL}/admin/voice/file?t=${Date.now()}`);
        }
      })
      .catch(console.error);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setStatus('');
      setStatusType('');
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    
    setLoading(true);
    setStatus('Processing audio sample...');
    setStatusType('');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await fetch(`${API_BASE_URL}/admin/voice/clone`, {
        method: 'POST',
        body: formData,
      });
      
      if (response.ok) {
        setStatus('Voice cloned successfully! You can now use it in interviews.');
        setStatusType('success');
        setAudioUrl(`${API_BASE_URL}/admin/voice/file?t=${Date.now()}`);
      } else {
        setStatus('Failed to clone voice.');
        setStatusType('error');
      }
    } catch (err) {
      console.error(err);
      setStatus('Error connecting to server.');
      setStatusType('error');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteVoice = async () => {
    if (!window.confirm('Are you sure you want to delete the cloned voice?')) return;
    try {
      const response = await fetch(`${API_BASE_URL}/admin/voice/file`, {
        method: 'DELETE',
      });
      if (response.ok) {
        setAudioUrl(null);
        setStatus('Voice deleted.');
        setStatusType('success');
        setFile(null);
      } else {
        setStatus('Failed to delete voice.');
        setStatusType('error');
      }
    } catch (err) {
      console.error(err);
      setStatus('Error connecting to server.');
      setStatusType('error');
    }
  };

  return (
    <div className="admin-container fade-in">
      <div className="admin-header">
        <h1>Voice Cloning Setup</h1>
        <p className="admin-subtitle">Provide an audio clip to construct a synthetic voice model for the AI interviewer.</p>
      </div>

      <div className="admin-card glass-panel">
        <div className="upload-area">
          <div className="upload-icon-wrapper">
            <UploadCloud size={48} className="upload-icon" />
          </div>
          <h3>Upload Audio Sample</h3>
          <p>WAV or MP3 up to 10MB (3-10 seconds recommended)</p>
          
          <input 
            type="file" 
            id="voice-upload"
            accept="audio/*" 
            onChange={handleFileChange} 
            className="file-input-hidden"
          />
          <label htmlFor="voice-upload" className="btn-secondary">
            {file ? file.name : 'Select File'}
          </label>
        </div>
        
        <div className="action-area">
          <button 
            onClick={handleUpload} 
            disabled={!file || loading}
            className="btn-primary w-full"
          >
            {loading ? 'Processing...' : 'Generate Voice Model'}
          </button>
        </div>
        
        {status && (
          <div className={`status-alert ${statusType}`}>
            {statusType === 'success' ? <CheckCircle size={20} /> : <AlertCircle size={20} />}
            <span>{status}</span>
          </div>
        )}

        {audioUrl && (
          <div className="audio-player-container">
            <h4>Cloned Voice</h4>
            <div className="audio-controls-wrapper">
              <audio controls src={audioUrl} className="custom-audio-player">
                Your browser does not support the audio element.
              </audio>
              <div className="audio-actions">
                <a href={audioUrl} download="cloned_voice.wav" className="icon-btn download" title="Download">
                  <Download size={18} />
                </a>
                <button onClick={handleDeleteVoice} className="icon-btn delete" title="Delete">
                  <Trash2 size={18} />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
